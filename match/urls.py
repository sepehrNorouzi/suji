from rest_framework.routers import DefaultRouter

from match.views import MatchTypeViewSet, MatchViewSet, MatchmakingViewSet

router = DefaultRouter()

router.register('match_type', MatchTypeViewSet, basename='match_type')
router.register('match', MatchViewSet, basename='match')
router.register('matchmaking', MatchmakingViewSet, basename='matchmaking')
