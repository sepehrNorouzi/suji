from rest_framework.routers import DefaultRouter

from player_shop.views import PlayerWalletViewSet, PlayerDailyRewardViewSet

router = DefaultRouter()

router.register('player_shop/wallet', PlayerWalletViewSet, basename='wallet')
router.register('player_shop/daily_reward', PlayerDailyRewardViewSet, basename='daily-reward')
