from rest_framework.routers import DefaultRouter

from player_statistic.views import PlayerStatisticViewSet, PlayerLevelViewSet

router = DefaultRouter()

router.register('player_statistic', PlayerStatisticViewSet, basename='player-statistic')
router.register('player_level', PlayerLevelViewSet, basename='player-level')
