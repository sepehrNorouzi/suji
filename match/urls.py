from rest_framework.routers import DefaultRouter

from match.views import MatchTypeViewSet, MatchViewSet

router = DefaultRouter()

router.register('match_type', MatchTypeViewSet, basename='match_type')
router.register('match', MatchViewSet, basename='match')

