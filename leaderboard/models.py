import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_celery_beat.models import PeriodicTask, ClockedSchedule
from redis import Redis

from leaderboard.documents import LeaderboardDocument
from user.models import User


class LeaderboardRedis:
    TOP_PLAYER_COUNT_LIMIT = 1000

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    def renew_leaderboard(self, key):
        return self._redis.delete(key)

    def add_player(self, key, member, initial_score=0):
        return self._redis.zadd(key, mapping={
            member: initial_score
        })

    def increment_player_score(self, key, member, score):
        return self._redis.zincrby(key, score, member)

    def update_player_score(self, key, member, score):
        return self._redis.zadd(key, mapping={
            member: score
        }, xx=True)

    def get_top_players(self, key, limit=10):
        if limit > self.TOP_PLAYER_COUNT_LIMIT or limit <= 0:
            raise ValueError(_(f"Limit should be from 1 to {self.TOP_PLAYER_COUNT_LIMIT}"))
        return self._redis.zrevrange(key, start=0, end=limit, withscores=True)

    def get_player_rank(self, key, member):
        return self._redis.zrevrank(key, member, withscore=True)

    def get_surrounding_players(self, key, member, offset=5):
        player_rank = self.get_player_rank(key, member)[0]
        if not player_rank:
            return []
        return self._redis.zrevrange(key, start=max(0, player_rank - offset), end=player_rank + offset, withscores=True)

    def get_range(self, key, start, stop):
        return self._redis.zrevrange(key, start, stop)

    def get_leaderboard(self, key):
        count = self._redis.zcard(key)
        return self._redis.zrevrange(key, start=0, end=count, withscores=True)

    @classmethod
    def get_leaderboard_with_players(cls, leaderboard):
        player_score = {player_id: score for player_id, score in leaderboard}
        players = list(player_score.keys())
        player_details = []
        if players:
            player_details = settings.REDIS_CLIENT.hmget("USERS", players)
        results = []

        for index, (pid, detail) in enumerate(zip(players, player_details)):
            if detail:
                detail = json.loads(detail)
                detail['score'] = player_score[pid]
                detail['rank'] = index + 1
                results.append(detail)
        return results


class LeaderboardReward(models.Model):
    reward = models.ForeignKey(to="shop.RewardPackage", on_delete=models.CASCADE, verbose_name=_("Reward"))
    from_rank = models.IntegerField(default=1, verbose_name=_("From Rank"))
    to_rank = models.IntegerField(default=10, verbose_name=_("To Rank"))
    leaderboard_type = models.ForeignKey(to="leaderboard.LeaderboardType", on_delete=models.CASCADE,
                                         verbose_name=_("Leaderboard Type"), related_name="rewards")

    def save(self, *args, **kwargs):
        if self.from_rank > self.to_rank:
            raise ValidationError(_("'From rank' must be lower than 'to rank'"))
        super(LeaderboardReward, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_rank} - {self.to_rank}: {self.leaderboard_type}"

    class Meta:
        verbose_name = _("Leaderboard Reward")
        verbose_name_plural = _("Leaderboard Rewards")


class LeaderboardType(models.Model):
    name = models.CharField(verbose_name=_("Name"), max_length=100, unique=True)
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    duration = models.DurationField(default="1 00:00:00", verbose_name=_("Duration"), null=True, blank=True,
                                    help_text=_("If set to null, it means infinite."))
    start_time = models.DateTimeField(verbose_name=_("Start time"), )

    def __str__(self):
        return self.name

    @property
    def leaderboard_type_key(self):
        return f'LEADERBOARD:{self.name.replace(" ", "_").upper()}'

    @property
    def leaderboard_type_task_name(self):
        return f'LEADERBOARD {self.name.replace(" ", "_").upper()} closing task.'

    class Meta:
        verbose_name = _("Leaderboard Type")
        verbose_name_plural = _("Leaderboard Types")
        ordering = ("-duration", 'name')

    def archive_leaderboard(self):
        leaderboard_redis = LeaderboardRedis(settings.REDIS_CLIENT)
        archive_time = timezone.now()
        leaderboard_name = self.name
        leaderboard_key = self.leaderboard_type_key
        leaderboard = leaderboard_redis.get_leaderboard(leaderboard_key)
        leaderboard = LeaderboardRedis.get_leaderboard_with_players(leaderboard)
        data = {
            "archive_time": archive_time,
            "name": leaderboard_name,
            "key": leaderboard_key,
            "results": leaderboard,
        }
        document = LeaderboardDocument(**data)
        document.save()
        return document

    def create_task(self):
        if self.duration is None:
            return

        execute_at = self.start_time + self.duration
        task_name = self.leaderboard_type_key

        PeriodicTask.objects.filter(name=task_name).delete()

        clocked, _ = ClockedSchedule.objects.get_or_create(
            clocked_time=execute_at
        )

        PeriodicTask.objects.create(
            name=task_name,
            task='leaderboard.tasks.close_leaderboard_task',
            clocked=clocked,
            one_off=True,
            args=json.dumps([self.id]),
        )

    def calculate_leaderboard(self):
        self.is_active = False
        self.save()
        leaderboard_redis = LeaderboardRedis(settings.REDIS_CLIENT)
        rewards = self.rewards.all()

        for reward in rewards:
            from_rank = reward.from_rank
            to_rank = reward.to_rank
            players = leaderboard_redis.get_range(self.leaderboard_type_key, from_rank, to_rank)

            for player in players:
                try:
                    player_wallet = User.objects.get(pk=player).shop_info
                    player_wallet.add_reward_package(reward)
                except User.DoesNotExist:
                    continue

    def renew_leaderboard(self):
        leaderboard_redis = LeaderboardRedis(settings.REDIS_CLIENT)
        leaderboard_redis.renew_leaderboard(self.leaderboard_type_key)
        self.start_time = timezone.now()
        self.is_active = True
        self.save()

    def save(self, *args, **kwargs):
        if not self.pk:
            self.create_task()
        super(LeaderboardType, self).save(*args, **kwargs)

    def get_leaderboard(self, player_id):
        leaderboard_redis = LeaderboardRedis(settings.REDIS_CLIENT)
        leaderboard_key = self.leaderboard_type_key
        top_players = leaderboard_redis.get_top_players(leaderboard_key, limit=100)
        player_rank = leaderboard_redis.get_player_rank(leaderboard_key, player_id)
        surrounding_players = leaderboard_redis.get_surrounding_players(leaderboard_key, player_id)
        top_players = LeaderboardRedis.get_leaderboard_with_players(top_players)
        surrounding_players = LeaderboardRedis.get_leaderboard_with_players(surrounding_players)
        return top_players, surrounding_players, player_rank


class Leaderboard(models.Model):
    player = models.ForeignKey(to="user.User", on_delete=models.CASCADE, verbose_name=_("Player"),
                               related_name='leaderboard')
    score = models.PositiveIntegerField(default=0, verbose_name=_("Score"), editable=False)

    def add_score(self, score):
        self.score += score
        self.save()
        types = LeaderboardType.objects.filter(is_active=True, start_time__lte=timezone.now())
        leaderboard_redis = LeaderboardRedis(settings.REDIS_CLIENT)
        for t in types:
            leaderboard_redis.increment_player_score(t.leaderboard_type_key, self.player.id, score)

    def __str__(self):
        return f'{self.player} - {self.score}'

    @classmethod
    def get_player_leaderboard(cls, player):
        ldb = cls.objects.filter(player=player).first()
        if not ldb:
            return cls.objects.create(player=player)
        return ldb
