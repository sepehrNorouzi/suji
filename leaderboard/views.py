from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from leaderboard.models import LeaderboardType
from leaderboard.serializers import LeaderboardTypeSerializer


class LeaderboardTypeViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = LeaderboardType.objects.filter(is_active=True)
    serializer_class = LeaderboardTypeSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        leaderboard_type: LeaderboardType = self.get_object()
        serializer = self.get_serializer(leaderboard_type)
        try:
            top_players, surrounding_players, player_rank = leaderboard_type.get_leaderboard(self.request.user.id)
        except Exception as e:
            return Response({"detail": _("Service temporary down.")}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        leaderboard_data = {
            "top_players": top_players,
            "surrounding_players": surrounding_players,
            "player_rank": {
                "rank": player_rank[0],
                "score": int(player_rank[1])
            }
        }
        return Response({**serializer.data, **leaderboard_data}, status=status.HTTP_200_OK)
