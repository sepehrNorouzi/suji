from rest_framework import serializers

from match.models import MatchType
from shop.serializers import CostSerializer, RewardPackageSerializer


class MatchTypeSerializer(serializers.ModelSerializer):
    entry_cost = CostSerializer()
    winner_package = RewardPackageSerializer()
    loser_package = RewardPackageSerializer()

    class Meta:
        model = MatchType
        exclude = ['priority', 'is_active', 'updated_time', 'created_time']
