import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel, SingletonModel, SingletonCachableModel
from match.controllers import PlayerMatch, PlayerMatchCheckout
from match.exceptions import MatchJoinError
from user.models import User


class MatchConfiguration(SingletonCachableModel):
    simultaneous_game = models.BooleanField(default=False, verbose_name=_("Simultaneous availability"))

    def __str__(self):
        return _("Match Configuration")

    class Meta:
        verbose_name = _("Match Configuration")
        verbose_name_plural = _("Match Configuration")

class MatchType(BaseModel):
    class MatchTypeModes(models.TextChoices):
        ONLINE = 'online', _('Online')
        OFFLINE = 'offline', _('Offline')

    name = models.CharField(max_length=100, verbose_name=_("Name"), unique=True)
    priority = models.PositiveSmallIntegerField(verbose_name=_("Priority"), default=1)
    entry_cost = models.ForeignKey(to="shop.Cost", on_delete=models.SET_NULL, verbose_name=_("Entry cost"), null=True)
    min_xp = models.PositiveSmallIntegerField(verbose_name=_("Min XP"), default=0)
    min_cup = models.PositiveSmallIntegerField(verbose_name=_("Min Cup"), default=0)
    min_score = models.PositiveSmallIntegerField(verbose_name=_("Min Score"), default=0)

    config = models.JSONField(verbose_name=_("Config"), default=dict)

    # Winner
    winner_package = models.ForeignKey(to='shop.RewardPackage', on_delete=models.SET_NULL,
                                       verbose_name=_("Winner package"), null=True, blank=True,
                                       related_name='match_type_winner_packages')
    winner_xp = models.PositiveSmallIntegerField(verbose_name=_("Winner XP"), default=0)
    winner_cup = models.PositiveSmallIntegerField(verbose_name=_("Winner Cup"), default=0)
    winner_score = models.PositiveSmallIntegerField(verbose_name=_("Winner Score"), default=0)

    # Loser
    loser_package = models.ForeignKey(to='shop.RewardPackage', on_delete=models.SET_NULL,
                                      verbose_name=_("Loser package"), null=True, blank=True,
                                      related_name='match_type_loser_packages')
    loser_xp = models.PositiveSmallIntegerField(verbose_name=_("Loser XP"), default=0)
    loser_cup = models.PositiveSmallIntegerField(verbose_name=_("Loser Cup"), default=0)
    loser_score = models.PositiveSmallIntegerField(verbose_name=_("Loser Score"), default=0)

    mode = models.CharField(max_length=15, choices=MatchTypeModes.choices, default=MatchTypeModes.ONLINE)

    banner = models.ImageField(upload_to='match/type/banner', null=True, blank=True, verbose_name=_("Banner"))

    pool_name = models.CharField(
        max_length=100,
        verbose_name=_("Pool Name"),
        help_text=_("OpenMatch pool name for this match type"),
        default="default_pool"
    )
    
    # Search fields configuration
    search_fields_config = models.JSONField(
        default=dict,
        verbose_name=_("Search Fields Config"),
        help_text=_("Configuration for OpenMatch search fields")
    )
    
    # Matchmaking settings
    max_players = models.PositiveSmallIntegerField(
        default=2,
        verbose_name=_("Max Players"),
        help_text=_("Maximum number of players for this match type")
    )
    
    min_players = models.PositiveSmallIntegerField(
        default=2,
        verbose_name=_("Min Players"),
        help_text=_("Minimum number of players for this match type")
    )
    
    matchmaking_timeout = models.PositiveIntegerField(
        default=300,  # 5 minutes
        verbose_name=_("Matchmaking Timeout (seconds)"),
        help_text=_("How long to wait for matchmaking before timeout")
    )

    class Meta:
        verbose_name = _("Match Type")
        verbose_name_plural = _("Match Types")
        ordering = ("priority", "name")

    def can_join(self, player):
        player_match = PlayerMatch(player=player, match_type=self, config=MatchConfiguration.load())
        can_join, errors = player_match.can_join()
        return can_join, errors

    def pay_match_entry(self, player):
        player_match = PlayerMatch(player=player, match_type=self, config=MatchConfiguration.load())
        player_match.pay_match_entry()

    def __str__(self):
        return _(self.name).__str__()


class Match(BaseModel):
    uuid = models.UUIDField(verbose_name="UUID", unique=True, primary_key=True, default=uuid.uuid4, editable=False)
    players = models.ManyToManyField(to='user.User', verbose_name=_("Players"), blank=True)
    match_type = models.ForeignKey(to=MatchType, on_delete=models.PROTECT, verbose_name=_("Match Type"),
                                   related_name="matches")

    def __str__(self):
        return f'{",".join(self.players.values_list("id", flat=True))} - {self.match_type}'

    @classmethod
    def get_random_players(cls, count: int):
        return User.get_random_users(count=count)

    @classmethod
    def start(cls, match_uuid, players, match_type: MatchType):
        match_uuid = uuid.uuid4() if not match_uuid else match_uuid
        players = list(players)
        for player in players:
            can_join, errors = match_type.can_join(player=player)
            if not can_join:
                raise MatchJoinError(errors)
            match_type.pay_match_entry(player=player)
            
        match = cls.objects.create(uuid=match_uuid, match_type=match_type)
        match.players.set(players)
        return match

    def check_out(self, player_data, player):
        player_checkout_manager = PlayerMatchCheckout(player, self.match_type)
        return player_checkout_manager.check_out_player(player_data['result'])

    def finish(self, results):
        players_data = results["players"]
        stat_log = dict()
        for player_data in players_data:
            try:
                player = User.objects.get(id=player_data["id"])
            except User.DoesNotExist:
                continue
            stat_log[player.username] = self.check_out(player_data, player)
        result = self.create_results({**results, "stat_log": stat_log})
        self.delete()
        return result

    def create_results(self, results):
        match_uuid = self.uuid
        players = self.players.all()
        history = {
            **results,
            "recorded_players": [
                {
                    "id": player.id,
                    "profile_name": player.profile_name,
                } for player in players.all()
            ]

        }
        return MatchResult.create(match_uuid=match_uuid, players=players, history=history, match_type=self.match_type)

    def archive_results(self):
        pass

    @classmethod
    def get_player_current_match(cls, player):
        return cls.objects.filter(players=player).first()

    class Meta:
        verbose_name = _("Match")
        verbose_name_plural = _("Matches")
        ordering = ('-created_time', )


class MatchResult(BaseModel):
    match_uuid = models.UUIDField(verbose_name="UUID", default=uuid.uuid4, editable=False)
    players = models.ManyToManyField(to='user.User', verbose_name=_("Players"), blank=True, related_name="game_results")
    match_type = models.ForeignKey(to=MatchType, on_delete=models.SET_NULL, verbose_name=_("Match Type"),
                                   related_name="match_results", null=True, blank=True)
    history = models.JSONField(verbose_name=_("History"), default=dict)

    class Meta:
        verbose_name = _("Match Result")
        verbose_name_plural = _("Match Results")

    def __str__(self):
        return self.match_uuid.__str__()

    @classmethod
    def create(cls, match_uuid, players, match_type, history):
        obj = cls.objects.create(match_uuid=match_uuid, match_type=match_type, history=history)
        obj.players.add(*players)
        return obj


class MatchmakingTicket(BaseModel):
    """
    Represents a matchmaking ticket in OpenMatch
    """
    class TicketStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        MATCHED = 'matched', _('Matched')
        CANCELLED = 'cancelled', _('Cancelled')
        ERROR = 'error', _('Error')

    ticket_id = models.CharField(max_length=255, unique=True, verbose_name=_("Ticket ID"))
    player = models.ForeignKey(
        to='user.User', 
        on_delete=models.CASCADE, 
        verbose_name=_("Player"),
        related_name='matchmaking_tickets'
    )
    match_type = models.ForeignKey(
        to='match.MatchType',
        on_delete=models.CASCADE,
        verbose_name=_("Match Type"),
        related_name='matchmaking_tickets'
    )
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.PENDING,
        verbose_name=_("Status")
    )
    search_fields = models.JSONField(
        default=dict,
        verbose_name=_("Search Fields"),
        help_text=_("OpenMatch search fields for this ticket")
    )
    assignment = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Assignment"),
        help_text=_("Match assignment data from OpenMatch")
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Error Message")
    )

    class Meta:
        verbose_name = _("Matchmaking Ticket")
        verbose_name_plural = _("Matchmaking Tickets")

    def __str__(self):
        return f"{self.player.username} - {self.match_type.name} ({self.status})"

    @classmethod
    def get_active_ticket(cls, player, match_type=None):
        """Get active matchmaking ticket for a player"""
        queryset = cls.objects.filter(
            player=player,
            status=cls.TicketStatus.PENDING,
            is_active=True
        )
        if match_type:
            queryset = queryset.filter(match_type=match_type)
        return queryset.first()

    def cancel(self):
        """Mark ticket as cancelled"""
        self.status = self.TicketStatus.CANCELLED
        self.save()

    def mark_matched(self, assignment_data):
        """Mark ticket as matched with assignment data"""
        self.status = self.TicketStatus.MATCHED
        self.assignment = assignment_data
        self.save()

    def mark_error(self, error_message):
        """Mark ticket as error with error message"""
        self.status = self.TicketStatus.ERROR
        self.error_message = error_message
        self.save()
