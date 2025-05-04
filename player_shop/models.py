from typing import Union

from django.db import models
from django.db.models.signals import post_save
from django.db.transaction import atomic
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel
from exceptions.player_shop import DailyRewardEligibilityError, LuckyWheelCoolDownError, InvalidAvatarError
from exceptions.shop import WrongShopFlowError, NotEnoughCreditError
from shop.choices import AssetType
from shop.models import Currency, Asset, Market, ShopPackage, ShopConfiguration, RewardPackage, Package, \
    DailyRewardPackage, LuckyWheel
from user.models import Player, User, NormalPlayer, GuestPlayer


class PlayerRewardPackage(BaseModel):
    player = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Player"))
    package = models.ForeignKey(RewardPackage, on_delete=models.CASCADE, verbose_name=_("Reward Package"))

    class Meta:
        verbose_name = _("Player Reward Package")
        verbose_name_plural = _("Player Reward Packages")

    def __str__(self):
        return f"{self.player} - {self.package}"


class PlayerWallet(BaseModel):
    player_market = models.ForeignKey(to=Market, on_delete=models.SET_NULL, verbose_name=_("Market"), null=True,
                                      blank=True)
    player = models.OneToOneField(to=User, on_delete=models.RESTRICT, verbose_name=_("Player"),
                                  related_name="shop_info")

    def __str__(self):
        return f"{self.player} Shop info"

    class Meta:
        verbose_name = _("Player Wallet")
        verbose_name_plural = _("Players Wallets")

    def get_or_create_currency(self, currency: Currency) -> 'CurrencyBalance':
        return self.currency_balances.get_or_create(currency=currency)[0]

    def get_player_currency(self, currency: Currency) -> Union['CurrencyBalance', None]:
        return self.currency_balances.filter(currency=currency).first()

    def has_enough_credit(self, currency: Currency, amount: int) -> bool:
        if not isinstance(currency, Currency):
            raise ValueError(f"{currency} must be of type Currency")
        player_currency: CurrencyBalance = self.get_player_currency(currency)
        return player_currency and player_currency.balance >= amount

    def get_player_asset(self, asset: Asset) -> Asset:
        return self.asset_ownerships.filter(asset=asset).first()

    def buy_package(self, package: ShopPackage):
        if package.price_currency.type == package.price_currency.CurrencyType.REAL:
            raise WrongShopFlowError(_(f"{package.name} must be bought through market verification."))

        if not self.has_enough_credit(package.price_currency, package.final_price):
            raise NotEnoughCreditError(_(f"Player does not have enough {package.price_currency} for {package.name}."))

        self.add_shop_package(package, description="buying.")

    def pay(self, currency: Currency, amount: int, description: str = None):
        if self.has_enough_credit(currency=currency, amount=amount):
            player_currency = self.get_player_currency(currency)
            player_currency.balance -= amount
            player_currency.save()
            PlayerWalletLog.objects.create(player=self.player, description=description,
                                           transaction_type=PlayerWalletLog.TransactionType.SPEND,
                                           currency=currency, amount=amount)
        else:
            raise NotEnoughCreditError(_(f"Player does not have enough {currency} to pay."))

    def _add_package_base(self, package: Package, description):
        player_wallet_log_objects = []
        for item in package.currency_items.all():
            player_currency = self.get_or_create_currency(item.currency)
            player_currency.balance += item.amount
            description = f"{self.player} earned {item.amount} X {item.currency} from {description}"
            player_wallet_log_objects.append(PlayerWalletLog(player=self.player, description=description,
                                                             transaction_type=PlayerWalletLog.TransactionType.EARN,
                                                             currency=item.currency, amount=item.amount), )
            player_currency.save()
        assets = []
        for item in package.asset_items.all():
            player_asset = self.get_player_asset(asset=item)
            if player_asset:
                continue
            assets.append(AssetOwnership(wallet_id=self.id, asset=item))
            description = f"{self.player} earned {item} from {description}"
            player_wallet_log_objects.append(PlayerWalletLog(player=self.player, description=description,
                                                             transaction_type=PlayerWalletLog.TransactionType.EARN,
                                                             asset=item))
        self.asset_ownerships.bulk_create(assets)
        PlayerWalletLog.objects.bulk_create(player_wallet_log_objects)
        if package.has_supported:
            self.player.supports.create(reason=package.support_type)
        if package.vip:
            player_vip, c = self.player.vip.get_or_create()
            if c or player_vip.is_expired():
                player_vip.expiration_date = timezone.now() + package.vip_duration
            else:
                player_vip.expiration_date = player_vip.expiration_date + package.vip_duration
            player_vip.save()

    @atomic()
    def add_shop_package(self, package: ShopPackage, description=None):
        self.pay(package.price_currency, package.price_amount, f"Bought {package.name}")
        self._add_package_base(package, description)

    @atomic()
    def add_reward_package(self, package: RewardPackage, description=None):
        if not package.claimable:
            self._add_package_base(package, description)
        else:
            PlayerRewardPackage.objects.create(player=self.player, package=package)

    @atomic()
    def claim_reward_package(self, player_package: PlayerRewardPackage):
        self._add_package_base(player_package.package, f'{player_package.package.reward_type}')
        player_package.adelete()

    def claim_daily_reward(self):
        player: Player = self.player.player
        if not player.is_eligible_for_daily_reward():
            raise DailyRewardEligibilityError(_("Player is not eligible to claim daily reward."))
        reward_packages = DailyRewardPackage.load()
        player = player.claim_daily_reward(max_streak=reward_packages.last().day_number)
        reward_package = reward_packages.filter(day_number=player.daily_reward_streak)
        if reward_package.exists():
            self.add_reward_pacakge(reward_package.first())

    def spin_lucky_wheel(self, lucky_wheel: LuckyWheel):
        player: Player = self.player.player
        can_spin, next_spin = player.can_spin_lucky_wheel(lucky_wheel.cool_down)
        if not can_spin:
            raise LuckyWheelCoolDownError(_(f"Player can't spin lucky wheel for {next_spin}."))
        reward = lucky_wheel.spin()
        player.spin_lucky_wheel()
        self.add_reward_pacakge(reward, 'Lucky wheel')
        return reward

    @classmethod
    def initialize(cls, player):
        wallet, c = cls.objects.get_or_create(player=User.objects.get(pk=player.pk))
        if not c:
            return
        init_package: RewardPackage = ShopConfiguration.load().player_initial_package
        wallet.add_reward_pacakge(init_package, "Initiation.")

    def current_asset(self, asset_type: AssetType) -> 'AssetOwnership':
        return self.asset_ownerships.filter(asset__type=asset_type, is_current=True).first()

    def set_avatar(self, asset_ownership: 'AssetOwnership') -> 'PlayerWallet':
        if asset_ownership.asset.type != AssetType.AVATAR:
            raise InvalidAvatarError(_(f"Selected asset should be {AssetType.AVATAR} not {asset_ownership.asset.type}"))
        asset_ownership.set_current()
        self.player.cache_user()
        return self


class CurrencyBalance(models.Model):
    wallet = models.ForeignKey(PlayerWallet, on_delete=models.CASCADE, related_name='currency_balances')
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    balance = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('wallet', 'currency')
        verbose_name = _("Currency Balance")
        verbose_name_plural = _("Currency Balance")

    def __str__(self):
        return f"{self.balance} {self.currency.name} in {self.wallet}"


class AssetOwnership(models.Model):
    wallet = models.ForeignKey(PlayerWallet, on_delete=models.CASCADE, related_name='asset_ownerships')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, verbose_name=_("Asset"))
    is_current = models.BooleanField(default=False, verbose_name=_("Is Current"))

    class Meta:
        unique_together = ('wallet', 'asset')
        verbose_name = _("Asset Ownership")
        verbose_name_plural = _("Asset Ownerships")

    def __str__(self):
        return f"{self.asset.name} owned by {self.wallet.player.username}"

    def save(self, *args, **kwargs):
        if self.is_current:
            self.__class__.objects.filter(asset__type=self.asset.type).exclude(id=self.id).update(is_current=False)
        super(AssetOwnership, self).save(*args, **kwargs)

    def set_current(self):
        self.is_current = True
        self.save()


class PlayerWalletLog(BaseModel):
    class TransactionType(models.TextChoices):
        SPEND = 'spend', _('Spend')
        EARN = 'earn', _('Earn')

    player = models.ForeignKey(to=User, on_delete=models.RESTRICT, verbose_name=_("Player"),
                               related_name="transactions")
    description = models.TextField(verbose_name=_("Description"), blank=True, null=True)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, default=TransactionType.EARN)
    transaction_id = models.CharField(max_length=255, verbose_name=_("Transaction ID"), null=True, blank=True)
    currency = models.ForeignKey(to=Currency, on_delete=models.SET_NULL, verbose_name=_("Currency"), null=True,
                                 blank=True)
    amount = models.PositiveIntegerField(verbose_name=_("Amount"), null=True, blank=True)
    asset = models.ForeignKey(to=Asset, on_delete=models.SET_NULL, verbose_name=_("Asset"), null=True, blank=True)

    def __str__(self):
        return f"{self.player} - {self.description[5:] if self.description else ''} - {self.created_time}"

    class Meta:
        verbose_name = _("Player Wallet Log")
        verbose_name_plural = _("Player Wallet Logs")


@receiver(signal=post_save, sender=NormalPlayer)
def normal_player_post_save_signal(sender, instance, created, **kwargs):
    if created:
        PlayerWallet.initialize(instance)


@receiver(signal=post_save, sender=GuestPlayer)
def guest_post_save_signal(sender, instance, created, **kwargs):
    if created:
        PlayerWallet.initialize(instance)
