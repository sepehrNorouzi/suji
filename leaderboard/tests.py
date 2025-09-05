from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import timedelta

from user.models import NormalPlayer, GuestPlayer
from leaderboard.models import LeaderboardType, LeaderboardReward
from shop.models import RewardPackage, ShopConfiguration


class LeaderboardTypeViewSetTests(APITestCase):
    """Test LeaderboardTypeViewSet behaviors for leaderboard management and viewing"""

    def setUp(self):
        """Create test users, leaderboard types, and test data"""
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

        # Create rewards for leaderboards
        self.winner_reward = RewardPackage.objects.create(
            name='Winner Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )
        self.participant_reward = RewardPackage.objects.create(
            name='Participant Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )

        # Create active leaderboard types
        self.weekly_leaderboard = LeaderboardType.objects.create(
            name='Weekly Tournament',
            is_active=True,
            duration=timedelta(days=7),
            start_time=timezone.now() - timedelta(days=2)  # Started 2 days ago
        )

        self.monthly_leaderboard = LeaderboardType.objects.create(
            name='Monthly Championship',
            is_active=True,
            duration=timedelta(days=30),
            start_time=timezone.now() - timedelta(days=5)  # Started 5 days ago
        )

        self.infinite_leaderboard = LeaderboardType.objects.create(
            name='All Time Leaderboard',
            is_active=True,
            duration=None,  # Infinite duration
            start_time=timezone.now() - timedelta(days=100)
        )

        # Create inactive leaderboard (should not appear)
        self.inactive_leaderboard = LeaderboardType.objects.create(
            name='Inactive Tournament',
            is_active=False,
            duration=timedelta(days=7),
            start_time=timezone.now()
        )

        # Create rewards for leaderboard types
        LeaderboardReward.objects.create(
            leaderboard_type=self.weekly_leaderboard,
            reward=self.winner_reward,
            from_rank=1,
            to_rank=3
        )
        LeaderboardReward.objects.create(
            leaderboard_type=self.weekly_leaderboard,
            reward=self.participant_reward,
            from_rank=4,
            to_rank=10
        )

    def test_authenticated_user_can_list_active_leaderboard_types(self):
        """Authenticated users should see list of active leaderboard types"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)  # Only active leaderboards

        leaderboard_names = [lb['name'] for lb in response.data['results']]
        self.assertIn('Weekly Tournament', leaderboard_names)
        self.assertIn('Monthly Championship', leaderboard_names)
        self.assertIn('All Time Leaderboard', leaderboard_names)
        self.assertNotIn('Inactive Tournament', leaderboard_names)

    def test_unauthenticated_user_cannot_list_leaderboards(self):
        """Unauthenticated users cannot access leaderboards"""
        response = self.client.get(reverse('leaderboard-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_leaderboard_list_includes_time_information(self):
        """Leaderboard list should include timing information"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for leaderboard in response.data['results']:
            self.assertIn('start_time', leaderboard)
            self.assertIn('duration', leaderboard)
            self.assertIn('time_remaining', leaderboard)

            # Infinite leaderboard should have null time_remaining
            if leaderboard['name'] == 'All Time Leaderboard':
                self.assertIsNone(leaderboard['time_remaining'])

    def test_leaderboard_time_remaining_calculation_for_active_tournaments(self):
        """Active leaderboards should show reasonable time remaining"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find weekly tournament
        weekly = None
        for lb in response.data['results']:
            if lb['name'] == 'Weekly Tournament':
                weekly = lb
                break

        self.assertIsNotNone(weekly)
        self.assertIsNotNone(weekly['time_remaining'])
        # Should have some time remaining (started 2 days ago, runs for 7 days)

    def test_guest_user_can_access_leaderboards(self):
        """Guest users should also be able to access leaderboards"""
        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('leaderboard-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) > 0)

    def test_leaderboard_pagination_support(self):
        """Leaderboard list should support pagination"""
        # Create many leaderboard types
        for i in range(25):
            LeaderboardType.objects.create(
                name=f'Tournament {i}',
                is_active=True,
                duration=timedelta(days=7),
                start_time=timezone.now()
            )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('leaderboard-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertEqual(response.data['count'], 28)  # 3 original + 25 new

    def test_retrieving_inactive_leaderboard_returns_404(self):
        """Inactive leaderboards should not be accessible"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.inactive_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieving_nonexistent_leaderboard_returns_404(self):
        """Non-existent leaderboards should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': 99999}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # SAFE REDIS MOCKING TESTS
    @patch('leaderboard.models.LeaderboardType.get_leaderboard')
    def test_user_can_retrieve_leaderboard_with_rankings(self, mock_get_leaderboard):
        """Users should be able to retrieve leaderboard details with player rankings"""
        # Mock the complete leaderboard response at the model level
        mock_top_players = [
            {
                'id': self.other_user.id,
                'profile_name': 'OtherUser',
                'score': 1500,
                'rank': 1,
                'avatar': None,
                'username': 'other@example.com'
            },
            {
                'id': self.user.id,
                'profile_name': 'TestUser',
                'score': 1200,
                'rank': 2,
                'avatar': None,
                'username': 'user@example.com'
            },
            {
                'id': self.guest_user.id,
                'profile_name': 'guest-123',
                'score': 800,
                'rank': 3,
                'avatar': None,
                'username': 'guest-device-123'
            }
        ]

        mock_surrounding_players = [
            {
                'id': self.other_user.id,
                'profile_name': 'OtherUser',
                'score': 1500,
                'rank': 1,
                'avatar': None,
                'username': 'other@example.com'
            },
            {
                'id': self.user.id,
                'profile_name': 'TestUser',
                'score': 1200,
                'rank': 2,
                'avatar': None,
                'username': 'user@example.com'
            }
        ]

        mock_player_rank = (1, 1200.0)  # User is rank 2 (0-based index 1) with 1200 score

        mock_get_leaderboard.return_value = (
            mock_top_players,
            mock_surrounding_players,
            mock_player_rank
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include leaderboard metadata
        self.assertEqual(response.data['name'], 'Weekly Tournament')
        self.assertIn('duration', response.data)
        self.assertIn('start_time', response.data)

        # Should include ranking data
        self.assertIn('top_players', response.data)
        self.assertIn('surrounding_players', response.data)
        self.assertIn('player_rank', response.data)

        # Check player rank information
        self.assertEqual(response.data['player_rank']['rank'], 1)
        self.assertEqual(response.data['player_rank']['score'], 1200)

        # Top players should include player details
        self.assertTrue(len(response.data['top_players']) > 0)
        for player in response.data['top_players']:
            self.assertIn('profile_name', player)
            self.assertIn('score', player)
            self.assertIn('rank', player)

        # Verify mock was called with correct parameters
        mock_get_leaderboard.assert_called_once_with(self.user.id)

    @patch('leaderboard.models.LeaderboardType.get_leaderboard')
    def test_user_can_view_leaderboard_when_not_ranked(self, mock_get_leaderboard):
        """Users should be able to view leaderboard even when they're not ranked"""
        # Mock response for user not in leaderboard
        mock_top_players = [
            {
                'id': self.other_user.id,
                'profile_name': 'OtherUser',
                'score': 1500,
                'rank': 1,
                'avatar': None,
                'username': 'other@example.com'
            },
            {
                'id': self.guest_user.id,
                'profile_name': 'guest-123',
                'score': 800,
                'rank': 2,
                'avatar': None,
                'username': 'guest-device-123'
            }
        ]

        mock_surrounding_players = []  # User not ranked, so no surrounding players
        mock_player_rank = (None, 0.0)  # User not ranked

        mock_get_leaderboard.return_value = (
            mock_top_players,
            mock_surrounding_players,
            mock_player_rank
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('top_players', response.data)
        self.assertIn('player_rank', response.data)

        # Player rank should reflect unranked status
        self.assertIsNone(response.data['player_rank']['rank'])
        self.assertEqual(response.data['player_rank']['score'], 0)

    @patch('leaderboard.models.LeaderboardType.get_leaderboard')
    def test_leaderboard_handles_empty_rankings(self, mock_get_leaderboard):
        """Leaderboard should handle case when no players have scores"""
        # Mock empty leaderboard response
        mock_get_leaderboard.return_value = ([], [], (None, 0.0))

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['top_players']), 0)
        self.assertEqual(len(response.data['surrounding_players']), 0)

    @patch('leaderboard.models.LeaderboardType.get_leaderboard')
    def test_leaderboard_surrounding_players_feature(self, mock_get_leaderboard):
        """Leaderboard should show players around the user's rank"""
        # Create a scenario where user is in middle of leaderboard
        mock_top_players = []  # Empty top players for this test

        # Surrounding players (user in middle)
        mock_surrounding_players = [
            {
                'id': self.other_user.id,
                'profile_name': 'OtherUser',
                'score': 520,
                'rank': 48,
                'avatar': None,
                'username': 'other@example.com'
            },
            {
                'id': self.user.id,
                'profile_name': 'TestUser',
                'score': 500,
                'rank': 50,
                'avatar': None,
                'username': 'user@example.com'
            },
            {
                'id': self.guest_user.id,
                'profile_name': 'guest-123',
                'score': 480,
                'rank': 52,
                'avatar': None,
                'username': 'guest-device-123'
            }
        ]

        mock_player_rank = (49, 500.0)  # User is rank 50 (0-based index 49)

        mock_get_leaderboard.return_value = (
            mock_top_players,
            mock_surrounding_players,
            mock_player_rank
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['surrounding_players']), 3)

        # User should be in surrounding players
        user_in_surrounding = any(
            player['id'] == self.user.id
            for player in response.data['surrounding_players']
        )
        self.assertTrue(user_in_surrounding)

    @patch('leaderboard.models.LeaderboardType.get_leaderboard')
    def test_leaderboard_includes_complete_player_information(self, mock_get_leaderboard):
        """Leaderboard should include complete player information"""
        mock_top_players = [
            {
                'id': self.user.id,
                'profile_name': 'TestUser',
                'score': 1200,
                'rank': 1,
                'avatar': {'id': 1, 'config': {'color': 'blue'}},
                'username': 'user@example.com'
            }
        ]

        mock_get_leaderboard.return_value = (mock_top_players, [], (0, 1200.0))

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        player_data = response.data['top_players'][0]
        self.assertIn('id', player_data)
        self.assertIn('profile_name', player_data)
        self.assertIn('score', player_data)
        self.assertIn('rank', player_data)
        self.assertIn('avatar', player_data)
        self.assertIn('username', player_data)

    def test_leaderboard_detail_includes_metadata(self):
        """Leaderboard detail should include all necessary metadata"""
        # This test doesn't need Redis mocking as it's just checking basic metadata
        with patch('leaderboard.models.LeaderboardType.get_leaderboard') as mock_get_leaderboard:
            mock_get_leaderboard.return_value = ([], [], (None, 0.0))

            self.client.force_authenticate(user=self.user)

            response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Basic leaderboard info
            self.assertEqual(response.data['name'], 'Weekly Tournament')
            self.assertEqual(response.data['id'], self.weekly_leaderboard.id)
            self.assertIn('start_time', response.data)
            self.assertIn('duration', response.data)
            self.assertIn('time_remaining', response.data)

    def test_leaderboard_time_remaining_for_infinite_duration(self):
        """Infinite duration leaderboards should show null time remaining"""
        with patch('leaderboard.models.LeaderboardType.get_leaderboard') as mock_get_leaderboard:
            mock_get_leaderboard.return_value = ([], [], (None, 0.0))

            self.client.force_authenticate(user=self.user)

            response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.infinite_leaderboard.id}))

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsNone(response.data['time_remaining'])

    @patch('leaderboard.models.LeaderboardType.get_leaderboard')
    def test_leaderboard_handles_redis_errors_gracefully(self, mock_get_leaderboard):
        """Leaderboard should handle Redis errors gracefully"""
        # Simulate Redis connection error
        mock_get_leaderboard.side_effect = Exception("Redis connection failed")

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        # Should return 500 or handle gracefully, not crash the system
        self.assertIn(response.status_code, [status.HTTP_503_SERVICE_UNAVAILABLE, status.HTTP_200_OK])

    def test_leaderboard_endpoint_requires_authentication(self):
        """Leaderboard detail endpoint should require authentication"""
        response = self.client.get(reverse('leaderboard-detail', kwargs={'pk': self.weekly_leaderboard.id}))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def tearDown(self):
        """Clear cache after each test to avoid caching issues"""
        cache.clear()
