from rest_framework import serializers

from shop.models import ShopPackage, Currency, ShopSection, CurrencyPackageItem, Asset, Market, DailyRewardPackage, \
    RewardPackage, LuckyWheel, LuckyWheelSection, Cost


class MarketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Market
        fields = ['id', 'name']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'name', 'icon', 'config', 'type', ]


class CurrencyItemSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer()

    class Meta:
        model = CurrencyPackageItem
        fields = ['id', 'currency', 'amount', ]


class AssetItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'name', 'config', 'type']


class ShopPackageSerializer(serializers.ModelSerializer):
    has_discount = serializers.SerializerMethodField()
    shop_section = serializers.SerializerMethodField()
    price_currency = CurrencySerializer()
    currency_items = CurrencyItemSerializer(many=True)
    asset_items = AssetItemSerializer(many=True)

    class Meta:
        model = ShopPackage
        fields = ['id', 'price_currency', 'discount', 'discount_start', 'discount_end', 'shop_section', 'sku',
                  'has_discount', 'name', 'currency_items', 'asset_items', ]

    @staticmethod
    def get_has_discount(obj: ShopPackage):
        return obj.is_in_discount()

    @staticmethod
    def get_shop_section(obj: ShopPackage):
        return obj.shop_section.name


class ShopSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopSection
        fields = ['id', 'name', ]


class RewardPackageSerializer(serializers.ModelSerializer):
    currency_items = CurrencyItemSerializer(many=True)
    asset_items = AssetItemSerializer(many=True)

    class Meta:
        model = RewardPackage
        fields = ['id', 'name', 'currency_items', 'asset_items', ]


class DailyRewardPackageSerializer(serializers.ModelSerializer):
    reward = RewardPackageSerializer()

    class Meta:
        model = DailyRewardPackage
        fields = ['id', 'reward', 'day_number', ]


class LuckyWheelSectionSerializer(serializers.ModelSerializer):
    package = RewardPackageSerializer()

    class Meta:
        model = LuckyWheelSection
        fields = ['package', ]


class LuckyWheelRetrieveSerializer(serializers.ModelSerializer):
    sections = serializers.SerializerMethodField()

    class Meta:
        model = LuckyWheel
        fields = ['sections', 'cool_down', 'name', 'id', ]

    @staticmethod
    def get_sections(obj: LuckyWheel):
        return LuckyWheelSectionSerializer(obj.sections, many=True).data

class CostSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer()

    class Meta:
        model = Cost
        fields = ['currency', 'amount', ]