import datetime
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel, SingletonCachableModel
from user.models import User


class MatchConfiguration(SingletonCachableModel):
    simultaneous_game = models.BooleanField(default=False, verbose_name=_("Simultaneous availability"))

    def __str__(self):
        return "Match Configuration"

    class Meta:
        verbose_name = _("Match Configuration")
        verbose_name_plural = _("Match Configuration")


class PlayerMatchCheckout:

    def __init__(self, player, match_type):
        self.player = player
        self.match_type = match_type

    def _get_checkout_handler(self, result):
        win_lose_handlers = {
            "win": self._checkout_player_win,
            "lose": self._checkout_player_lose,
        }
        return win_lose_handlers.get(result, self._checkout_player_lose)

    def _grant_win_reward(self):
        self.player.shop_info.add_reward_package(self.match_type.winner_package)

    def _grant_lose_reward(self):
        self.player.shop_info.add_reward_package(self.match_type.lose_package)

    def _grant_win_xp(self):
        self.player.stats.add_xp(self.match_type.winner_xp)

    def _grant_lose_xp(self):
        self.player.stats.add_xp(self.match_type.lose_xp)

    def _grant_win_cup(self):
        self.player.stats.add_cup(self.match_type.winner_cup)

    def _grant_lose_cup(self):
        self.player.stats.add_cup(self.match_type.lose_cup)

    def _grant_win_score(self):
        self.player.stats.add_score(self.match_type.winner_score)

    def _grant_lose_score(self):
        self.player.stats.add_score(self.match_type.lose_score)

    def _checkout_player_win(self):
        self._grant_win_xp()
        self._grant_win_cup()
        self._grant_win_score()
        self._grant_win_reward()

    def _checkout_player_lose(self):
        self._grant_lose_xp()
        self._grant_lose_cup()
        self._grant_lose_score()
        self._grant_lose_reward()

    def check_out_player(self, result):
        checkout_handler = self._get_checkout_handler(result)
        checkout_handler()


class PlayerMatch:

    def __init__(self, player, match_type):
        self.player = player
        self.match_type = match_type
        self.errors = dict()
        self.payment_description = "Paid to enter match."

    def _is_player_blocked(self):
        block_reliefe_time: datetime.datetime = self.player.blocked()
        if block_reliefe_time:
            self.errors['block'] = f"Player is blocked for {block_reliefe_time.second}."

    def _simultaneous_game_check(self):
        sim_game_availability = MatchConfiguration.load().simultaneous_game
        if not sim_game_availability and self.player.is_in_game():
            self.errors["simultaneous_game"] = "Player is in another game."

    def _can_player_pay(self, entry_cost):
        has_credit = self.player.shop_info.has_enough_credit(currency=entry_cost.currency, amount=entry_cost.amount)
        if not has_credit:
            self.errors["funds"] = "Insufficient funds."

    def can_join(self) -> tuple[bool, dict]:
        self._simultaneous_game_check()
        self._is_player_blocked()
        match_entry_fee = self.match_type.entry_cost
        self._can_player_pay(match_entry_fee)
        can_join = len(self.errors.keys()) == 0
        return can_join, self.errors

    def pay_match_entry(self):
        can_join, errors = self.can_join()
        if not can_join:
            return False, errors
        match_entry_fee = self.match_type.entry_cost
        self.player.shop_info.pay(currency=match_entry_fee.currency, amount=match_entry_fee.amount,
                                  description=self.payment_description)
        return True, {}


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
                                       verbose_name=_("Winner package"), null=True, blank=True,
                                       related_name='match_winner')
    winner_xp = models.PositiveSmallIntegerField(verbose_name=_("Winner XP"), default=0)
    winner_cup = models.PositiveSmallIntegerField(verbose_name=_("Winner Cup"), default=0)
    winner_score = models.PositiveSmallIntegerField(verbose_name=_("Winner Score"), default=0)

    # Loser
    loser_package = models.ForeignKey(to='shop.RewardPackage', on_delete=models.SET_NULL,
                                      verbose_name=_("Loser package"), null=True, blank=True,
                                      related_name='match_loser')
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
    players = models.ManyToManyField(to='user.User', verbose_name=_("Players"), blank=True, related_name="games")
    match_type = models.ForeignKey(to=MatchType, on_delete=models.PROTECT, verbose_name=_("Match Type"),
                                   related_name="matches")

    def __str__(self):
        return f'{self.uuid} - {self.match_type}'

    @classmethod
    def start(cls, players, match_type: MatchType, match_uid):
        match_uuid = uuid.uuid4() if not match_uid else match_uid
        for player in players:
            match_type.pay_match_entry(player)
        return cls.objects.create(uuid=match_uuid, players=players, match_type=match_type)

    def check_out(self, player_data, player):
        player_checkout_manager = PlayerMatchCheckout(player, self.match_type)
        player_checkout_manager.check_out_player(player_data['result'])


    def finish(self, results):
        players_data = results["players"]
        for player_data in players_data:
            try:
                player = User.objects.get(id=player_data["id"])
            except User.DoesNotExist:
                continue
            self.check_out(player_data, player)
        self.create_results(results)

    def create_results(self, results):
        pass

    def archive_results(self):
        pass

    class Meta:
        verbose_name = _("Match")
        verbose_name_plural = _("Matches")
