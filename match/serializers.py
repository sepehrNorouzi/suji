from django.db.models import QuerySet
from rest_framework import serializers
from uuid import uuid4

from rest_framework.exceptions import ValidationError

from match.models import MatchType, Match, MatchResult
from shop.serializers import CostSerializer, RewardPackageSerializer
from user.models import User
from user.serializers import PlayerProfileSerializer


class MatchTypeSerializer(serializers.ModelSerializer):
    entry_cost = CostSerializer()
    winner_package = RewardPackageSerializer()
    loser_package = RewardPackageSerializer()

    class Meta:
        model = MatchType
        exclude = ['priority', 'is_active', 'updated_time', 'created_time']

class MatchTypeCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchType
        fields = ['id', 'name',]

class MatchSerializer(serializers.ModelSerializer):
    match_type = MatchTypeCompactSerializer()
    players = PlayerProfileSerializer(many=True)

    class Meta:
        model = Match
        fields = ['uuid', 'players', 'match_type']

class MatchCreateSerializer(serializers.Serializer):
    players = serializers.ListField(child=serializers.IntegerField())
    match_type = serializers.IntegerField()
    uuid = serializers.UUIDField(default=uuid4)

    def validate_players(self, data):
        players = User.objects.filter(id__in=data)
        criteria = players.count() == len(data)
        if not criteria:
            raise ValidationError('Player is invalid')
        return User.objects.filter(id__in=data)

    def validate_match_type(self, data):
        match_type = MatchType.objects.filter(id=data)
        criteria = match_type.exists()
        if not criteria:
            raise ValidationError('Match type is invalid.')
        return match_type.first()

    def create(self, validated_data):
        match_uuid: str = validated_data['uuid'].__str__()
        match_type: MatchType = validated_data['match_type']
        players: QuerySet[User] = validated_data['players']
        match = Match.start(players=players, match_type=match_type, match_uuid=match_uuid)
        return match

class PlayerMatchFinish(serializers.Serializer):
    id = serializers.IntegerField()
    result = serializers.CharField()

class MatchResultSerializer(serializers.ModelSerializer):
    players = PlayerProfileSerializer(many=True)

    class Meta:
        model = MatchResult
        fields = ['id', 'match_uuid', 'match_type', 'history', 'players', ]


class MatchFinishSerializer(serializers.Serializer):
    players = PlayerMatchFinish(many=True, write_only=True)
    end_time = serializers.IntegerField(write_only=True)
    winner = serializers.IntegerField(write_only=True)
    result = MatchResultSerializer(read_only=True)


class MatchmakingJoinSerializer(serializers.Serializer):
    match_type_id = serializers.IntegerField()
    search_fields = serializers.JSONField(default=dict, required=False)
    
    def validate_match_type_id(self, value):
        from .models import MatchType
        try:
            match_type = MatchType.objects.get(id=value, is_active=True)
            return value
        except MatchType.DoesNotExist:
            raise serializers.ValidationError("Invalid match type")
