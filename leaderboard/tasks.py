from celery import shared_task

from leaderboard.models import LeaderboardType


@shared_task
def close_leaderboard_task(leaderboard_type_id: int):
    leaderboard_type = LeaderboardType.objects.get(pk=leaderboard_type_id)
    leaderboard_type.calculate_leaderboard()
    leaderboard_type.archive_leaderboard()
    leaderboard_type.renew_leaderboard()

