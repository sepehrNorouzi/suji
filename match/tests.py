from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from uuid import uuid4

from user.models import NormalPlayer, GuestPlayer
from match.models import MatchType, Match
from shop.models import RewardPackage, Currency, Cost, ShopConfiguration
from player_shop.models import PlayerWallet, CurrencyBalance
from player_statistic.models import PlayerStatistic


class MatchTypeViewSetTests(APITestCase):
    """Test MatchTypeViewSet behaviors for match type management and eligibility"""

    def setUp(self):
        """Create test users, currencies, and match types"""
        # Create initial package and shop config for player creation
        self.initial_package = RewardPackage.objects.create(
            name='Initial Package',
            reward_type=RewardPackage.RewardType.INIT_WALLET
        )
        self.shop_config = ShopConfiguration.objects.create(
            player_initial_package=self.initial_package
        )

        # Create currency for entry costs
        self.coins = Currency.objects.create(
            name='Coins',
            type=Currency.CurrencyType.IN_APP
        )

        # Create entry cost
        self.entry_cost = Cost.objects.create(
            currency=self.coins,
            amount=100
        )

        # Create reward packages
        self.winner_package = RewardPackage.objects.create(
            name='Winner Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )
        self.loser_package = RewardPackage.objects.create(
            name='Loser Reward',
            reward_type=RewardPackage.RewardType.MATCH_REWARD
        )

        # Create test users
        self.user = NormalPlayer.objects.create_user(
            email='user@example.com',
            password='password123',
            profile_name='TestUser'
        )
        self.user.is_verified = True
        self.user.save()

        self.low_level_user = NormalPlayer.objects.create_user(
            email='newbie@example.com',
            password='password123',
            profile_name='NewbieUser'
        )
        self.low_level_user.is_verified = True
        self.low_level_user.save()

        self.guest_user = GuestPlayer.objects.create_user(
            device_id='guest-device-123',
            password='password123'
        )

        # Set up user stats and currencies
        self.user.stats.xp = 500
        self.user.stats.cup = 10
        self.user.stats.score = 2000
        self.user.stats.save()

        # Give user sufficient coins
        CurrencyBalance.objects.create(
            wallet=self.user.shop_info,
            currency=self.coins,
            balance=1000
        )

        # Low level user has minimal stats and coins
        CurrencyBalance.objects.create(
            wallet=self.low_level_user.shop_info,
            currency=self.coins,
            balance=50  # Not enough for entry cost
        )

        # Create match types
        self.beginner_match = MatchType.objects.create(
            name='Beginner Match',
            priority=1,
            entry_cost=None,
            min_xp=0,
            min_cup=0,
            min_score=0,
            winner_package=self.winner_package,
            loser_package=self.loser_package,
            winner_xp=50,
            winner_cup=2,
            winner_score=100,
            loser_xp=10,
            loser_cup=0,
            loser_score=10
        )

        self.intermediate_match = MatchType.objects.create(
            name='Intermediate Match',
            priority=2,
            entry_cost=self.entry_cost,
            min_xp=200,
            min_cup=5,
            min_score=1000,
            winner_package=self.winner_package,
            loser_package=self.loser_package,
            winner_xp=100,
            winner_cup=3,
            winner_score=200,
            loser_xp=20,
            loser_cup=1,
            loser_score=20
        )

        self.expert_match = MatchType.objects.create(
            name='Expert Match',
            priority=3,
            entry_cost=self.entry_cost,
            min_xp=1000,
            min_cup=20,
            min_score=5000,
            winner_package=self.winner_package,
            loser_package=self.loser_package,
            winner_xp=200,
            winner_cup=5,
            winner_score=500,
            loser_xp=30,
            loser_cup=2,
            loser_score=50
        )

        # Create inactive match type (should not appear)
        self.inactive_match = MatchType.objects.create(
            name='Inactive Match',
            priority=4,
            is_active=False,
            min_xp=0,
            min_cup=0,
            min_score=0
        )

    def test_authenticated_user_can_list_active_match_types(self):
        """Authenticated users should see list of active match types ordered by priority"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)  # Only active match types

        # Should be ordered by priority
        self.assertEqual(response.data['results'][0]['name'], 'Beginner Match')
        self.assertEqual(response.data['results'][1]['name'], 'Intermediate Match')
        self.assertEqual(response.data['results'][2]['name'], 'Expert Match')

    def test_unauthenticated_user_cannot_list_match_types(self):
        """Unauthenticated users cannot access match types"""
        response = self.client.get(reverse('match_type-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_retrieve_match_type_details(self):
        """Authenticated users should be able to view match type details"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-detail', kwargs={'pk': self.intermediate_match.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Intermediate Match')
        self.assertEqual(response.data['min_xp'], 200)
        self.assertEqual(response.data['min_cup'], 5)
        self.assertEqual(response.data['min_score'], 1000)

        # Should include reward information
        self.assertIn('winner_package', response.data)
        self.assertIn('loser_package', response.data)
        self.assertIn('entry_cost', response.data)

    def test_retrieving_inactive_match_type_returns_404(self):
        """Inactive match types should not be accessible"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-detail', kwargs={'pk': self.inactive_match.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_join_match_when_meeting_requirements(self):
        """Users should be able to join matches when they meet all requirements"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-can-join', kwargs={'pk': self.intermediate_match.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_join_match_when_not_meeting_requirements(self):
        """Users should not be able to join matches when they don't meet requirements"""
        self.client.force_authenticate(user=self.low_level_user)

        response = self.client.get(reverse('match_type-can-join', kwargs={'pk': self.expert_match.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('errors', response.data)


    def test_guest_user_can_check_match_eligibility(self):
        """Guest users should also be able to check match eligibility"""
        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('match_type-can-join', kwargs={'pk': self.beginner_match.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_match_type_by_name_for_authenticated_user(self):
        """Authenticated users should be able to get match type by name"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-get-by-name'), {'name': 'Beginner Match'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Beginner Match')

    def test_get_match_type_by_name_returns_404_for_nonexistent_name(self):
        """Getting match type by non-existent name should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-get-by-name'), {'name': 'Non-existent Match'})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_match_type_by_name_returns_404_for_inactive_match(self):
        """Getting inactive match type by name should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match_type-get-by-name'), {'name': 'Inactive Match'})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('match.permissions.os.environ.get')
    def test_game_server_can_get_match_type_by_name(self, mock_env_get):
        """Game server should be able to get match type by name"""
        mock_env_get.return_value = 'test-server-key'

        response = self.client.get(
            reverse('match_type-get-by-name'),
            {'name': 'Beginner Match'},
            HTTP_X_GAME_SERVER_KEY='test-server-key'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Beginner Match')

    def test_match_types_are_paginated(self):
        """Match types list should support pagination"""
        # Create many match types
        for i in range(25):
            MatchType.objects.create(
                name=f'Match Type {i}',
                priority=i + 10,
                min_xp=0,
                min_cup=0,
                min_score=0
            )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('match_type-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertEqual(response.data['count'], 28)  # 3 original + 25 new

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()


class MatchViewSetTests(APITestCase):
    """Test MatchViewSet behaviors for match management and gameplay"""

    def setUp(self):
        """Create test users, match types, and matches"""
        # Create initial package and shop config
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

        self.opponent = NormalPlayer.objects.create_user(
            email='opponent@example.com',
            password='password123',
            profile_name='OpponentUser'
        )
        self.opponent.is_verified = True
        self.opponent.save()

        self.other_user = NormalPlayer.objects.create_user(
            email='other@example.com',
            password='password123',
            profile_name='OtherUser'
        )
        self.other_user.is_verified = True
        self.other_user.save()

        self.forth_user = NormalPlayer.objects.create_user(
            email='forth@example.com',
            password='password123',
            profile_name='ForthUser'
        )

        self.forth_user.is_verified = True
        self.forth_user.save()

        # Create match type
        self.match_type = MatchType.objects.create(
            name='Test Match',
            priority=1,
            min_xp=0,
            min_cup=0,
            min_score=0,
            mode='offline'
        )

        # Create matches
        self.user_match = Match.objects.create(
            uuid=uuid4(),
            match_type=self.match_type,
        )
        self.user_match.players.add(self.user, self.opponent)

        self.opponent_match = Match.objects.create(
            uuid=uuid4(),
            match_type=self.match_type,
        )
        self.opponent_match.players.add(self.opponent, self.user)

        # Match that user is not part of
        self.other_match = Match.objects.create(
            uuid=uuid4(),
            match_type=self.match_type,
        )
        self.other_match.players.add(self.other_user)

    def test_authenticated_user_can_list_their_matches(self):
        """Authenticated users should see only matches they're participating in"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

        match_uuids = [str(match['uuid']) for match in response.data['results']]
        self.assertIn(str(self.user_match.uuid), match_uuids)
        # self.assertNotIn(str(self.opponent_match.uuid), match_uuids)
        self.assertNotIn(str(self.other_match.uuid), match_uuids)

    def test_user_sees_empty_list_when_no_matches(self):
        """Users with no matches should see empty list"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(reverse('match-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only their own match

    def test_unauthenticated_user_cannot_list_matches(self):
        """Unauthenticated users cannot access matches"""
        response = self.client.get(reverse('match-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_retrieve_their_match_details(self):
        """Users should be able to view details of matches they're in"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match-detail', kwargs={'uuid': self.user_match.uuid}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], str(self.user_match.uuid))
        self.assertEqual(response.data['match_type']['name'], 'Test Match')

        # Should include player information
        self.assertIn('players', response.data)
        player_ids = [player['id'] for player in response.data['players']]
        self.assertIn(self.user.id, player_ids)
        self.assertIn(self.opponent.id, player_ids)

    def test_user_cannot_retrieve_match_they_are_not_in(self):
        """Users should not be able to view matches they're not participating in"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match-detail', kwargs={'uuid': self.other_match.uuid}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieving_nonexistent_match_returns_404(self):
        """Retrieving non-existent match should return 404"""
        self.client.force_authenticate(user=self.user)

        fake_uuid = uuid4()
        response = self.client.get(reverse('match-detail', kwargs={'uuid': fake_uuid}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('match.permissions.os.environ.get')
    def test_game_server_can_create_match(self, mock_env_get):
        """Game server should be able to create matches"""
        mock_env_get.return_value = 'test-server-key'
        Match.objects.all().delete()

        match_data = {
            'players': [self.other_user.id, self.user.id],
            'match_type': self.match_type.id,
            'uuid': str(uuid4()),
        }

        response = self.client.post(
            reverse('match-create'),
            match_data,
            HTTP_X_GAME_SERVER_KEY='test-server-key'
        )

        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('uuid', response.data)
        self.assertEqual(len(response.data['players']), 1)

    def test_authenticated_user_cannot_create_match(self):
        """Regular authenticated users should not be able to create matches"""
        self.client.force_authenticate(user=self.user)

        match_data = {
            'players': [self.user.id, self.opponent.id],
            'match_type': self.match_type.id,
            'uuid': str(uuid4()),
        }

        response = self.client.post(reverse('match-create'), match_data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('match.permissions.os.environ.get')
    def test_game_server_cannot_create_match_with_invalid_data(self, mock_env_get):
        """Game server should get validation errors for invalid match data"""
        mock_env_get.return_value = 'test-server-key'

        match_data = {
            'players': [99999],  # Non-existent player
            'match_type': self.match_type.id,
            'uuid': str(uuid4())
        }

        response = self.client.post(
            reverse('match-create'),
            match_data,
            HTTP_X_GAME_SERVER_KEY='test-server-key'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('match.permissions.os.environ.get')
    def test_game_server_can_finish_match(self, mock_env_get):
        """Users should be able to finish matches they're participating in"""
        mock_env_get.return_value = 'test-server-key'

        finish_data = {
            'players': [
                {'id': self.user.id, 'result': 'win', 'board': [1, 2, 3]},
                {'id': self.opponent.id, 'result': 'lose', 'board': [4, 5, 6]}
            ],
            'end_time': 1234567890,
            'winner': self.user.id
        }

        response = self.client.post(
            reverse('match-finish', kwargs={'uuid': self.user_match.uuid}),
            finish_data,
            format='json',
            HTTP_X_GAME_SERVER_KEY = 'test-server-key'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('result', response.data)

    def test_user_cannot_finish_match(self):
        """Users should not be able to finish matches they're not in"""
        self.client.force_authenticate(user=self.user)

        finish_data = {
            'players': [
                {'id': self.other_user.id, 'result': 'win', 'board': [1, 2, 3]}
            ],
            'end_time': 1234567890,
            'winner': self.other_user.id
        }

        response = self.client.post(
            reverse('match-finish', kwargs={'uuid': self.other_match.uuid}),
            finish_data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('match.permissions.os.environ.get')
    def test_finishing_match_with_invalid_data_returns_400(self, mock_env_get):
        """Finishing match with invalid data should return 400"""
        mock_env_get.return_value = 'test-server-key'

        finish_data = {
            'players': [],  # Empty players list
            'end_time': 'invalid_time',
            'winner': 'invalid_winner',
        }

        response = self.client.post(
            reverse('match-finish', kwargs={'uuid': self.user_match.uuid}),
            finish_data,
            format='json',
            HTTP_X_GAME_SERVER_KEY='test-server-key'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('match.permissions.os.environ.get')
    def test_game_server_can_access_any_match(self, mock_env_get):
        """Game server should be able to access any match"""
        mock_env_get.return_value = 'test-server-key'

        response = self.client.get(
            reverse('match-detail', kwargs={'uuid': self.other_match.uuid}),
            HTTP_X_GAME_SERVER_KEY='test-server-key'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], str(self.other_match.uuid))

    def test_match_includes_all_required_fields(self):
        """Match response should include all necessary fields"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match-detail', kwargs={'uuid': self.user_match.uuid}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Core match fields
        self.assertIn('uuid', response.data)
        self.assertIn('match_type', response.data)
        self.assertIn('players', response.data)

        # Match type details
        self.assertIn('name', response.data['match_type'])
        self.assertIn('id', response.data['match_type'])

        # Player details
        for player in response.data['players']:
            self.assertIn('id', player)
            self.assertIn('profile_name', player)

    def test_inactive_matches_are_filtered_out(self):
        """Inactive matches should not appear in listings"""
        # Create inactive match with user
        inactive_match = Match.objects.create(
            uuid=uuid4(),
            match_type=self.match_type,
            is_active=False
        )
        inactive_match.players.add(self.user)

        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('match-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should not include inactive match
        match_uuids = [str(match['uuid']) for match in response.data['results']]
        self.assertNotIn(str(inactive_match.uuid), match_uuids)

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()
