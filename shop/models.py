import math
import random
from datetime import timedelta

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from imagekit.models.fields import ImageSpecField
from imagekit.processors import ResizeToFill

from common.models import BaseModel, SingletonCachableModel, CachableModel
from exceptions.shop import EmptyLuckyWheelError
from shop.choices import AssetType


class Market(BaseModel):
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    name = models.CharField(max_length=255, unique=True, verbose_name=_('Name'))
    last_version = models.IntegerField(verbose_name=_("last version"), default=0)
    support_version = models.IntegerField(verbose_name=_("support version"), default=0)
    config = models.JSONField(verbose_name=_("config"), null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Market')
        verbose_name_plural = _('Markets')
        ordering = ['created_time', ]


class Currency(BaseModel):
    class CurrencyType(models.TextChoices):
        IN_APP = 'in_app', 'In App'
        REAL = 'real', 'Real'

    name = models.CharField(verbose_name=_("Currency Name"), max_length=100, unique=True)
    icon = models.ImageField(upload_to='currencies', null=True, blank=True, verbose_name=_("Currency Icon"))
    config = models.JSONField(null=True, blank=True, verbose_name=_("Currency Config"))
    type = models.CharField(verbose_name=_("Currency Type"), choices=CurrencyType.choices, max_length=100,
                            default=CurrencyType.IN_APP)
    icon_thumbnail = ImageSpecField(
        source='icon',
        processors=[ResizeToFill(30, 30)],
        format='PNG',
        options={'quality': 60}
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")

    def save(self, *args, **kwargs):
        if not self.pk and self.icon:
            self.icon.name = f'{self.name}.{self.icon.name.split('.')[-1]}'
        super(Currency, self).save(*args, **kwargs)


class Asset(BaseModel):
    name = models.CharField(verbose_name=_("Asset Name"), max_length=100, unique=True)
    config = models.JSONField(null=True, blank=True, verbose_name=_("Asset Config"))
    type = models.CharField(verbose_name=_("Asset Type"), max_length=100, choices=AssetType.choices,
                            default=AssetType.AVATAR)
    image = models.ImageField(verbose_name=_("Image"), null=True, blank=True, upload_to='assets')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Asset")
        verbose_name_plural = _("Assets")


class Cost(BaseModel):
    currency = models.ForeignKey(to=Currency, verbose_name=_("Currency"), on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(verbose_name=_("Amount"), default=0)

    def __str__(self):
        return f'{self.amount} X {self.currency}'

    class Meta:
        verbose_name = _("Cost")
        verbose_name_plural = _("Costs")
        unique_together = (("currency", "amount"),)


class CurrencyPackageItem(BaseModel):
    currency = models.ForeignKey(to=Currency, verbose_name=_("Currency"), on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(verbose_name=_("Amount"), default=0)
    config = models.JSONField(null=True, blank=True, verbose_name=_("Config"))

    def __str__(self):
        return f'{self.amount} X {self.currency}'

    class Meta:
        verbose_name = _("Currency Package Item")
        verbose_name_plural = _("Currency Package Items")


class Package(BaseModel):
    start_time = models.DateTimeField(verbose_name=_("Start Time"), null=True, blank=True, )
    name = models.CharField(verbose_name=_("Name"), unique=True, max_length=255)
    priority = models.PositiveIntegerField(verbose_name=_("Priority"), help_text=_("1 is More important"), default=1)
    expiration_date = models.DateTimeField(verbose_name=_("Expired time"), null=True, blank=True, )
    image = models.ImageField(upload_to='package', null=True, blank=True, verbose_name=_("Image"))
    config = models.JSONField(null=True, blank=True, verbose_name=_("Config"))
    currency_items = models.ManyToManyField(to=CurrencyPackageItem, verbose_name=_("Currency Package Items"),
                                            blank=True)
    asset_items = models.ManyToManyField(to=Asset, verbose_name=_("Asset Package Items"), blank=True)
    icon_thumbnail = ImageSpecField(
        source='image',
        processors=[ResizeToFill(30, 30)],
        format='PNG',
        options={'quality': 60}
    )


    def _has_started(self):
        return self.start_time and self.start_time > timezone.now()

    def _has_expired(self):
        return not self.expiration_date or self.expiration_date > timezone.now()

    def is_pacakge_available(self):
        return self._has_started() and not self._has_expired()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Package")
        verbose_name_plural = _("Packages")
        abstract = True


class ShopSection(BaseModel):
    name = models.CharField(verbose_name=_("Name"), max_length=255, unique=True)
    config = models.JSONField(null=True, blank=True, verbose_name=_("Config"))

    def __str__(self):
        return self.name

    @property
    def packages(self):
        return self.packages.filter(is_active=True)

    class Meta:
        verbose_name = _("Shop Section")
        verbose_name_plural = _("Shop Sections")


class ShopPackage(Package):
    price_currency = models.ForeignKey(to=Currency, verbose_name=_("Price"), on_delete=models.CASCADE)
    price_amount = models.PositiveIntegerField(verbose_name=_("Price Amount"), default=0)
    discount = models.FloatField(verbose_name=_("Discount"), default=0.0, null=True, blank=True,
                                 validators=[MinValueValidator(0), MaxValueValidator(1)])
    discount_start = models.DateTimeField(verbose_name=_("Discount Start Time"), null=True, blank=True, )
    discount_end = models.DateTimeField(verbose_name=_("Discount End Time"), null=True, blank=True, )
    shop_section = models.ForeignKey(to=ShopSection, verbose_name=_("Shop Section"), on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='packages')
    sku = models.CharField(verbose_name=_("SKU"), max_length=100, unique=True)
    markets = models.ManyToManyField(to=Market, verbose_name=_("Markets"), blank=True,
                                     related_name='shop_packages')

    def _is_in_discount_period(self) -> bool:
        has_discount_values = self.discount_start and self.discount_end
        if has_discount_values:
            is_in_period = self.discount_end > timezone.now() > self.discount_start
            return is_in_period
        return False

    def is_in_discount(self):
        return self._is_in_discount_period()

    @property
    def final_price(self) -> int:
        if self.is_in_discount():
            return math.ceil(self.price_amount * (1 - self.discount))
        return self.price_amount

    @property
    def is_in_app_purchase(self):
        return self.price_currency.type == Currency.CurrencyType.IN_APP

    class Meta:
        verbose_name = _("Shop Package")
        verbose_name_plural = _("Shop Packages")
        ordering = ('priority',)


class RewardPackage(Package):
    class RewardType(models.TextChoices):
        INIT_WALLET = 'initial_wallet', _('Initial')
        DAILY_REWARD = 'daily', _('Daily')
        LUCKY_WHEEL = 'lucky_wheel', _('Lucky Wheel')
        MATCH_REWARD = 'match_reward', _('Match Reward')

    reward_type = models.CharField(verbose_name=_("Reward Type"), choices=RewardType.choices, max_length=50)
    claimable = models.BooleanField(verbose_name=_("Claimable"), default=False)

    class Meta:
        verbose_name = _("Reward Package")
        verbose_name_plural = _("Reward Packages")


class ShopConfiguration(SingletonCachableModel):
    player_initial_package = models.ForeignKey(to=RewardPackage, verbose_name=_("Player Initial Package"),
                                               on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return 'Shop Configuration'

    class Meta:
        verbose_name = _("Shop Configuration")
        verbose_name_plural = _("Shop Configurations")


class DailyRewardPackage(CachableModel):
    day_number = models.PositiveIntegerField(default=1, verbose_name=_("Day number"), unique=True)
    reward = models.ForeignKey(to=RewardPackage, verbose_name=_("Reward"), on_delete=models.SET_NULL, null=True,
                               blank=True)

    def __str__(self):
        return f'Day {self.day_number} reward'

    class Meta:
        verbose_name = _("Daily Reward")
        verbose_name_plural = _("Daily Rewards")
        ordering = ('day_number',)


class LuckyWheel(BaseModel):
    name = models.CharField(verbose_name=_("Name"), max_length=255, default="Wheel of fortune")
    cool_down = models.DurationField(verbose_name=_('Cool down'), default=timedelta(days=1))

    @property
    def accumulated_chance(self) -> int:
        return self.sections.filter(is_active=True).aggregate(Sum('chance'))['chance__sum']

    @property
    def sections_count(self) -> int:
        return self.sections.filter(is_active=True).count()

    def spin(self) -> 'RewardPackage':
        if self.sections_count < 1:
            raise EmptyLuckyWheelError(_("Lucky Wheel is empty."))
        
        sections = self.sections.filter(is_active=True).select_related("package")
        weighted_sections = [(section, section.chance) for section in sections]

        selected_section = random.choices(
            population=[section for section, __ in weighted_sections],
            weights=[weight for __, weight in weighted_sections],
            k=1
        )[0]
        return selected_section.package

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Lucky Wheel")
        verbose_name_plural = _("Lucky Wheel")


class LuckyWheelSection(BaseModel):
    package = models.ForeignKey(to=RewardPackage, verbose_name=_("Package"), on_delete=models.SET_NULL, null=True,
                                blank=True)
    chance = models.PositiveIntegerField(verbose_name=_("Chance"), default=0)

    lucky_wheel = models.ForeignKey(to=LuckyWheel, verbose_name=_("Lucky Wheel"), on_delete=models.CASCADE,
                                    related_name="sections")

    def __str__(self):
        return f'{self.lucky_wheel} section'

    class Meta:
        verbose_name = _("Lucky Wheel Section")
        verbose_name_plural = _("Lucky Wheel Sections")
        unique_together = (('package', 'lucky_wheel'),)
