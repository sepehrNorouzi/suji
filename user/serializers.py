from rest_framework import serializers

from user.models import NormalPlayer, GuestPlayer, VipPlayer, SupporterPlayerInfo, Player


class NormalPlayerSignUpSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = NormalPlayer
        fields = ['email', 'password', 'profile_name', 'gender', 'birth_date', 'first_name', 'last_name', ]

    def create(self, validated_data):
        data = validated_data
        email = data['email']
        password = data['password']
        del data['email']
        del data['password']
        return NormalPlayer.create(email=email, password=password, **data)


class NormalPlayerVerifySerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(write_only=True, required=True)
    profile_name = serializers.CharField(read_only=True)
    gender = serializers.CharField(read_only=True)
    birth_date = serializers.DateField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    credentials = serializers.SerializerMethodField()

    class Meta:
        model = NormalPlayer
        fields = ['email', 'profile_name', 'gender', 'birth_date', 'first_name', 'last_name', 'credentials', 'otp', ]

    def get_credentials(self, obj: NormalPlayer):
        return obj.get_token()


class VipSerializer(serializers.ModelSerializer):
    class Meta:
        model = VipPlayer
        fields = ['expiration_date', 'id']


class NormalPlayerSignInSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    vip = serializers.SerializerMethodField()

    class Meta:
        model = NormalPlayer
        fields = ['email', 'profile_name', 'gender', 'birth_date', 'first_name', 'last_name', 'password', 'vip', ]

    @staticmethod
    def get_vip(obj: NormalPlayer):
        vip = obj.vip.first()
        if vip and not vip.is_expired():
            return VipSerializer(vip).data
        return None


class NormalPlayerForgetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    deep_link = serializers.CharField(default='')


class NormalPlayerResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    new_password = serializers.CharField(required=True)
    token = serializers.CharField(required=True)


class GuestPlayerSignUpSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(required=True)
    credentials = serializers.SerializerMethodField()

    class Meta:
        model = GuestPlayer
        fields = ['device_id', 'recovery_string', 'profile_name', 'gender', 'birth_date', 'first_name', 'last_name',
                  'credentials']

    def create(self, validated_data):
        data = validated_data
        device_id = data['device_id']
        password = data['password']
        del data['password']
        del data['device_id']
        return GuestPlayer.create(device_id=device_id, password=password, **data)

    def get_credentials(self, obj: GuestPlayer):
        return obj.get_token()


class GuestPlayerSignInSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    device_id = serializers.CharField(required=True)

    class Meta:
        model = GuestPlayer
        fields = ['device_id', 'profile_name', 'gender', 'birth_date', 'first_name', 'last_name', 'password',
                  'recovery_string']


class GuestPlayerRecoverySerializer(serializers.ModelSerializer):
    recovery_string = serializers.CharField(write_only=True, required=True)
    device_id = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = GuestPlayer
        fields = ['device_id', 'profile_name', 'gender', 'birth_date', 'first_name', 'last_name',
                  'recovery_string', 'password', ]


class PlayerAvatarSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    config = serializers.JSONField(read_only=True)


class PlayerProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    profile_name = serializers.CharField(read_only=True)
    gender = serializers.CharField(read_only=True)
    birth_date = serializers.DateField(read_only=True)
    vip = serializers.SerializerMethodField()
    current_avatar = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def get_current_avatar(obj):
        current = obj.current_avatar
        return PlayerAvatarSerializer(obj.current_avatar).data if current else None

    @staticmethod
    def get_vip(obj):
        vip = obj.vip.first()
        if vip:
            return not vip.is_expired()
        return False


class PlayerProfileSelfRetrieveSerializer(PlayerProfileSerializer):
    daily_reward_streak = serializers.IntegerField(read_only=True)
    last_claimed = serializers.DateTimeField(read_only=True)
    last_lucky_wheel_spin = serializers.DateTimeField(read_only=True)
    inviter = serializers.CharField(read_only=True)
    invites_count = serializers.SerializerMethodField()

    @staticmethod
    def get_invites_count(obj: Player):
        return obj.invite_count()


class SupporterPlayerSerializer(serializers.ModelSerializer):
    player = PlayerProfileSerializer()

    class Meta:
        model = SupporterPlayerInfo
        exclude = ['created_time', 'is_active', 'updated_time']


class SupporterRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupporterPlayerInfo
        fields = ['reason', 'message', 'instagram_link', 'telegram_link', 'rubika_link', 'id']


class SupporterPanelUseSerializer(serializers.Serializer):
    message = serializers.CharField(required=False)
    instagram_link = serializers.CharField(required=False)
    telegram_link = serializers.CharField(required=False)
    website_link = serializers.CharField(required=False)
    visible = serializers.BooleanField(default=False)


class PlayerCacheSerializer(PlayerProfileSerializer):
    pass
