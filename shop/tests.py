from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
from decimal import Decimal

from user.models import NormalPlayer
from shop.models import (
    Market, ShopPackage, Currency, ShopSection, CurrencyPackageItem,
    DailyRewardPackage, RewardPackage, LuckyWheel, LuckyWheelSection, Cost, ShopConfiguration
)
from player_shop.models import PlayerWallet, CurrencyBalance


class MarketViewSetTests(APITestCase):
    """Test MarketViewSet behaviors for market management"""

    def setUp(self):
        """Create test user and markets"""
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        self.user.is_verified = True
        self.user.save()

        # Create test markets
        self.active_market = Market.objects.create(
            name='Google Play',
            is_active=True,
            last_version=100,
            support_version=90
        )

        self.inactive_market = Market.objects.create(
            name='Inactive Market',
            is_active=False,
            last_version=50
        )

    def test_authenticated_user_can_list_active_markets(self):
        """Authenticated users should see list of active markets only"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('market-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Google Play')

    def test_unauthenticated_user_cannot_list_markets(self):
        """Unauthenticated users cannot access markets"""
        response = self.client.get(reverse('market-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_retrieve_market_details(self):
        """Authenticated users should be able to view market details"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('market-detail', kwargs={'pk': self.active_market.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Google Play')
        self.assertEqual(response.data['last_version'], 100)

    def test_retrieving_inactive_market_returns_404(self):
        """Inactive markets should not be accessible"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('market-detail', kwargs={'pk': self.inactive_market.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_markets_are_paginated(self):
        """Markets list should support pagination"""
        # Create many markets
        for i in range(25):
            Market.objects.create(name=f'Market {i}', is_active=True)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('market-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)


class ShopViewSetTests(APITestCase):
    """Test ShopViewSet behaviors for shop package management and purchases"""

    def setUp(self):
        """Create test user, market, currency, and shop data"""
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        self.user.is_verified = True
        self.user.save()

        self.initial_package = RewardPackage.objects.create(
            name='Initial Package',
            reward_type=RewardPackage.RewardType.INIT_WALLET
        )

        self.shop_config = ShopConfiguration.objects.create(
            player_initial_package=self.initial_package
        )

        # Create player wallet
        self.market = Market.objects.create(name='Test Market', is_active=True)
        self.wallet = self.user.shop_info
        self.wallet.player_market = self.market
        self.wallet.save()

        self.in_app_currency = Currency.objects.create(
            name='Coins',
            type=Currency.CurrencyType.IN_APP
        )
        self.real_currency = Currency.objects.create(
            name='USD',
            type=Currency.CurrencyType.REAL
        )

        # Give user some in-app currency
        CurrencyBalance.objects.create(
            wallet=self.wallet,
            currency=self.in_app_currency,
            balance=1000
        )

        # Create shop section
        self.section = ShopSection.objects.create(name='Premium Packages')

        # Create shop packages
        self.in_app_package = ShopPackage.objects.create(
            name='Coin Pack',
            price_currency=self.in_app_currency,
            price_amount=100,
            shop_section=self.section,
            sku='coin_pack_001'
        )
        self.in_app_package.markets.add(self.market)

        self.real_money_package = ShopPackage.objects.create(
            name='Premium Pack',
            price_currency=self.real_currency,
            price_amount=499,  # $4.99
            shop_section=self.section,
            sku='premium_pack_001'
        )

        # Package not in user's market
        other_market = Market.objects.create(name='Other Market', is_active=True)
        self.other_market_package = ShopPackage.objects.create(
            name='Other Market Pack',
            price_currency=self.in_app_currency,
            price_amount=200,
            sku='other_pack_001'
        )
        self.other_market_package.markets.add(other_market)

    def test_authenticated_user_can_list_shop_packages_for_their_market(self):
        """Users should only see packages available in their market"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('shop-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        package_names = [pkg['name'] for pkg in response.data['results']]
        self.assertIn('Coin Pack', package_names)
        self.assertIn('Premium Pack', package_names)  # No market restriction
        self.assertNotIn('Other Market Pack', package_names)  # Different market

    def test_user_can_filter_packages_by_section(self):
        """Users should be able to filter packages by shop section"""
        # Create another section with package
        other_section = ShopSection.objects.create(name='Basic Packages')
        basic_package = ShopPackage.objects.create(
            name='Basic Pack',
            price_currency=self.in_app_currency,
            price_amount=50,
            shop_section=other_section,
            sku='basic_pack_001'
        )

        self.client.force_authenticate(user=self.user)

        # Filter by premium section
        response = self.client.get(reverse('shop-list'), {'section': self.section.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        package_names = [pkg['name'] for pkg in response.data['results']]
        self.assertIn('Coin Pack', package_names)
        self.assertNotIn('Basic Pack', package_names)

    def test_user_can_retrieve_package_details_from_their_market(self):
        """Users should be able to view details of packages in their market"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('shop-detail', kwargs={'pk': self.in_app_package.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Coin Pack')
        self.assertEqual(response.data['price_currency']['name'], 'Coins')

    def test_user_cannot_retrieve_package_from_other_market(self):
        """Users should not be able to view packages from other markets"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('shop-detail', kwargs={'pk': self.other_market_package.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_view_shop_sections(self):
        """Users should be able to view available shop sections"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('shop-section'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        section_names = [section['name'] for section in response.data]
        self.assertIn('Premium Packages', section_names)

    def test_user_can_purchase_in_app_package_with_sufficient_currency(self):
        """Users should be able to purchase in-app packages when they have enough currency"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('shop-purchase', kwargs={'pk': self.in_app_package.id}))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])

        # User's currency should be deducted
        currency_balance = CurrencyBalance.objects.get(wallet=self.wallet, currency=self.in_app_currency)
        self.assertEqual(currency_balance.balance, 900)  # 1000 - 100

    def test_user_cannot_purchase_package_without_sufficient_currency(self):
        """Users should not be able to purchase packages without enough currency"""
        # Set user's balance to insufficient amount
        currency_balance = CurrencyBalance.objects.get(wallet=self.wallet, currency=self.in_app_currency)
        currency_balance.balance = 50  # Less than package price of 100
        currency_balance.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('shop-purchase', kwargs={'pk': self.in_app_package.id}))

        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertFalse(response.data['success'])
        self.assertIn('error', response.data)

    def test_user_cannot_purchase_real_money_package_through_purchase_endpoint(self):
        """Real money packages should not be purchasable through regular purchase endpoint"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('shop-purchase', kwargs={'pk': self.real_money_package.id}))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(response.data['success'])
        self.assertIn('error', response.data)

    def test_user_cannot_purchase_package_from_other_market(self):
        """Users should not be able to purchase packages from other markets"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('shop-purchase', kwargs={'pk': self.other_market_package.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_access_shop(self):
        """Unauthenticated users cannot access shop endpoints"""
        response = self.client.get(reverse('shop-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_packages_with_discounts_show_correct_pricing(self):
        """Packages with active discounts should show discounted prices"""
        # Create package with discount
        discounted_package = ShopPackage.objects.create(
            name='Discounted Pack',
            price_currency=self.in_app_currency,
            price_amount=200,
            discount=0.5,  # 50% off
            discount_start=timezone.now() - timedelta(hours=1),
            discount_end=timezone.now() + timedelta(hours=1),
            sku='discounted_pack_001'
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('shop-detail', kwargs={'pk': discounted_package.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_discount'])

    # def test_shop_verify_endpoint_exists(self):
    #     """Shop verify endpoint should exist (even if not implemented)"""
    #     self.client.force_authenticate(user=self.user)
    #
    #     response = self.client.post(reverse('shop-verify'))
    #
    #     # Should not return 404 (endpoint exists)
    #     self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DailyRewardViewSetTests(APITestCase):
    """Test DailyRewardViewSet behaviors for daily reward system"""

    def setUp(self):
        """Create test user and daily rewards"""
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        self.user.is_verified = True
        self.user.save()

        # Create reward packages
        self.day1_reward = RewardPackage.objects.create(
            name='Day 1 Reward',
            reward_type=RewardPackage.RewardType.DAILY_REWARD
        )
        self.day2_reward = RewardPackage.objects.create(
            name='Day 2 Reward',
            reward_type=RewardPackage.RewardType.DAILY_REWARD
        )

        # Create daily reward packages
        self.daily_reward_1 = DailyRewardPackage.objects.create(
            day_number=1,
            reward=self.day1_reward
        )
        self.daily_reward_2 = DailyRewardPackage.objects.create(
            day_number=2,
            reward=self.day2_reward
        )

        # Create inactive daily reward (should not appear)
        inactive_reward = RewardPackage.objects.create(
            name='Inactive Reward',
            reward_type=RewardPackage.RewardType.DAILY_REWARD,
            is_active=False
        )
        DailyRewardPackage.objects.create(
            day_number=3,
            reward=inactive_reward,
            is_active=False
        )

    def test_authenticated_user_can_list_daily_rewards(self):
        """Authenticated users should see list of active daily rewards ordered by day"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('daily-reward-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

        # Should be ordered by day_number
        self.assertEqual(response.data['results'][0]['day_number'], 1)
        self.assertEqual(response.data['results'][1]['day_number'], 2)

    def test_unauthenticated_user_cannot_list_daily_rewards(self):
        """Unauthenticated users cannot access daily rewards"""
        response = self.client.get(reverse('daily-reward-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_retrieve_daily_reward_details(self):
        """Authenticated users should be able to view daily reward details"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('daily-reward-detail', kwargs={'pk': self.daily_reward_1.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['day_number'], 1)
        self.assertEqual(response.data['reward']['name'], 'Day 1 Reward')

    def test_retrieving_inactive_daily_reward_returns_404(self):
        """Inactive daily rewards should not be accessible"""
        inactive_daily_reward = DailyRewardPackage.objects.get(day_number=3)

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('daily-reward-detail', kwargs={'pk': inactive_daily_reward.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_daily_rewards_are_paginated(self):
        """Daily rewards list should support pagination"""
        # Create many daily rewards
        for i in range(25):
            reward = RewardPackage.objects.create(
                name=f'Day {i + 10} Reward',
                reward_type=RewardPackage.RewardType.DAILY_REWARD
            )
            DailyRewardPackage.objects.create(day_number=i + 10, reward=reward)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('daily-reward-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)

    def test_daily_reward_includes_reward_package_details(self):
        """Daily reward response should include full reward package details"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('daily-reward-detail', kwargs={'pk': self.daily_reward_1.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reward', response.data)
        self.assertEqual(response.data['reward']['name'], 'Day 1 Reward')
        self.assertEqual(response.data['reward']['reward_type'], 'daily')


class LuckyWheelViewSetTests(APITestCase):
    """Test LuckyWheelViewSet behaviors for lucky wheel system"""

    def setUp(self):
        """Create test user, lucky wheel, and player wallet"""
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        self.user.is_verified = True
        self.user.save()

        # Create player wallet
        self.wallet, c = PlayerWallet.objects.get_or_create(player=self.user)

        # Create reward packages for wheel
        self.small_reward = RewardPackage.objects.create(
            name='Small Reward',
            reward_type=RewardPackage.RewardType.LUCKY_WHEEL
        )
        self.big_reward = RewardPackage.objects.create(
            name='Big Reward',
            reward_type=RewardPackage.RewardType.LUCKY_WHEEL
        )

        # Create lucky wheel
        self.lucky_wheel = LuckyWheel.objects.create(
            name='Fortune Wheel',
            cool_down=timedelta(hours=24)
        )

        # Create wheel sections
        self.section1 = LuckyWheelSection.objects.create(
            lucky_wheel=self.lucky_wheel,
            package=self.small_reward,
            chance=70  # 70% chance
        )
        self.section2 = LuckyWheelSection.objects.create(
            lucky_wheel=self.lucky_wheel,
            package=self.big_reward,
            chance=30  # 30% chance
        )

    def test_authenticated_user_can_view_lucky_wheel(self):
        """Authenticated users should be able to view the lucky wheel configuration"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('lucky-wheel-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Fortune Wheel')
        self.assertEqual(len(response.data['sections']), 2)

        # Check wheel sections include package details
        packages_in_wheel = [section['package']['name'] for section in response.data['sections']]
        self.assertIn('Small Reward', packages_in_wheel)
        self.assertIn('Big Reward', packages_in_wheel)

    def test_unauthenticated_user_cannot_view_lucky_wheel(self):
        """Unauthenticated users cannot access lucky wheel"""
        response = self.client.get(reverse('lucky-wheel-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_spin_lucky_wheel_when_eligible(self):
        """Users should be able to spin the wheel when not on cooldown"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('lucky-wheel-spin', kwargs={'pk': self.lucky_wheel.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return a reward package
        self.assertIn('name', response.data)
        self.assertIn('currency_items', response.data)
        self.assertIn('asset_items', response.data)

        # User's last spin time should be updated
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_lucky_wheel_spin)

    def test_user_cannot_spin_wheel_during_cooldown(self):
        """Users should not be able to spin the wheel during cooldown period"""
        # Set user's last spin to recent time (within cooldown)
        self.user.last_lucky_wheel_spin = timezone.now() - timedelta(hours=1)  # 1 hour ago, cooldown is 24h
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('lucky-wheel-spin', kwargs={'pk': self.lucky_wheel.id}))

        self.assertEqual(response.status_code, status.HTTP_425_TOO_EARLY)
        self.assertIn('error', response.data)

    def test_user_can_spin_wheel_after_cooldown_expires(self):
        """Users should be able to spin the wheel after cooldown expires"""
        # Set user's last spin to time before cooldown period
        self.user.last_lucky_wheel_spin = timezone.now() - timedelta(hours=25)  # 25 hours ago, cooldown is 24h
        self.user.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('lucky-wheel-spin', kwargs={'pk': self.lucky_wheel.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('name', response.data)

    def test_spinning_nonexistent_wheel_returns_404(self):
        """Spinning non-existent wheel should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('lucky-wheel-spin', kwargs={'pk': 99999}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_spinning_empty_wheel_returns_error(self):
        """Spinning wheel with no sections should return error"""
        # Create empty wheel
        empty_wheel = LuckyWheel.objects.create(
            name='Empty Wheel',
            cool_down=timedelta(hours=24)
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('lucky-wheel-spin', kwargs={'pk': empty_wheel.id}))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_spinning_inactive_wheel_returns_404(self):
        """Spinning inactive wheel should return 404"""
        # Create inactive wheel
        inactive_wheel = LuckyWheel.objects.create(
            name='Inactive Wheel',
            cool_down=timedelta(hours=24),
            is_active=False
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse('lucky-wheel-spin', kwargs={'pk': inactive_wheel.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_wheel_cooldown_information_is_included(self):
        """Lucky wheel response should include cooldown information"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('lucky-wheel-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cool_down', response.data)

    def test_wheel_shows_only_active_sections(self):
        """Lucky wheel should only show active sections"""
        # Create inactive section
        inactive_reward = RewardPackage.objects.create(
            name='Inactive Reward',
            reward_type=RewardPackage.RewardType.LUCKY_WHEEL,
            is_active=False
        )
        LuckyWheelSection.objects.create(
            lucky_wheel=self.lucky_wheel,
            package=inactive_reward,
            chance=50,
            is_active=False
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('lucky-wheel-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still only show 2 active sections
        self.assertEqual(len(response.data['sections']), 2)

        package_names = [section['package']['name'] for section in response.data['sections']]
        self.assertNotIn('Inactive Reward', package_names)

    def tearDown(self):
        """Clear cache after each test to avoid caching issues"""
        cache.clear()
