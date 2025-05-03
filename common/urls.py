from rest_framework.routers import DefaultRouter

from common.views import ConfigurationViewSet

router = DefaultRouter()

router.register('common/configuration', ConfigurationViewSet, basename='common-configuration')
