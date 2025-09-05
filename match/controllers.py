from django.utils.translation import gettext_lazy as _

class PlayerMatchCheckout:

    def __init__(self, player, match_type):
        self.player = player
        self.match_type = match_type

    @staticmethod
    def create_stat_log_json(xp, score, cup, reward):
        return {
            "xp": xp,
            "score": score,
            "cup": cup,
            "reward": reward,
        }

    def _get_checkout_handler(self, result):
        win_lose_handlers = {
            "win": self._checkout_player_win,
            "lose": self._checkout_player_lose,
        }
        return win_lose_handlers.get(result, self._checkout_player_lose)

    def _grant_win_reward(self):
        added_reward = self.match_type.winner_package
        if added_reward:
            self.player.shop_info.add_reward_package(added_reward, "winning match")
            return added_reward.id
        return None

    def _grant_lose_reward(self):
        added_reward = self.match_type.loser_package
        if added_reward:
            self.player.shop_info.add_reward_package(added_reward, "losing match")
            return added_reward.id
        return None

    def _grant_win_xp(self):
        added_xp = self.match_type.winner_xp
        self.player.stats.add_xp(added_xp)
        return added_xp

    def _grant_lose_xp(self):
        added_xp = self.match_type.loser_xp
        self.player.stats.add_xp(added_xp)
        return added_xp

    def _grant_win_cup(self):
        added_cup = self.match_type.winner_cup
        self.player.stats.add_cup(added_cup)
        return added_cup

    def _grant_lose_cup(self):
        added_cup = self.match_type.loser_cup
        self.player.stats.add_cup(added_cup)
        return added_cup

    def _grant_win_score(self):
        added_score = self.match_type.winner_score
        self.player.stats.add_score(self.match_type.winner_score)
        return added_score

    def _grant_lose_score(self):
        added_score = self.match_type.loser_score
        self.player.stats.add_score(self.match_type.loser_score)
        return added_score

    def _checkout_player_win(self):
        xp = self._grant_win_xp()
        cup = self._grant_win_cup()
        score = self._grant_win_score()
        reward = self._grant_win_reward()
        return self.create_stat_log_json(xp, score, cup, reward)

    def _checkout_player_lose(self):
        xp = self._grant_lose_xp()
        cup = self._grant_lose_cup()
        score = self._grant_lose_score()
        reward = self._grant_lose_reward()
        return self.create_stat_log_json(xp, score, cup, reward)

    def check_out_player(self, result):
        checkout_handler = self._get_checkout_handler(result)
        return checkout_handler()


class PlayerMatch:
    def __init__(self, player, match_type, config):
        self.player = player
        self.match_type = match_type
        self.config = config
        self.errors = dict()

    def _is_player_blocked(self):
        blocked = self.player.blocked() is not None
        if blocked:
            self.errors['block'] = _("Player is blocked for {delta} seconds").format(delta=blocked)

    def _simultaneous_game_check(self):
        sim_game = self.config.simultaneous_game
        if not sim_game and self.player.is_in_match():
            self.errors['simultaneous_game'] = _("Player is in another match.")

    def _can_player_pay(self):
        entry_cost = self.match_type.entry_cost
        if entry_cost:
            currency = entry_cost.currency
            amount = entry_cost.amount
            has_credit = self.player.shop_info.has_enough_credit(currency=currency, amount=amount)
            if not has_credit:
                self.errors["payment"] = _("Insufficient {currency} to pay").format(currency=currency)

    def can_join(self) -> tuple[bool, dict]:
        self._simultaneous_game_check()
        self._is_player_blocked()
        self._can_player_pay()
        can_join = len(self.errors.keys()) == 0
        return can_join, self.errors

    def pay_match_entry(self):
        entry_cost = self.match_type.entry_cost
        if entry_cost:
            currency = entry_cost.currency
            amount = entry_cost.amount
            desc = f"Paid {entry_cost} to join match."
            self.player.shop_info.pay(currency=currency, amount=amount, description=desc)
