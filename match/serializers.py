from django.db.models import QuerySet
from rest_framework import serializers
from uuid import uuid4

from rest_framework.exceptions import ValidationError

from match.models import MatchType, Match
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

    def validate(self, attrs):
        return super().validate(attrs)

    def create(self, validated_data):
        match_uuid: str = validated_data['uuid']
        match_type: MatchType = validated_data['match_type']
        players: QuerySet[User] = validated_data['players']
        match: Match = Match.objects.create(uuid=match_uuid, match_type=match_type)

        for player in players:
            match_type.pay_match_entry(player)

        match.players.add(*players)
        return match

class MatchFinishSerializer(serializers.Serializer):
    pass