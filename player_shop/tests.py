from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta

from user.models import NormalPlayer, GuestPlayer
from shop.models import (
    RewardPackage, ShopConfiguration, Currency, Asset, CurrencyPackageItem,
    DailyRewardPackage
)
from shop.choices import AssetType
from player_shop.models import PlayerWallet, CurrencyBalance, AssetOwnership


class PlayerWalletViewSetTests(APITestCase):
    """Test PlayerWalletViewSet behaviors for wallet and inventory management"""

    def setUp(self):
        """Create test user, currencies, assets, and wallet data"""
        # Create initial package and shop config for player creation
        self.initial_package = RewardPackage.objects.create(
            name='Initial Package',
            reward_type=RewardPackage.RewardType.INIT_WALLET
        )
        self.shop_config = ShopConfiguration.objects.create(
            player_initial_package=self.initial_package
        )

        # Create test users
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123',
            profile_name='TestUser'
        )
        self.user.is_verified = True
        self.user.save()

        self.other_user = NormalPlayer.objects.create_user(
            email='other@example.com',
            password='password123',
            profile_name='OtherUser'
        )
        self.other_user.is_verified = True
        self.other_user.save()

        self.guest_user = GuestPlayer.objects.create_user(
            device_id='guest-device-123',
            password='password123'
        )

        # Create currencies
        self.coins = Currency.objects.create(
            name='Coins',
            type=Currency.CurrencyType.IN_APP
        )
        self.gems = Currency.objects.create(
            name='Gems',
            type=Currency.CurrencyType.IN_APP
        )
        self.usd = Currency.objects.create(
            name='USD',
            type=Currency.CurrencyType.REAL
        )

        # Create assets
        self.avatar1 = Asset.objects.create(
            name='Default Avatar',
            type=AssetType.AVATAR,
            config={'color': 'blue'}
        )
        self.avatar2 = Asset.objects.create(
            name='Premium Avatar',
            type=AssetType.AVATAR,
            config={'color': 'gold'}
        )
        self.sticker1 = Asset.objects.create(
            name='Happy Sticker',
            type=AssetType.STICKER,
            config={'emoji': '😊'}
        )
        self.sticker2 = Asset.objects.create(
            name='Cool Sticker',
            type=AssetType.STICKER,
            config={'emoji': '😎'}
        )

        # Set up user wallet with currencies
        self.user_wallet = self.user.shop_info

        CurrencyBalance.objects.create(
            wallet=self.user_wallet,
            currency=self.coins,
            balance=1000
        )
        CurrencyBalance.objects.create(
            wallet=self.user_wallet,
            currency=self.gems,
            balance=50
        )
        CurrencyBalance.objects.create(
            wallet=self.user_wallet,
            currency=self.usd,
            balance=0
        )

        # Give user some assets
        self.user_avatar1 = AssetOwnership.objects.create(
            wallet=self.user_wallet,
            asset=self.avatar1,
            is_current=True  # Set as current avatar
        )
        self.user_avatar2 = AssetOwnership.objects.create(
            wallet=self.user_wallet,
            asset=self.avatar2,
            is_current=False
        )
        self.user_sticker1 = AssetOwnership.objects.create(
            wallet=self.user_wallet,
            asset=self.sticker1,
            is_current=False
        )

    def test_authenticated_user_can_view_wallet_overview(self):
        """Authenticated users should see their complete wallet information"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include currency balances
        self.assertIn('currency_balances', response.data)
        self.assertEqual(len(response.data['currency_balances']), 3)

        # Should include asset ownerships
        self.assertIn('asset_ownerships', response.data)
        self.assertEqual(len(response.data['asset_ownerships']), 3)

        # Check currency data
        currency_names = [cb['currency']['name'] for cb in response.data['currency_balances']]
        self.assertIn('Coins', currency_names)
        self.assertIn('Gems', currency_names)
        self.assertIn('USD', currency_names)

        # Check asset data
        asset_names = [ao['asset']['name'] for ao in response.data['asset_ownerships']]
        self.assertIn('Default Avatar', asset_names)
        self.assertIn('Premium Avatar', asset_names)
        self.assertIn('Happy Sticker', asset_names)

    def test_unauthenticated_user_cannot_view_wallet(self):
        """Unauthenticated users cannot access wallet information"""
        response = self.client.get(reverse('wallet-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guest_user_can_view_their_wallet(self):
        """Guest users should also be able to view their wallet"""
        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('wallet-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('currency_balances', response.data)
        self.assertIn('asset_ownerships', response.data)

    def test_user_can_view_all_currencies(self):
        """Users should be able to view all their currency balances"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-currency'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        # Check specific currency balances
        coins_balance = next(cb for cb in response.data if cb['currency']['name'] == 'Coins')
        self.assertEqual(coins_balance['balance'], 1000)

        gems_balance = next(cb for cb in response.data if cb['currency']['name'] == 'Gems')
        self.assertEqual(gems_balance['balance'], 50)

    def test_user_can_filter_currencies_by_type(self):
        """Users should be able to filter currencies by type"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-currency'), {'type': 'in_app'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Coins and Gems only

        currency_names = [cb['currency']['name'] for cb in response.data]
        self.assertIn('Coins', currency_names)
        self.assertIn('Gems', currency_names)
        self.assertNotIn('USD', currency_names)

    def test_user_can_view_all_assets(self):
        """Users should be able to view all their owned assets"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-asset'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        # Check current avatar is marked correctly
        current_avatar = next(
            ao for ao in response.data
            if ao['asset']['name'] == 'Default Avatar'
        )
        self.assertTrue(current_avatar['is_current'])

        # Check non-current assets
        premium_avatar = next(
            ao for ao in response.data
            if ao['asset']['name'] == 'Premium Avatar'
        )
        self.assertFalse(premium_avatar['is_current'])

    def test_user_can_filter_assets_by_type(self):
        """Users should be able to filter assets by type"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-asset'), {'type': 'avatar'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Only avatars

        asset_names = [ao['asset']['name'] for ao in response.data]
        self.assertIn('Default Avatar', asset_names)
        self.assertIn('Premium Avatar', asset_names)
        self.assertNotIn('Happy Sticker', asset_names)

    def test_user_can_set_avatar_from_owned_assets(self):
        """Users should be able to set avatar from assets they own"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('wallet-asset-set-avatar', kwargs={'asset_ownership': self.user_avatar2.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that avatar was changed
        self.user_avatar2.refresh_from_db()
        self.user_avatar1.refresh_from_db()

        self.assertTrue(self.user_avatar2.is_current)
        self.assertFalse(self.user_avatar1.is_current)

    def test_user_cannot_set_avatar_from_non_owned_asset(self):
        """Users should not be able to set avatar from assets they don't own"""
        # Create asset owned by other user
        other_wallet = self.other_user.shop_info
        other_avatar = AssetOwnership.objects.create(
            wallet=other_wallet,
            asset=self.avatar2,
            is_current=False
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('wallet-asset-set-avatar', kwargs={'asset_ownership': other_avatar.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_set_non_avatar_asset_as_avatar(self):
        """Users should not be able to set non-avatar assets as avatars"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('wallet-asset-set-avatar', kwargs={'asset_ownership': self.user_sticker1.id})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_setting_nonexistent_asset_as_avatar_returns_404(self):
        """Setting non-existent asset as avatar should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('wallet-asset-set-avatar', kwargs={'asset_ownership': 99999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_wallet_shows_accurate_currency_balances(self):
        """Wallet should show current, accurate currency balances"""
        # Update currency balance
        coins_balance = CurrencyBalance.objects.get(wallet=self.user_wallet, currency=self.coins)
        coins_balance.balance = 1500
        coins_balance.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-currency'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        coins_data = next(cb for cb in response.data if cb['currency']['name'] == 'Coins')
        self.assertEqual(coins_data['balance'], 1500)

    def test_wallet_includes_complete_currency_information(self):
        """Wallet currency data should include complete currency details"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-currency'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for currency_balance in response.data:
            # Should include currency details
            self.assertIn('currency', currency_balance)
            self.assertIn('balance', currency_balance)

            currency = currency_balance['currency']
            self.assertIn('id', currency)
            self.assertIn('name', currency)
            self.assertIn('type', currency)

    def test_wallet_includes_complete_asset_information(self):
        """Wallet asset data should include complete asset details"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('wallet-asset'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for asset_ownership in response.data:
            # Should include asset details
            self.assertIn('asset', asset_ownership)
            self.assertIn('is_current', asset_ownership)

            asset = asset_ownership['asset']
            self.assertIn('id', asset)
            self.assertIn('name', asset)
            self.assertIn('type', asset)
            self.assertIn('config', asset)

    def test_user_with_no_currencies_sees_empty_list(self):
        """Users with no currencies should see empty currency list"""
        # Create user with no currency balances
        empty_user = NormalPlayer.objects.create_user(
            email='empty@example.com',
            password='password123'
        )
        empty_user.is_verified = True
        empty_user.save()

        self.client.force_authenticate(user=empty_user)

        response = self.client.get(reverse('wallet-currency'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_user_with_no_assets_sees_empty_list(self):
        """Users with no assets should see empty asset list"""
        empty_user = NormalPlayer.objects.create_user(
            email='empty2@example.com',
            password='password123'
        )
        empty_user.is_verified = True
        empty_user.save()

        self.client.force_authenticate(user=empty_user)

        response = self.client.get(reverse('wallet-asset'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()


class PlayerDailyRewardViewSetTests(APITestCase):
    """Test PlayerDailyRewardViewSet behaviors for daily reward system"""

    def setUp(self):
        """Create test user and daily reward configuration"""
        # Create initial package and shop config for player creation
        self.initial_package = RewardPackage.objects.create(
            name='Initial Package',
            reward_type=RewardPackage.RewardType.INIT_WALLET
        )
        self.shop_config = ShopConfiguration.objects.create(
            player_initial_package=self.initial_package
        )

        # Create daily reward packages
        self.day1_reward = RewardPackage.objects.create(
            name='Day 1 Reward',
            reward_type=RewardPackage.RewardType.DAILY_REWARD
        )
        self.day2_reward = RewardPackage.objects.create(
            name='Day 2 Reward',
            reward_type=RewardPackage.RewardType.DAILY_REWARD
        )
        self.day3_reward = RewardPackage.objects.create(
            name='Day 3 Reward',
            reward_type=RewardPackage.RewardType.DAILY_REWARD
        )

        DailyRewardPackage.objects.create(day_number=1, reward=self.day1_reward)
        DailyRewardPackage.objects.create(day_number=2, reward=self.day2_reward)
        DailyRewardPackage.objects.create(day_number=3, reward=self.day3_reward)

        # Create currency for rewards
        self.coins = Currency.objects.create(
            name='Coins',
            type=Currency.CurrencyType.IN_APP
        )

        # Add currency items to rewards
        coin_item = CurrencyPackageItem.objects.create(currency=self.coins, amount=100)
        self.day1_reward.currency_items.add(coin_item)

        # Create test users
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123',
            profile_name='TestUser'
        )
        self.user.is_verified = True
        self.user.save()

        self.other_user = NormalPlayer.objects.create_user(
            email='other@example.com',
            password='password123',
            profile_name='OtherUser'
        )
        self.other_user.is_verified = True
        self.other_user.save()

        self.guest_user = GuestPlayer.objects.create_user(
            device_id='guest-device-123',
            password='password123'
        )

    def test_eligible_user_can_claim_daily_reward(self):
        """Users who are eligible should be able to claim daily rewards"""
        # User hasn't claimed before, so they're eligible
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check user's daily reward data was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 1)
        self.assertIsNotNone(self.user.last_claimed)

    def test_user_cannot_claim_daily_reward_twice_same_day(self):
        """Users should not be able to claim daily reward twice in the same day"""
        # Set user as having claimed today
        self.user.last_claimed = timezone.now()
        self.user.daily_reward_streak = 1
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
        self.assertIn('error', response.data)

    def test_user_can_claim_daily_reward_next_day(self):
        """Users should be able to claim daily reward the next day"""
        # Set user as having claimed yesterday
        self.user.last_claimed = timezone.now() - timedelta(days=1)
        self.user.daily_reward_streak = 1
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Streak should continue
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 2)

    def test_daily_reward_streak_resets_after_missing_day(self):
        """Daily reward streak should reset if user misses a day"""
        # Set user as having claimed 3 days ago (missed 2 days)
        self.user.last_claimed = timezone.now() - timedelta(days=3)
        self.user.daily_reward_streak = 5
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Streak should reset to 1
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 1)

    def test_daily_reward_streak_cycles_after_max_days(self):
        """Daily reward streak should cycle back to 1 after reaching max streak"""
        # Set user as having claimed yesterday with max streak
        self.user.last_claimed = timezone.now() - timedelta(days=1)
        self.user.daily_reward_streak = 3  # Max available rewards
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Streak should cycle back to 1
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 1)

    def test_guest_user_can_claim_daily_reward(self):
        """Guest users should also be able to claim daily rewards"""
        self.client.force_authenticate(user=self.guest_user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check guest user's data was updated
        self.guest_user.refresh_from_db()
        self.assertEqual(self.guest_user.daily_reward_streak, 1)

    def test_unauthenticated_user_cannot_claim_daily_reward(self):
        """Unauthenticated users cannot claim daily rewards"""
        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_claiming_daily_reward_updates_wallet(self):
        """Claiming daily reward should update user's wallet with rewards"""
        # Check initial wallet state
        initial_balance = CurrencyBalance.objects.filter(
            wallet=self.user.shop_info,
            currency=self.coins
        ).first()
        initial_amount = initial_balance.balance if initial_balance else 0

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check wallet was updated with reward
        updated_balance = CurrencyBalance.objects.get(
            wallet=self.user.shop_info,
            currency=self.coins
        )
        self.assertEqual(updated_balance.balance, initial_amount + 100)

    def test_daily_reward_claim_response_includes_updated_wallet(self):
        """Daily reward claim response should include updated wallet information"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Response should include wallet data
        self.assertIn('currency_balances', response.data)
        self.assertIn('asset_ownerships', response.data)

    def test_first_time_user_gets_day_1_reward(self):
        """First-time users should get day 1 reward"""
        # Ensure user has never claimed
        self.user.last_claimed = None
        self.user.daily_reward_streak = 0
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 1)

    def test_consecutive_day_user_gets_progressive_reward(self):
        """Users claiming on consecutive days should get progressive rewards"""
        # Set user as having claimed yesterday with streak 1
        self.user.last_claimed = timezone.now() - timedelta(days=1)
        self.user.daily_reward_streak = 1
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('daily-reward-claim'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should progress to day 2
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 2)

    def test_multiple_users_can_claim_independently(self):
        """Multiple users should be able to claim daily rewards independently"""
        self.client.force_authenticate(user=self.user)
        response1 = self.client.post(reverse('daily-reward-claim'))
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.other_user)
        response2 = self.client.post(reverse('daily-reward-claim'))
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Both users should have streak 1
        self.user.refresh_from_db()
        self.other_user.refresh_from_db()
        self.assertEqual(self.user.daily_reward_streak, 1)
        self.assertEqual(self.other_user.daily_reward_streak, 1)

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()
