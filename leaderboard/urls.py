from rest_framework.routers import DefaultRouter

from leaderboard.views import LeaderboardTypeViewSet

router = DefaultRouter()

router.register("leaderboard", LeaderboardTypeViewSet, basename="leaderboard")
