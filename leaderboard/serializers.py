from django.utils import timezone
from rest_framework import serializers

from leaderboard.models import LeaderboardType


class LeaderboardTypeSerializer(serializers.ModelSerializer):
    time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardType
        fields = ['id', 'name', 'duration', 'start_time', 'time_remaining']

    @staticmethod
    def get_time_remaining(obj):
        if obj.duration:
            return (obj.start_time + obj.duration) - timezone.now()
        return None
