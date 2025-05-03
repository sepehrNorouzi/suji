from django.db import models
from django.utils.translation import gettext_lazy as _


class AssetType(models.TextChoices):
    AVATAR = 'avatar', _('Avatar')
    STICKER = 'sticker', _('Sticker')
