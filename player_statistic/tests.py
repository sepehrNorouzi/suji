from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status

from user.models import NormalPlayer, GuestPlayer
from player_statistic.models import PlayerLevel, PlayerStatistic
from shop.models import RewardPackage, ShopConfiguration


class PlayerLevelViewSetTests(APITestCase):
    """Test PlayerLevelViewSet behaviors for level system management"""

    def setUp(self):
        """Create test user and player levels"""
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        self.user.is_verified = True
        self.user.save()

        # Create reward packages for levels
        self.level1_reward = RewardPackage.objects.create(
            name='Level 1 Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )
        self.level5_reward = RewardPackage.objects.create(
            name='Level 5 Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )
        self.level10_reward = RewardPackage.objects.create(
            name='Level 10 Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )

        # Create player levels (ordered by start_xp)
        self.level1, c = PlayerLevel.objects.get_or_create(
            start_xp=0
        )
        self.level1.reward_package = self.level1_reward
        self.level1.save()

        self.level2 = PlayerLevel.objects.create(
            start_xp=100,
            reward=None  # Some levels might not have rewards
        )
        self.level3 = PlayerLevel.objects.create(
            start_xp=250,
            reward=self.level5_reward
        )
        self.level4 = PlayerLevel.objects.create(
            start_xp=500,
            reward=self.level10_reward
        )

        # Create inactive level (should not appear)
        self.inactive_level = PlayerLevel.objects.create(
            start_xp=1000,
            reward=None,
            is_active=False
        )

    def test_authenticated_user_can_list_active_player_levels(self):
        """Authenticated users should see list of active player levels ordered by XP"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-level-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)  # Only active levels

        # Should be ordered by start_xp
        self.assertEqual(response.data['results'][0]['start_xp'], 0)
        self.assertEqual(response.data['results'][1]['start_xp'], 100)
        self.assertEqual(response.data['results'][2]['start_xp'], 250)
        self.assertEqual(response.data['results'][3]['start_xp'], 500)

    def test_unauthenticated_user_cannot_list_player_levels(self):
        """Unauthenticated users cannot access player levels"""
        response = self.client.get(reverse('player-level-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_retrieve_player_level_details(self):
        """Authenticated users should be able to view player level details with rewards"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-level-detail', kwargs={'pk': self.level3.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['start_xp'], 250)
        self.assertEqual(response.data['index'], 3)  # Third level (0-based counting + 1)

        # Should include reward details
        self.assertIn('reward', response.data)
        self.assertEqual(response.data['reward']['name'], 'Level 5 Reward')

    def test_player_level_without_reward_shows_null_reward(self):
        """Player levels without rewards should show null for reward field"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-level-detail', kwargs={'pk': self.level2.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['start_xp'], 100)
        self.assertIsNone(response.data['reward'])

    def test_retrieving_inactive_player_level_returns_404(self):
        """Inactive player levels should not be accessible"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-level-detail', kwargs={'pk': self.inactive_level.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieving_nonexistent_player_level_returns_404(self):
        """Non-existent player levels should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-level-detail', kwargs={'pk': 99999}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_player_levels_are_paginated(self):
        """Player levels list should support pagination"""
        # Create many player levels
        for i in range(25):
            PlayerLevel.objects.create(start_xp=1000 + (i * 100))

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('player-level-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertEqual(response.data['count'], 29)  # 4 original + 25 new

    def test_player_level_index_calculation_is_correct(self):
        """Player level index should be calculated correctly based on XP ordering"""
        self.client.force_authenticate(user=self.user)

        # Check first level (lowest XP)
        response = self.client.get(reverse('player-level-detail', kwargs={'pk': self.level1.id}))
        self.assertEqual(response.data['index'], 1)

        # Check last level (highest XP)
        response = self.client.get(reverse('player-level-detail', kwargs={'pk': self.level4.id}))
        self.assertEqual(response.data['index'], 4)

    def test_player_level_response_includes_all_required_fields(self):
        """Player level response should include all necessary fields"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-level-detail', kwargs={'pk': self.level3.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('start_xp', response.data)
        self.assertIn('index', response.data)
        self.assertIn('reward', response.data)


class PlayerStatisticViewSetTests(APITestCase):
    """Test PlayerStatisticViewSet behaviors for player statistics management"""

    def setUp(self):
        """Create test users and set up player statistics"""
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

        # Create player levels for testing
        self.level1 = PlayerLevel.objects.create(start_xp=0)
        self.level2 = PlayerLevel.objects.create(start_xp=100)
        self.level3 = PlayerLevel.objects.create(start_xp=300)
        self.level3 = PlayerLevel.objects.create(start_xp=450)

        # Update some player stats for testing
        self.user.stats.score = 1500
        self.user.stats.xp = 250
        self.user.stats.cup = 5
        self.user.stats.save()

    def test_authenticated_user_can_view_own_statistics(self):
        """When user requests statistics list, they get their own stats"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.stats.id)
        self.assertEqual(response.data['score'], 1500)
        self.assertEqual(response.data['xp'], 250)
        self.assertEqual(response.data['cup'], 5)

        # Should include level information
        self.assertIn('level', response.data)
        self.assertEqual(response.data['level']['start_xp'], 100)  # Level 2 (100-299 XP)

        # Should include player information
        self.assertIn('player', response.data)
        self.assertEqual(response.data['player']['profile_name'], 'TestUser')

    def test_guest_user_can_view_own_statistics(self):
        """Guest users should also be able to view their own statistics"""
        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['score'], 0)  # Default values
        self.assertEqual(response.data['xp'], 0)
        self.assertEqual(response.data['cup'], 0)

    def test_unauthenticated_user_cannot_view_statistics(self):
        """Unauthenticated users cannot access player statistics"""
        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_retrieve_other_player_statistics(self):
        """Authenticated users should be able to view other players' statistics"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-statistic-detail', kwargs={'pk': self.other_user.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['player']['id'], self.other_user.id)
        self.assertEqual(response.data['player']['profile_name'], 'OtherUser')

    def test_retrieving_nonexistent_player_statistics_returns_404(self):
        """Requesting statistics for non-existent player should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-statistic-detail', kwargs={'pk': 99999}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_player_statistics_automatically_created_for_new_players(self):
        """Player statistics should be automatically created when new players are created"""
        new_user = NormalPlayer.objects.create_user(
            email='newuser2@example.com',
            password='password123'
        )

        # Stats should be automatically created
        self.assertTrue(hasattr(new_user, 'stats'))
        self.assertEqual(new_user.stats.score, 0)
        self.assertEqual(new_user.stats.xp, 0)
        self.assertEqual(new_user.stats.cup, 0)

    def test_player_level_updates_based_on_xp(self):
        """Player level should be calculated correctly based on XP"""
        self.client.force_authenticate(user=self.user)

        # User has 250 XP, should be level 2 (100-299 XP range)
        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['level']['start_xp'], 100)

    def test_player_statistics_include_all_required_fields(self):
        """Player statistics response should include all necessary fields"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Core stats fields
        self.assertIn('id', response.data)
        self.assertIn('score', response.data)
        self.assertIn('xp', response.data)
        self.assertIn('cup', response.data)

        # Related objects
        self.assertIn('level', response.data)
        self.assertIn('player', response.data)

        # Level details
        self.assertIn('id', response.data['level'])
        self.assertIn('start_xp', response.data['level'])
        self.assertIn('index', response.data['level'])

        # Player details
        self.assertIn('id', response.data['player'])
        self.assertIn('profile_name', response.data['player'])

    def test_player_statistics_reflect_current_data(self):
        """Player statistics should reflect the most current data"""
        # Update user stats directly
        stats = self.user.stats
        stats.score = 2000
        stats.xp = 350  # Should put them in level 3
        stats.cup = 10
        stats.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['score'], 2000)
        self.assertEqual(response.data['xp'], 350)
        self.assertEqual(response.data['cup'], 10)
        self.assertEqual(response.data['level']['start_xp'], 300)  # Level 3

    def test_guest_player_statistics_work_correctly(self):
        """Guest players should have functional statistics"""
        # Update guest stats
        self.guest_user.stats.score = 500
        self.guest_user.stats.save()

        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['score'], 500)
        self.assertIn('player', response.data)

    def test_retrieving_guest_player_statistics_by_id_works(self):
        """Other users should be able to view guest player statistics by ID"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('player-statistic-detail', kwargs={'pk': self.guest_user.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['player']['id'], self.guest_user.id)

    def test_level_calculation_handles_edge_cases(self):
        """Level calculation should handle edge cases correctly"""
        # Test player with 0 XP (should be level 1)
        zero_xp_user = NormalPlayer.objects.create_user(
            email='zeroxp@example.com',
            password='password123'
        )

        self.client.force_authenticate(user=zero_xp_user)
        response = self.client.get(reverse('player-statistic-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['xp'], 0)
        self.assertEqual(response.data['level']['start_xp'], 0)  # Level 1

    def tearDown(self):
        """Clear cache after each test to avoid singleton caching issues"""
        cache.clear()
