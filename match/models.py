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
    owner = models.ForeignKey(to="user.User", verbose_name=_("Owner"), on_delete=models.CASCADE, related_name="matches")

    def __str__(self):
        return f'{self.owner} - {self.match_type}'

    @classmethod
    def get_random_players(cls, count: int):
        return User.get_random_users(count=count)

    @classmethod
    def start(cls, match_uuid, owner, players, match_type: MatchType):
        match_uuid = uuid.uuid4() if not match_uuid else match_uuid
        players = list(players)
        can_join, errors = match_type.can_join(player=owner)
        if not can_join:
            raise MatchJoinError(errors)
        match_type.pay_match_entry(player=owner)
        random_players = cls.get_random_players(count=4-len(players)) # Make variable
        all_players = players + list(random_players)
        match =  cls.objects.create(uuid=match_uuid, match_type=match_type, owner=owner)
        match.players.set(all_players)
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
    def get_player_current_match(cls, owner):
        return cls.objects.filter(owner=owner).first()

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
