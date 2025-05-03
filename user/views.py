from django.db import IntegrityError
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from user.models import NormalPlayer, GuestPlayer, User, SupporterPlayerInfo
from user.permissions import IsGuestPlayer
from user.serializers import NormalPlayerSignUpSerializer, NormalPlayerVerifySerializer, NormalPlayerSignInSerializer, \
    GuestPlayerSignUpSerializer, GuestPlayerSignInSerializer, GuestPlayerRecoverySerializer, \
    NormalPlayerForgetPasswordRequestSerializer, NormalPlayerResetPasswordSerializer, PlayerProfileSerializer, \
    SupporterPlayerSerializer, SupporterPanelUseSerializer, SupporterRetrieveSerializer, \
    PlayerProfileSelfRetrieveSerializer
from utils.random_functions import generate_random_string


class NormalPlayerAuthView(viewsets.GenericViewSet):
    queryset = NormalPlayer.objects.filter(is_active=True)

    @action(methods=['POST'], detail=False, url_path="signup", url_name="signup",
            serializer_class=NormalPlayerSignUpSerializer)
    def player_signup(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError as e:
            return Response({'error': _("User already exists.")}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data={"message": _(f"OTP is sent to {user.email}."), "user": self.serializer_class(user).data},
                        status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=False, url_path="signup/verify", url_name="signup-verify",
            serializer_class=NormalPlayerVerifySerializer)
    def player_email_verify(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user: QuerySet = NormalPlayer.objects.filter(email=data['email'])
        if not user.exists():
            return Response({'error': _("Invalid email.")}, status=status.HTTP_400_BAD_REQUEST)
        user: NormalPlayer = user.first()
        verified = user.verify_email(otp=data["otp"])
        if verified:
            return Response(data={'user': self.serializer_class(user).data, "message": _("Verified successfully")},
                            status=status.HTTP_200_OK)
        return Response(data={'error': _('Invalid OTP.')}, status=status.HTTP_406_NOT_ACCEPTABLE)

    @action(methods=['POST'], detail=False, url_path="login", url_name="login",
            serializer_class=NormalPlayerSignInSerializer)
    def player_signin(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user, token, errors = NormalPlayer.attempt_login(email=data["email"], password=data["password"])
        if errors:
            return Response(data={'error': errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={'credentials': token, 'user': self.serializer_class(user).data},
                        status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path="recovery/request", url_name="recovery-request",
            serializer_class=NormalPlayerForgetPasswordRequestSerializer)
    def player_forget_password_request(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        deep_link = data['deep_link']
        email = data["email"]
        try:
            success = NormalPlayer.attempt_password_recovery(email=email, deep_link=deep_link)
        except NormalPlayer.DoesNotExist:
            return Response(data={"error": _("No player with this email is found.")}, status=status.HTTP_404_NOT_FOUND)
        if not success:
            return Response(data={'error': _("Cool down is not over.")}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        return Response(data={'message': _('Password reset link is sent.')}, status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path="recovery/verify", url_name="recovery-verify",
            serializer_class=NormalPlayerResetPasswordSerializer)
    def player_reset_password_verify(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        token = data['token']
        new_password = data['new_password']
        email = data['email']
        success = NormalPlayer.reset_password(email=email, token=token, new_password=new_password)
        if not success:
            return Response(data={'error': _('Invalid token.')}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={'message': _("Password reset successfully.")}, status=status.HTTP_200_OK)


class GuestPlayerAuthView(viewsets.GenericViewSet):
    queryset = GuestPlayer.objects.filter(is_active=True)

    @action(methods=['POST'], detail=False, url_path="signup", url_name="signup",
            serializer_class=GuestPlayerSignUpSerializer)
    def guest_signup(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = generate_random_string(length=10)
        try:
            user = serializer.save(password=password)
        except IntegrityError as e:
            return Response({'error': _("User already exists.")}, status=status.HTTP_400_BAD_REQUEST)
        data = {**self.serializer_class(user).data, "password": password}
        return Response(data=data, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=False, url_path="login", url_name="login",
            serializer_class=GuestPlayerSignInSerializer)
    def guest_signin(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user, token, errors = GuestPlayer.attempt_login(device_id=data["device_id"], password=data["password"])
        if errors:
            return Response(data={'error': errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={'credentials': token, 'user': self.serializer_class(user).data},
                        status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path="recovery", url_name="recovery",
            serializer_class=GuestPlayerRecoverySerializer)
    def guest_recovery(self, request, *args, **kwargs):
        # Will change
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        password = generate_random_string(length=10)
        user, token, errors = GuestPlayer.attempt_recovery(device_id=data["device_id"],
                                                           recovery_string=data["recovery_string"],
                                                           new_password=password)
        if errors:
            return Response(data={'error': errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={'credentials': token, 'user': {**self.serializer_class(user).data, 'password': password}},
                        status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path='convert', url_name='convert', permission_classes=[IsGuestPlayer])
    def guest_convert(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exceptions=True)
        data = serializer.validated_data
        player: GuestPlayer = self.request.user.player
        email = data['email']
        password = data['password']
        profile_name = data.get("profile_name")
        normal_player: NormalPlayer = player.convert_to_normal_player(email=email, password=password,
                                                                      profile_name=profile_name)
        return Response(data=NormalPlayerSignUpSerializer(normal_player).data, status=status.HTTP_201_CREATED)


class PlayerProfileView(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = User.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, ]
    serializer_class = PlayerProfileSerializer

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        user = get_object_or_404(User, pk=self.kwargs[lookup_url_kwarg])
        return user

    def list(self, request, *args, **kwargs):
        player = self.request.user
        serializer = PlayerProfileSelfRetrieveSerializer(player)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path='supports', url_name='supports',
            serializer_class=SupporterRetrieveSerializer)
    def self_support_package(self, request, *args, **kwargs):
        user = self.request.user
        packages = user.supports.filter(is_active=True)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(packages, request)
        return paginator.get_paginated_response(self.serializer_class(page, many=True).data)

    @action(methods=['GET'], detail=True, url_path='supports', url_name='supports',
            serializer_class=SupporterRetrieveSerializer)
    def player_support_package(self, request, *args, **kwargs):
        player = self.get_object()
        packages = player.supports.filter(visible=True, approved=True, is_active=True, used=True)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(packages, request)
        return paginator.get_paginated_response(self.serializer_class(page, many=True).data)


class SupporterPlayerView(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = SupporterPlayerInfo.objects.filter(is_active=True, approved=True, visible=True)
    serializer_class = SupporterPlayerSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return SupporterPlayerInfo.objects.filter(is_active=True, approved=True, visible=True).order_by(
            "-approval_date")

    def get_usable_object(self) -> SupporterPlayerInfo:
        queryset = SupporterPlayerInfo.objects.filter(player=self.request.user, used=False)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        return obj

    @action(methods=['POST'], detail=True, url_name='use', url_path='use', serializer_class=SupporterPanelUseSerializer)
    def use(self, request, *args, **kwargs):
        usable_object: SupporterPlayerInfo = self.get_usable_object()
        serializer = self.serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        usable_object.use(data={**serializer.validated_data})
        usable_object.refresh_from_db()
        return Response(data=SupporterPlayerSerializer(usable_object).data, status=status.HTTP_202_ACCEPTED)
