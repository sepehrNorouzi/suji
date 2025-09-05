from django.shortcuts import get_object_or_404
from rest_framework import viewsets, mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from player_statistic.models import PlayerStatistic, PlayerLevel
from player_statistic.serializers import PlayerStatisticSerializer, PlayerLevelWithRewardSerializer


class PlayerLevelViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, ):
    queryset = PlayerLevel.objects.filter(is_active=True)
    serializer_class = PlayerLevelWithRewardSerializer
    pagination_class = PageNumberPagination
    permission_classes = [IsAuthenticated, ]



class PlayerStatisticViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, ):
    queryset = PlayerStatistic.objects.all()
    serializer_class = PlayerStatisticSerializer
    permission_classes = [IsAuthenticated, ]

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {"player_id": self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(self.get_queryset(), **filter_kwargs)
        return obj

    def list(self, request, *args, **kwargs):
        obj = PlayerStatistic.objects.filter(player_id=self.request.user.id).first()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
