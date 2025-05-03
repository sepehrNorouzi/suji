from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from common.models import Configuration
from common.serializers import CommonConfigurationSerializer


class ConfigurationViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Configuration.objects.filter(is_active=True)
    serializer_class = CommonConfigurationSerializer

    def list(self, *args, **kwargs):
        return Response(data=self.get_serializer(Configuration.load()).data, status=status.HTTP_200_OK)
