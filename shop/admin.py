from django.contrib import admin
from django.utils.html import format_html

from shop.models import Currency, ShopPackage, RewardPackage, CurrencyPackageItem, Asset, Market, ShopSection, \
    ShopConfiguration, Cost, DailyRewardPackage, LuckyWheel, LuckyWheelSection


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_active', 'display_thumbnail', ]
    list_filter = ['is_active', 'type', ]
    search_fields = ['name', ]

    def display_thumbnail(self, obj):
        if obj.icon_thumbnail:
            return format_html('<img src="{}" width="30" height="30" />', obj.icon_thumbnail.url)
        return "-"

    display_thumbnail.short_description = 'Icon Thumbnail'


@admin.register(ShopPackage)
class ShopPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_currency', 'price_amount', 'is_in_discount', 'final_price', ]
    list_filter = ['shop_section', 'markets', 'is_active', ]
    search_fields = ['name', 'sku', ]


@admin.register(RewardPackage)
class RewardPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'reward_type', 'claimable', 'is_active', ]
    list_filter = ['reward_type', 'claimable', 'is_active', ]
    search_fields = ['name', ]


@admin.register(CurrencyPackageItem)
class CurrencyPackageItemAdmin(admin.ModelAdmin):
    list_display = ['currency', 'amount', 'is_active', ]
    list_filter = ['currency']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_active', ]
    list_filter = ['type', 'is_active', ]
    search_fields = ['name', ]


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', ]
    list_filter = ['is_active', ]
    search_fields = ['name', ]


class ShopPackageInline(admin.TabularInline):
    model = ShopPackage
    extra = 0
    fields = ['name', 'price_currency', 'price_amount', ]
    can_delete = True
    show_change_link = True

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ShopSection)
class ShopSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', ]
    list_filter = ['is_active', ]
    search_fields = ['name', ]
    inlines = [ShopPackageInline, ]


@admin.register(Cost)
class CostAdmin(admin.ModelAdmin):
    list_display = ['currency', 'amount', 'is_active', ]
    list_filter = ['currency', 'is_active', ]


@admin.register(ShopConfiguration)
class ShopConfigurationAdmin(admin.ModelAdmin):
    list_display = ['__str__', ]


@admin.register(DailyRewardPackage)
class DailyRewardPackageAdmin(admin.ModelAdmin):
    list_display = ['day_number', 'reward', 'is_active', ]


class LuckyWheelSectionInline(admin.TabularInline):
    model = LuckyWheelSection
    extra = 1


@admin.register(LuckyWheel)
class LuckyWheelAdmin(admin.ModelAdmin):
    inlines = [LuckyWheelSectionInline, ]
    list_display = ['__str__', 'cool_down', 'sections_count', 'accumulated_chance', ]

