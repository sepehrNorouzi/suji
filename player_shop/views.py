from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from exceptions.player_shop import DailyRewardEligibilityError, InvalidAvatarError
from player_shop.models import PlayerWallet, AssetOwnership, CurrencyBalance
from player_shop.serializers import PlayerWalletSerializer, AssetOwnerShipSerializer, CurrencyBalanceSerializer


class PlayerWalletViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    queryset = PlayerWallet.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = PlayerWalletSerializer

    def get_asset(self) -> AssetOwnership:
        lookup_url_kwarg = 'asset_ownership'
        assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
        )
        queryset = self.request.user.shop_info.asset_ownerships.all()
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        self.check_object_permissions(self.request, obj)
        return obj

    def get_asset_list(self) -> QuerySet[AssetOwnership]:
        asset_type = self.request.query_params.get('type')
        filter_expression = dict()
        if asset_type:
            filter_expression['asset__type'] = asset_type
        queryset = self.request.user.shop_info.asset_ownerships.filter(**filter_expression)
        return queryset

    def get_currency_list(self) -> QuerySet[CurrencyBalance]:
        currency_type = self.request.query_params.get('type')
        filter_expression = dict()
        if currency_type:
            filter_expression['currency__type'] = currency_type
        queryset = self.request.user.shop_info.currency_balances.filter(**filter_expression)
        return queryset

    def list(self, request, *args, **kwargs):
        user = self.request.user
        return Response(self.serializer_class(user.shop_info).data, status=status.HTTP_200_OK)

    @action(methods=['POST'], url_path='asset/(?P<asset_ownership>[0-9]+)/set_avatar', url_name='asset-set-avatar',
            detail=False)
    def set_avatar(self, request, *args, **kwargs):
        avatar = self.get_asset()
        try:
            shop_info = self.request.user.shop_info.set_avatar(avatar)
        except InvalidAvatarError as e:
            return Response(data={"error": _(str(e))}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(shop_info).data, status=status.HTTP_200_OK)

    @action(methods=['GET'], url_path='asset', url_name='asset',
            detail=False, serializer_class=AssetOwnerShipSerializer)
    def get_assets(self, request, *args, **kwargs):
        queryset = self.get_asset_list()
        return Response(self.get_serializer(queryset, many=True).data, status=status.HTTP_200_OK)

    @action(methods=['GET'], url_path='currency', url_name='currency',
            detail=False, serializer_class=CurrencyBalanceSerializer)
    def get_currencies(self, request, *args, **kwargs):
        queryset = self.get_currency_list()
        return Response(self.get_serializer(queryset, many=True).data, status=status.HTTP_200_OK)


class PlayerDailyRewardViewSet(viewsets.GenericViewSet, ):
    queryset = PlayerWallet.objects.filter(is_active=True)
    serializer_class = PlayerWalletSerializer
    permission_classes = [IsAuthenticated, ]

    @action(methods=['POST'], url_name="claim", url_path="claim", detail=False)
    def claim(self, request, *args, **kwargs):
        player = self.request.user
        player_wallet: PlayerWallet = PlayerWallet.objects.filter(player=player).first()
        if not player_wallet:
            raise RuntimeError(_("Player has no wallet."))
        try:
            player_wallet.claim_daily_reward()
            return Response(self.serializer_class(player_wallet).data, status=status.HTTP_200_OK)
        except DailyRewardEligibilityError as e:
            return Response(data={"error": _(str(e))}, status=status.HTTP_406_NOT_ACCEPTABLE)
