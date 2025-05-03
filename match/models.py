import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel, SingletonModel
from match.exceptions import MatchJoinError


class MatchConfiguration(SingletonModel):
    simultaneous_game = models.BooleanField(default=False, verbose_name=_("Simultaneous availability"))

    def __str__(self):
        return _("Match Configuration")

    class Meta:
        verbose_name = _("Match Configuration")
        verbose_name_plural = _("Match Configuration")


class PlayerMatch:
    def __init__(self, player, match_type):
        self.player = player
        self.match_type = match_type
        self.errors = dict()

    def _is_player_blocked(self):
        pass

    def _simultaneous_game_check(self):
        pass

    def _can_player_pay(self):
        pass

    def can_join(self) -> tuple[bool, dict]:
        self._simultaneous_game_check()
        self._is_player_blocked()
        self._can_player_pay()
        can_join = len(self.errors.keys()) == 0
        return can_join, self.errors

    def pay_match_entry(self):
        pass


class MatchType(BaseModel):
    name = models.CharField(max_length=100, verbose_name=_("Name"), unique=True)
    priority = models.PositiveSmallIntegerField(verbose_name=_("Priority"), default=1)
    entry_cost = models.ForeignKey(to="shop.Cost", on_delete=models.SET_NULL, verbose_name=_("Entry cost"), null=True)
    min_xp = models.PositiveSmallIntegerField(verbose_name=_("Min XP"), default=0)
    min_cup = models.PositiveSmallIntegerField(verbose_name=_("Min Cup"), default=0)
    min_score = models.PositiveSmallIntegerField(verbose_name=_("Min Score"), default=0)

    config = models.JSONField(verbose_name=_("Config"), default=dict)

    # Winner
    winner_package = models.ForeignKey(to='shop.RewardPackage', on_delete=models.SET_NULL,
                                       verbose_name=_("Winner package"), null=True, blank=True)
    winner_xp = models.PositiveSmallIntegerField(verbose_name=_("Winner XP"), default=0)
    winner_cup = models.PositiveSmallIntegerField(verbose_name=_("Winner Cup"), default=0)
    winner_score = models.PositiveSmallIntegerField(verbose_name=_("Winner Score"), default=0)

    # Loser
    loser_package = models.ForeignKey(to='shop.RewardPackage', on_delete=models.SET_NULL,
                                      verbose_name=_("Loser package"), null=True, blank=True)
    loser_xp = models.PositiveSmallIntegerField(verbose_name=_("Loser XP"), default=0)
    loser_cup = models.PositiveSmallIntegerField(verbose_name=_("Loser Cup"), default=0)
    loser_score = models.PositiveSmallIntegerField(verbose_name=_("Loser Score"), default=0)

    class Meta:
        verbose_name = _("Match Type")
        verbose_name_plural = _("Match Types")
        ordering = ("priority", "name")

    def can_join(self, player):
        player_match = PlayerMatch(player, self)
        can_join, errors = player_match.can_join()
        return can_join, errors

    def pay_match_entry(self, player):
        player_match = PlayerMatch(player, self)
        player_match.pay_match_entry()

    def __str__(self):
        return _(self.name).__str__()


class Match(BaseModel):
    uuid = models.UUIDField(verbose_name="UUID", unique=True, primary_key=True, default=uuid.uuid4, editable=False)
    players = models.ManyToManyField(to='user.User', verbose_name=_("Players"), blank=True)
    match_type = models.ForeignKey(to=MatchType, on_delete=models.PROTECT, verbose_name=_("Match Type"),
                                   related_name="matches")
    owner = models.ForeignKey(to="user.User", verbose_name=_("Owner"), on_delete=models.CASCADE, related_name="matches")

    def __str__(self):
        return f'{self.owner} - {self.match_type}'

    @classmethod
    def start(cls, owner, players, match_type: MatchType):
        match_uuid = uuid.uuid4()
        can_join, errors = match_type.can_join(player=owner)
        if not can_join:
            raise MatchJoinError(errors)
        match_type.pay_match_entry(player=owner)
        return cls.objects.create(uuid=match_uuid, players=players, match_type=match_type)

    def check_out(self):
        pass

    def finish(self):
        pass

    def create_results(self):
        pass

    def archive_results(self):
        pass

    class Meta:
        verbose_name = _("Match")
        verbose_name_plural = _("Matches")
