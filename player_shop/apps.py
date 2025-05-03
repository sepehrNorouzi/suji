from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlayerShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'player_shop'

    verbose_name = _("Player Shop")
    verbose_name_plural = _("Player Shop")
