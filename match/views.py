from rest_framework import mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from django.utils.translation import gettext_lazy as _

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
    game_server_actions = ['create_match', 'finish', ]
    client_actions = ['list', 'retrieve', 'me', ]

    def get_permissions(self):
        if self.action in self.game_server_actions:
            return [IsGameServer(), ]
        return [permissions.OR(IsGameServer(), IsAuthenticated())]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)
        return qs

    def get_current_player_match(self) -> Match:
        return Match.get_player_current_match(self.request.user)

    @action(methods=['POST'], detail=False, serializer_class=MatchCreateSerializer, url_name='create',
            url_path='create',)
    def create_match(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            match = serializer.create(serializer.validated_data)
        except MatchJoinError as e:
            return Response(e.args[0], status=status.HTTP_400_BAD_REQUEST)
        return Response(MatchSerializer(match).data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=True, serializer_class=MatchFinishSerializer, url_name='finish',
            url_path='finish')
    def finish(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        match = self.get_object()
        try:
            result = match.finish(serializer.validated_data)
            return Response(self.serializer_class({"result": result}).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print("EXCEPTION:", e)
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'], detail=False, serializer_class=MatchSerializer, url_path='me', url_name='me')
    def me(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        match = self.get_current_player_match()
        if not match:
            return Response(data={"detail": _("User has no active match"), "code": "no_active_match"},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(self.serializer_class(match).data)
