from rest_framework.routers import DefaultRouter

from shop.views import ShopViewSet, MarketViewSet, LuckyWheelViewSet

router = DefaultRouter()

router.register('shop', ShopViewSet, basename='shop')
router.register('market', MarketViewSet, basename='market')
router.register('lucky_wheel', LuckyWheelViewSet, basename='lucky_wheel')
