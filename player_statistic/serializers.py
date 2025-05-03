from rest_framework import serializers

from player_statistic.models import PlayerStatistic, PlayerLevel
from shop.serializers import RewardPackageSerializer
from user.serializers import PlayerProfileSerializer


class PlayerLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerLevel
        fields = ['id', 'start_xp', 'index', ]


class PlayerLevelWithRewardSerializer(serializers.ModelSerializer):

    reward = RewardPackageSerializer()

    class Meta:
        model = PlayerLevel
        fields = ['id', 'start_xp', 'index', 'reward']


class PlayerStatisticSerializer(serializers.ModelSerializer):
    level = PlayerLevelSerializer()
    player = PlayerProfileSerializer(read_only=True)

    class Meta:
        model = PlayerStatistic
        fields = ['id', 'xp', 'score', 'cup', 'level', 'player']
