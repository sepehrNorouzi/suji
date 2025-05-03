from django.utils import timezone
from rest_framework import serializers

from common.models import Configuration


class CommonConfigurationSerializer(serializers.ModelSerializer):
    server_time = serializers.SerializerMethodField()

    class Meta:
        model = Configuration
        fields = ['id', 'app_name', 'game_package_name', 'app_version', 'app_version_bundle', 'last_bundle_version',
                  'minimum_supported_bundle_version', 'maintenance_mode', 'server_time', ]

    @staticmethod
    def get_server_time(obj):
        return timezone.now().timestamp()
