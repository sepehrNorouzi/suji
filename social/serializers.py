from rest_framework import serializers

from social.models import FriendshipRequest, Friendship
from user.serializers import PlayerProfileSerializer


class FriendshipRequestSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    sender = serializers.SerializerMethodField()
    receiver_id = serializers.IntegerField(write_only=True, required=True)
    created_time = serializers.DateTimeField(read_only=True)

    class Meta:
        model = FriendshipRequest
        fields = ['id', 'sender', 'receiver_id', 'created_time']

    @staticmethod
    def get_sender(obj):
        return PlayerProfileSerializer(obj.sender.player).data

    def create(self, validated_data):
        return FriendshipRequest.create(
            sender_id=self.context['sender_id'],
            receiver_id=validated_data['receiver_id']
        )


class RequestedFriendshipSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    receiver = serializers.SerializerMethodField()

    class Meta:
        model = FriendshipRequest
        fields = ['id', 'receiver', 'created_time', ]

    @staticmethod
    def get_receiver(obj):
        return PlayerProfileSerializer(obj.receiver.player).data


class FriendshipSerializer(serializers.ModelSerializer):
    user_1 = serializers.SerializerMethodField()
    user_2 = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ['id', 'user_1', 'user_2', 'created_time', ]

    @staticmethod
    def get_user_1(obj):
        return PlayerProfileSerializer(obj.user_1.player).data

    @staticmethod
    def get_user_2(obj):
        return PlayerProfileSerializer(obj.user_2.player).data
