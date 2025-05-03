from rest_framework.routers import DefaultRouter

from social.views import FriendshipRequestViewSet, FriendshipViewSet

router = DefaultRouter()

router.register("social/friendship_request", FriendshipRequestViewSet, basename="social-friendship-request")
router.register("social/friendship", FriendshipViewSet, basename="social-friendship")
