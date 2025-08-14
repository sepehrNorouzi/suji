from django.db.models.signals import post_save
from django.dispatch import receiver

from player_statistic.models import PlayerStatistic
from user.models import NormalPlayer, GuestPlayer


def user_stat_init(instance, created):
    if created:
        PlayerStatistic.objects.get_or_create(player=instance)


@receiver(signal=post_save, sender=NormalPlayer)
def player_stats_init(sender, instance, created, **kwargs):
    user_stat_init(instance, created)


@receiver(signal=post_save, sender=GuestPlayer)
def guest_player_stats_init(sender, instance, created, **kwargs):
    user_stat_init(instance, created)
