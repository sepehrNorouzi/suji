from rest_framework import serializers

from player_shop.models import PlayerWallet, CurrencyBalance, AssetOwnership
from shop.serializers import CurrencySerializer, AssetItemSerializer


class CurrencyBalanceSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer()

    class Meta:
        model = CurrencyBalance
        fields = ['id', 'currency', 'balance', ]


class AssetOwnerShipSerializer(serializers.ModelSerializer):
    asset = AssetItemSerializer()

    class Meta:
        model = AssetOwnership
        fields = ['id', 'asset', 'is_current', ]


class PlayerWalletSerializer(serializers.ModelSerializer):
    currency_balances = serializers.SerializerMethodField()
    asset_ownerships = serializers.SerializerMethodField()

    class Meta:
        model = PlayerWallet
        fields = ['id', 'currency_balances', 'asset_ownerships', ]

    @staticmethod
    def get_currency_balances(obj):
        return CurrencyBalanceSerializer(obj.currency_balances, many=True).data

    @staticmethod
    def get_asset_ownerships(obj):
        return AssetOwnerShipSerializer(obj.asset_ownerships, many=True).data
