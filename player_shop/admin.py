from django.contrib import admin

from player_shop.models import PlayerWallet, PlayerWalletLog, CurrencyBalance, AssetOwnership, PlayerRewardPackage


class PlayerCurrencyAdminInline(admin.TabularInline):
    model = CurrencyBalance
    extra = 1


class PlayerAssetAdminInline(admin.TabularInline):
    model = AssetOwnership
    extra = 1


@admin.register(PlayerWallet)
class PlayerWalletAdmin(admin.ModelAdmin):
    inlines = [PlayerCurrencyAdminInline, PlayerAssetAdminInline]


@admin.register(PlayerWalletLog)
class PlayerWalletLogAdmin(admin.ModelAdmin):
    list_display = ['player', 'transaction_id', 'currency', 'amount', 'asset', 'transaction_type', ]
    list_filter = ['currency', 'asset', 'transaction_type', ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PlayerRewardPackage)
class PlayerRewardPackageAdmin(admin.ModelAdmin):
    list_display = ('player', 'package', 'created_time', )
    list_filter = ('package', )
    date_hierarchy = 'created_time'
