import logging
from typing import Dict, Optional, Tuple
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from match.models import MatchType, MatchmakingTicket
from openmatch.services.open_match_service import OpenMatchService
from match.exceptions import MatchJoinError

logger = logging.getLogger(__name__)


class MatchmakingManager:
    """
    Manager class for handling matchmaking operations
    """
    
    def __init__(self):
        self.openmatch_service = OpenMatchService()
    
    def join_matchmaking(self, player, match_type_id: int, search_fields: Dict = None) -> Tuple[bool, Dict]:
        """
        Join matchmaking for a specific match type
        
        Args:
            player: User instance
            match_type_id: ID of the match type
            search_fields: Additional search fields for matchmaking
            
        Returns:
            Tuple of (success: bool, result: dict)
        """
        try:
            # Get match type
            try:
                match_type = MatchType.objects.get(id=match_type_id, is_active=True)
            except MatchType.DoesNotExist:
                return False, {"error": "Invalid match type"}
            
            can_join, join_errors = match_type.can_join(player)
            if not can_join:
                return False, {"error": "Cannot join match", "details": join_errors}
            
            existing_ticket = MatchmakingTicket.get_active_ticket(player)
            if existing_ticket:
                return False, {
                    "error": "Already in matchmaking queue", 
                    "ticket_id": existing_ticket.ticket_id,
                    "match_type": existing_ticket.match_type.name
                }
            
            # Prepare search fields
            final_search_fields = self._prepare_search_fields(player, match_type, search_fields or {})
            
            # Create ticket in OpenMatch
            om_result = self.openmatch_service.create_ticket(
                player_id=str(player.id),
                match_type_name=match_type.name,
                search_fields=final_search_fields
            )
            
            if not om_result["success"]:
                logger.error(f"Failed to create OpenMatch ticket: {om_result}")
                return False, {
                    "error": "Failed to join matchmaking",
                    "details": om_result.get("error", "Unknown error")
                }
            
            # Create local ticket record
            with transaction.atomic():
                ticket = MatchmakingTicket.objects.create(
                    ticket_id=om_result["ticket_id"],
                    player=player,
                    match_type=match_type,
                    status=MatchmakingTicket.TicketStatus.PENDING,
                    search_fields=final_search_fields
                )
            
            logger.info(f"Player {player.id} joined matchmaking for {match_type.name}")
            
            return True, {
                "ticket_id": ticket.ticket_id,
                "match_type": match_type.name,
                "status": ticket.status,
                "search_fields": ticket.search_fields
            }
            
        except Exception as e:
            logger.error(f"Error joining matchmaking: {str(e)}")
            return False, {"error": "Internal error", "details": str(e)}
    
    def leave_matchmaking(self, player, match_type_id: Optional[int] = None) -> Tuple[bool, Dict]:
        """
        Leave matchmaking (cancel ticket)
        
        Args:
            player: User instance
            match_type_id: Optional specific match type ID to leave
            
        Returns:
            Tuple of (success: bool, result: dict)
        """
        try:
            # Find active tickets
            tickets_query = MatchmakingTicket.objects.filter(
                player=player,
                status=MatchmakingTicket.TicketStatus.PENDING,
                is_active=True
            )
            
            if match_type_id:
                tickets_query = tickets_query.filter(match_type_id=match_type_id)
            
            tickets = list(tickets_query)
            
            if not tickets:
                return False, {"error": "No active matchmaking tickets found"}
            
            cancelled_tickets = []
            errors = []
            
            # Cancel each ticket
            for ticket in tickets:
                # Cancel in OpenMatch
                om_result = self.openmatch_service.delete_ticket(ticket.ticket_id)
                
                if om_result["success"]:
                    # Update local ticket
                    with transaction.atomic():
                        ticket.cancel()
                    
                    cancelled_tickets.append({
                        "ticket_id": ticket.ticket_id,
                        "match_type": ticket.match_type.name
                    })
                    
                    logger.info(f"Cancelled ticket {ticket.ticket_id} for player {player.id}")
                else:
                    # Even if OpenMatch deletion fails, mark as cancelled locally
                    with transaction.atomic():
                        ticket.mark_error(f"Failed to delete from OpenMatch: {om_result.get('error', 'Unknown error')}")
                    
                    errors.append({
                        "ticket_id": ticket.ticket_id,
                        "error": om_result.get("error", "Unknown error")
                    })
                    
                    logger.error(f"Failed to cancel ticket {ticket.ticket_id}: {om_result}")
            
            if cancelled_tickets:
                result = {
                    "cancelled_tickets": cancelled_tickets
                }
                if errors:
                    result["errors"] = errors
                
                return True, result
            else:
                return False, {"error": "Failed to cancel any tickets", "details": errors}
                
        except Exception as e:
            logger.error(f"Error leaving matchmaking: {str(e)}")
            return False, {"error": "Internal error", "details": str(e)}
    
    def get_matchmaking_status(self, player) -> Dict:
        """
        Get current matchmaking status for a player
        
        Args:
            player: User instance
            
        Returns:
            Dict containing matchmaking status
        """
        try:
            active_tickets = MatchmakingTicket.objects.filter(
                player=player,
                status=MatchmakingTicket.TicketStatus.PENDING,
                is_active=True
            )
            
            if not active_tickets.exists():
                return {
                    "in_queue": False,
                    "tickets": []
                }
            
            tickets_data = []
            for ticket in active_tickets:
                tickets_data.append({
                    "ticket_id": ticket.ticket_id,
                    "match_type": ticket.match_type.name,
                    "match_type_id": ticket.match_type.id,
                    "status": ticket.status,
                    "search_fields": ticket.search_fields,
                    "created_time": ticket.created_time.isoformat(),
                    "updated_time": ticket.updated_time.isoformat()
                })
            
            return {
                "in_queue": True,
                "tickets": tickets_data
            }
            
        except Exception as e:
            logger.error(f"Error getting matchmaking status: {str(e)}")
            return {
                "in_queue": False,
                "tickets": [],
                "error": str(e)
            }
    
    def _prepare_search_fields(self, player, match_type: MatchType, custom_fields: Dict) -> Dict:
        """
        Prepare search fields for OpenMatch ticket
        
        Args:
            player: User instance
            match_type: MatchType instance
            custom_fields: Custom search fields
            
        Returns:
            Dict containing prepared search fields
        """
        player_stats = getattr(player, 'stats', None)
        
        search_fields = {
            "string_args": {
                "region": custom_fields.get("region", "default"),
                "skill_level": custom_fields.get("skill_level", "beginner"),
            },
            "double_args": {}
        }
        
        if player_stats:
            search_fields["double_args"].update({
                "score": float(player_stats.score),
                "xp": float(player_stats.xp),
                "cup": float(player_stats.cup),
            })
        
        if hasattr(match_type, 'search_fields_config') and match_type.search_fields_config:
            config = match_type.search_fields_config
            if "string_args" in config:
                search_fields["string_args"].update(config["string_args"])
            if "double_args" in config:
                search_fields["double_args"].update(config["double_args"])
        
        if "string_args" in custom_fields:
            search_fields["string_args"].update(custom_fields["string_args"])
        if "double_args" in custom_fields:
            search_fields["double_args"].update(custom_fields["double_args"])
        
        return search_fields