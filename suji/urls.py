from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from common.urls import router as common_router
from user.urls import router as user_router
from shop.urls import router as shop_router
from player_shop.urls import router as player_shop_router
from social.urls import router as social_router
from player_statistic.urls import router as player_stats_router
from leaderboard.urls import router as leaderboard_router
from match.urls import router as match_router

router = DefaultRouter()

router.registry.extend(common_router.registry)
router.registry.extend(user_router.registry)
router.registry.extend(shop_router.registry)
router.registry.extend(player_shop_router.registry)
router.registry.extend(social_router.registry)
router.registry.extend(player_stats_router.registry)
router.registry.extend(leaderboard_router.registry)
router.registry.extend(match_router.registry)

urlpatterns = [
    path('', lambda request: redirect(to='admin/', permenant=True)),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]

