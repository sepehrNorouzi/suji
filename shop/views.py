from django.db.models import Q
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from exceptions.player_shop import LuckyWheelCoolDownError
from exceptions.shop import WrongShopFlowError, NotEnoughCreditError, EmptyLuckyWheelError
from shop.models import Market, ShopPackage, ShopSection, DailyRewardPackage, LuckyWheel
from shop.serializers import ShopPackageSerializer, ShopSectionSerializer, MarketSerializer, \
    DailyRewardPackageSerializer, LuckyWheelRetrieveSerializer, RewardPackageSerializer


class MarketViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Market.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, ]
    pagination_class = PageNumberPagination
    serializer_class = MarketSerializer


class ShopViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = ShopPackage.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, ]
    pagination_class = PageNumberPagination
    serializer_class = ShopPackageSerializer
    view_cache_timeout = 60 * 60

    def get_queryset(self):
        qs = super(ShopViewSet, self).get_queryset()
        market = self.request.user.shop_info.player_market
        qs = qs.filter(Q(markets__in=[market]) | Q(markets__isnull=True))
        return qs

    def get_object(self):
        obj: ShopPackage = super(ShopViewSet, self).get_object()
        if obj.markets.count() == 0:
            return obj
        market = self.request.user.shop_info.player_market
        is_in_market = obj.markets.filter(id=market.id).exists()
        if not is_in_market:
            raise Http404
        return obj

    @method_decorator(cache_page(view_cache_timeout, key_prefix='SHOP_PACKAGE_CACHE'))
    def list(self, request, *args, **kwargs):
        section = self.request.query_params.get('section', None)
        qs = self.get_queryset()
        if section and isinstance(section, int):
            qs = qs.filter(section_id=int(section))
        pagination = self.paginate_queryset(qs)
        serializer = self.get_serializer(pagination, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

    @method_decorator(cache_page(view_cache_timeout, key_prefix='SHOP_SECTION_CACHE'))
    @action(methods=['GET'], url_path='section', url_name='section', detail=False,
            serializer_class=ShopSectionSerializer)
    def sections(self, request, *args, **kwargs):
        sections = ShopSection.objects.filter(is_active=True)
        return Response(data=self.serializer_class(sections, many=True).data, status=status.HTTP_200_OK)

    @action(methods=['POST'], url_path='purchase', url_name='purchase', detail=True, )
    def purchase(self, request, *args, **kwargs):
        package = self.get_object()
        player_shop_info = self.request.user.shop_info
        try:
            player_shop_info.buy_package(package)
        except WrongShopFlowError as e:
            return Response({'error': str(e), "success": False}, status=status.HTTP_409_CONFLICT)
        except NotEnoughCreditError as e:
            return Response({'error': str(e), "success": False}, status=status.HTTP_402_PAYMENT_REQUIRED)
        return Response(data={"success": True}, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], url_path='verify', url_name='verify', detail=False)
    def verify(self, request, *args, **kwargs):
        pass


class DailyRewardViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = DailyRewardPackage.objects.filter(is_active=True)
    serializer_class = DailyRewardPackageSerializer
    permission_classes = [IsAuthenticated, ]
    pagination_class = PageNumberPagination


class LuckyWheelViewSet(GenericViewSet, mixins.ListModelMixin):
    queryset = LuckyWheel.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, ]
    serializer_class = LuckyWheelRetrieveSerializer

    def list(self, request, *args, **kwargs):
        wheel = LuckyWheel.load().first()
        return Response(self.serializer_class(wheel).data, status=status.HTTP_200_OK)

    @action(methods=['POST'], url_path='spin', url_name='spin', detail=True)
    def spin(self, request, *args, **kwargs):
        player_wallet = self.request.user.shop_info
        wheel = self.get_object()
        try:
            reward = player_wallet.spin_lucky_wheel(wheel)
            return Response(RewardPackageSerializer(reward).data, status=status.HTTP_200_OK)
        except LuckyWheelCoolDownError as e:
            return Response(data={"error": _(str(e))}, status=status.HTTP_425_TOO_EARLY)
        except EmptyLuckyWheelError as e:
            return Response(data={"error": _(str(e))}, status=status.HTTP_400_BAD_REQUEST)
