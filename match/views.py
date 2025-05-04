from rest_framework import permissions
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from match.exceptions import MatchJoinError
from match.models import MatchType, Match
from match.permissions import IsGameServer
from match.serializers import MatchTypeSerializer, MatchSerializer, MatchCreateSerializer, MatchFinishSerializer


class MatchTypeViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = MatchTypeSerializer
    queryset = MatchType.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, ]

    @action(methods=['GET'], detail=True, url_path='can_join', url_name='can-join')
    def can_join(self, request, *args, **kwargs):
        obj: MatchType = self.get_object()
        can_join, errors = obj.can_join(request.user)
        if not can_join:
            return Response({"errors": errors}, status=status.HTTP_403_FORBIDDEN)

        return Response(status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path='get_by_name', url_name='get-by-name',
            permission_classes=[IsGameServer | IsAuthenticated, ])
    def get_by_name(self, request, *args, **kwargs):
        name = self.request.query_params.get('name', '')
        obj = get_object_or_404(self.get_queryset(), name=name)
        return Response(MatchTypeSerializer(obj).data)


class MatchViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = MatchSerializer
    queryset = Match.objects.filter(is_active=True)
    lookup_field = 'uuid'
    permission_classes = [IsAuthenticated | IsGameServer]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(players=self.request.user)
        return qs

    @action(methods=['POST'], detail=False, serializer_class=MatchCreateSerializer, url_name='create',
            url_path='create',
            permission_classes=[IsGameServer])
    def create_match(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            match = self.serializer_class().create(serializer.validated_data)
        except MatchJoinError as e:
            return Response(e.args[0], status=status.HTTP_400_BAD_REQUEST)
        return Response(MatchSerializer(match).data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=True, serializer_class=MatchFinishSerializer, url_name='finish',
            url_path='finish')
    def finish(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        match: Match = get_object_or_404(Match.objects.all(), **filter_kwargs)
        try:
            match.finish(serializer.validated_data)
            return Response(status=status.HTTP_200_OK)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)



