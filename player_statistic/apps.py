from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlayerStatisticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'player_statistic'
    verbose_name = _("Player Statistic")
    verbose_name_plural = _("Player Statistics")

    def ready(self):
        # noinspection PyUnresolvedReferences
        from . import signals  # noq
