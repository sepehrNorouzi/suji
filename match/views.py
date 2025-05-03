from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from match.models import MatchType
from match.serializers import MatchTypeSerializer


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
