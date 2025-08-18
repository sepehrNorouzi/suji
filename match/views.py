from rest_framework import mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from django.utils.translation import gettext_lazy as _

from match.exceptions import MatchJoinError
from match.models import MatchType, Match, MatchmakingTicket
from match.permissions import IsGameServer
from match.serializers import MatchTypeSerializer, MatchSerializer, MatchCreateSerializer, MatchFinishSerializer, MatchmakingJoinSerializer, MatchmakingLeaveSerializer, MatchmakingStatusSerializer, MatchmakingTicketSerializer
from match.services.matchmaking import MatchmakingManager


class MatchTypeViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = MatchTypeSerializer
    queryset = MatchType.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, ]

    @action(methods=['GET'], detail=True, url_path='can_join', url_name='can-join')
    def can_join(self, request, *args, **kwargs):
        obj: MatchType = self.get_object()
        can_join, errors = obj.can_join(request.user)
        if not can_join:
            return Response({"errors": errors}, status=status.HTTP_403_FORBIDDEN)

        return Response(status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path='get_by_name', url_name='get-by-name',
            permission_classes=[IsGameServer | IsAuthenticated, ])
    def get_by_name(self, request, *args, **kwargs):
        name = self.request.query_params.get('name', '')
        obj = get_object_or_404(self.get_queryset(), name=name)
        return Response(MatchTypeSerializer(obj).data)


class MatchViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = MatchSerializer
    queryset = Match.objects.filter(is_active=True)
    lookup_field = 'uuid'
    game_server_actions = ['create_match', 'finish', ]
    client_actions = ['list', 'retrieve', 'me', ]

    def get_permissions(self):
        if self.action in self.game_server_actions:
            return [IsGameServer(), ]
        return [permissions.OR(IsGameServer(), IsAuthenticated())]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)
        return qs

    def get_current_player_match(self) -> Match:
        return Match.get_player_current_match(self.request.user)

    @action(methods=['POST'], detail=False, serializer_class=MatchCreateSerializer, url_name='create',
            url_path='create',)
    def create_match(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            match = serializer.create(serializer.validated_data)
        except MatchJoinError as e:
            return Response(e.args[0], status=status.HTTP_400_BAD_REQUEST)
        return Response(MatchSerializer(match).data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=True, serializer_class=MatchFinishSerializer, url_name='finish',
            url_path='finish')
    def finish(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        match = self.get_object()
        try:
            result = match.finish(serializer.validated_data)
            return Response(self.serializer_class({"result": result}).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print("EXCEPTION:", e)
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'], detail=False, serializer_class=MatchSerializer, url_path='me', url_name='me')
    def me(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        match = self.get_current_player_match()
        if not match:
            return Response(data={"detail": _("User has no active match"), "code": "no_active_match"},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(self.serializer_class(match).data)

class MatchmakingViewSet(GenericViewSet):
    """
    ViewSet for matchmaking operations
    """
    permission_classes = [IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matchmaking_manager = MatchmakingManager()
    
    @action(
        methods=['POST'], 
        detail=False, 
        url_path='join', 
        url_name='join',
        serializer_class=MatchmakingJoinSerializer
    )
    def join_matchmaking(self, request, *args, **kwargs):
        """
        Join matchmaking queue for a specific match type
        
        POST /api/matchmaking/join/
        {
            "match_type_id": 1,
            "search_fields": {
                "region": "us-west",
                "skill_level": "intermediate",
                "string_args": {...},
                "double_args": {...}
            }
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        match_type_id = serializer.validated_data['match_type_id']
        search_fields = serializer.validated_data.get('search_fields', {})
        
        success, result = self.matchmaking_manager.join_matchmaking(
            player=request.user,
            match_type_id=match_type_id,
            search_fields=search_fields
        )
        
        if success:
            return Response(
                {
                    "success": True,
                    "message": _("Successfully joined matchmaking queue"),
                    "data": result
                },
                status=status.HTTP_201_CREATED
            )
        else:
            error_status = status.HTTP_400_BAD_REQUEST
            if "Already in matchmaking" in result.get("error", ""):
                error_status = status.HTTP_409_CONFLICT
            elif "Cannot join match" in result.get("error", ""):
                error_status = status.HTTP_403_FORBIDDEN
            
            return Response(
                {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "details": result.get("details", {})
                },
                status=error_status
            )
    
    @action(
        methods=['POST'], 
        detail=False, 
        url_path='leave', 
        url_name='leave',
        serializer_class=MatchmakingLeaveSerializer
    )
    def leave_matchmaking(self, request, *args, **kwargs):
        """
        Leave matchmaking queue
        
        POST /api/matchmaking/leave/
        {
            "match_type_id": 1  // Optional: specific match type to leave
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        match_type_id = serializer.validated_data.get('match_type_id')
        
        success, result = self.matchmaking_manager.leave_matchmaking(
            player=request.user,
            match_type_id=match_type_id
        )
        
        if success:
            return Response(
                {
                    "success": True,
                    "message": _("Successfully left matchmaking queue"),
                    "data": result
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "details": result.get("details", {})
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(
        methods=['GET'], 
        detail=False, 
        url_path='status', 
        url_name='status',
        serializer_class=MatchmakingStatusSerializer
    )
    def get_status(self, request, *args, **kwargs):
        """
        Get current matchmaking status for the authenticated user
        
        GET /api/matchmaking/status/
        """
        result = self.matchmaking_manager.get_matchmaking_status(request.user)
        
        return Response(
            {
                "success": True,
                "data": result
            },
            status=status.HTTP_200_OK
        )
    
    @action(
        methods=['GET'], 
        detail=False, 
        url_path='tickets', 
        url_name='tickets',
        serializer_class=MatchmakingTicketSerializer
    )
    def list_tickets(self, request, *args, **kwargs):
        """
        List all matchmaking tickets for the authenticated user
        
        GET /api/matchmaking/tickets/
        """
        tickets = MatchmakingTicket.objects.filter(
            player=request.user,
            is_active=True
        ).order_by('-created_time')
        
        serializer = self.get_serializer(tickets, many=True)
        
        return Response(
            {
                "success": True,
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    @action(
        methods=['POST'], 
        detail=False, 
        url_path='cancel/(?P<ticket_id>[^/.]+)', 
        url_name='cancel-ticket'
    )
    def cancel_ticket(self, request, ticket_id=None, *args, **kwargs):
        """
        Cancel a specific matchmaking ticket
        
        POST /api/matchmaking/cancel/{ticket_id}/
        """
        try:
            ticket = MatchmakingTicket.objects.get(
                ticket_id=ticket_id,
                player=request.user,
                status=MatchmakingTicket.TicketStatus.PENDING,
                is_active=True
            )
        except MatchmakingTicket.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": _("Ticket not found or already processed")
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Use the matchmaking manager to properly cancel
        success, result = self.matchmaking_manager.leave_matchmaking(
            player=request.user,
            match_type_id=ticket.match_type.id
        )
        
        if success:
            return Response(
                {
                    "success": True,
                    "message": _("Ticket cancelled successfully"),
                    "data": result
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": result.get("error", "Failed to cancel ticket"),
                    "details": result.get("details", {})
                },
                status=status.HTTP_400_BAD_REQUEST
            )
