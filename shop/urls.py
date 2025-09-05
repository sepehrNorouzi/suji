from rest_framework.routers import DefaultRouter

from shop.views import ShopViewSet, MarketViewSet, LuckyWheelViewSet, DailyRewardViewSet

router = DefaultRouter()

router.register('shop', ShopViewSet, basename='shop')
router.register('market', MarketViewSet, basename='market')
router.register('daily_reward', DailyRewardViewSet, basename='daily-reward')
router.register('lucky_wheel', LuckyWheelViewSet, basename='lucky-wheel')
