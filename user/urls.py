from user.views import NormalPlayerAuthView, GuestPlayerAuthView, PlayerProfileView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register('user/auth/player', NormalPlayerAuthView, basename='auth-player')
router.register('user/auth/guest', GuestPlayerAuthView, basename='auth-guest')
router.register('user/profile', PlayerProfileView, basename='user-profile')
