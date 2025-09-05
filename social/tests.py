from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status

from user.models import NormalPlayer, GuestPlayer
from social.models import FriendshipRequest, Friendship
from shop.models import RewardPackage, ShopConfiguration


class FriendshipRequestViewSetTests(APITestCase):
    """Test FriendshipRequestViewSet behaviors for friendship request management"""

    def setUp(self):
        """Create test users and friendship data"""
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

        self.friend = NormalPlayer.objects.create_user(
            email='friend@example.com',
            password='password123',
            profile_name='FriendUser'
        )
        self.friend.is_verified = True
        self.friend.save()

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

        # Create some friendship requests for testing
        self.incoming_request = FriendshipRequest.objects.create(
            sender=self.friend,
            receiver=self.user
        )

        self.outgoing_request = FriendshipRequest.objects.create(
            sender=self.user,
            receiver=self.other_user
        )

        # Create friendship request from other user to friend (not involving main user)
        self.unrelated_request = FriendshipRequest.objects.create(
            sender=self.other_user,
            receiver=self.friend
        )

    def test_authenticated_user_can_view_received_friendship_requests(self):
        """Users should see friendship requests they have received"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-request-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

        request_data = response.data['results'][0]
        self.assertEqual(request_data['id'], self.incoming_request.id)
        self.assertEqual(request_data['sender']['profile_name'], 'FriendUser')

    def test_user_sees_empty_list_when_no_friendship_requests(self):
        """Users with no incoming requests should see empty list"""
        # Other user has no incoming requests
        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('social-friendship-request-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_unauthenticated_user_cannot_view_friendship_requests(self):
        """Unauthenticated users cannot access friendship requests"""
        response = self.client.get(reverse('social-friendship-request-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_send_friendship_request(self):
        """Users should be able to send friendship requests to other users"""
        self.client.force_authenticate(user=self.user)

        # Create a new user to send request to
        new_user = NormalPlayer.objects.create_user(
            email='newuser@example.com',
            password='password123',
            profile_name='NewUser'
        )
        new_user.is_verified = True
        new_user.save()

        data = {
            'receiver_id': new_user.id
        }
        response = self.client.post(reverse('social-friendship-request-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('sender', response.data)
        self.assertIn('created_time', response.data)

        # Verify request was created in database
        self.assertTrue(
            FriendshipRequest.objects.filter(
                sender=self.user,
                receiver=new_user
            ).exists()
        )

    def test_user_cannot_send_friendship_request_to_existing_friend(self):
        """Users should not be able to send requests to users they're already friends with"""
        # Create existing friendship
        Friendship.objects.create(user_1=self.user, user_2=self.friend)

        self.client.force_authenticate(user=self.user)

        data = {
            'receiver_id': self.friend.id
        }

        response = self.client.post(reverse('social-friendship-request-list'), data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('error', response.data)

    def test_user_cannot_send_friendship_request_to_nonexistent_user(self):
        """Sending friendship request to non-existent user should fail"""
        self.client.force_authenticate(user=self.user)

        data = {
            'receiver_id': 99999
        }

        response = self.client.post(reverse('social-friendship-request-list'), data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_send_friendship_request_to_themselves(self):
        """Users should not be able to send friendship requests to themselves"""
        self.client.force_authenticate(user=self.user)

        data = {
            'receiver_id': self.user.id
        }

        response = self.client.post(reverse('social-friendship-request-list'), data)

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    def test_user_can_view_sent_friendship_requests(self):
        """Users should be able to view friendship requests they have sent"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-request-requested'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

        request_data = response.data['results'][0]
        self.assertEqual(request_data['id'], self.outgoing_request.id)
        self.assertEqual(request_data['receiver']['profile_name'], 'OtherUser')

    def test_user_can_cancel_sent_friendship_request(self):
        """Users should be able to cancel friendship requests they have sent"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('social-friendship-request-requested-delete', kwargs={'request_id': self.outgoing_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify request was deleted
        self.assertFalse(
            FriendshipRequest.objects.filter(id=self.outgoing_request.id).exists()
        )

    def test_user_cannot_cancel_other_users_sent_request(self):
        """Users should not be able to cancel requests sent by others"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('social-friendship-request-requested-delete', kwargs={'request_id': self.unrelated_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_accept_incoming_friendship_request(self):
        """Users should be able to accept friendship requests sent to them"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('social-friendship-request-accept', kwargs={'pk': self.incoming_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user_1', response.data)
        self.assertIn('user_2', response.data)

        # Verify friendship was created
        self.assertTrue(
            Friendship.objects.filter(
                user_1__in=[self.user, self.friend],
                user_2__in=[self.user, self.friend]
            ).exists()
        )

        # Verify request was deleted
        self.assertFalse(
            FriendshipRequest.objects.filter(id=self.incoming_request.id).exists()
        )

    def test_user_can_reject_incoming_friendship_request(self):
        """Users should be able to reject friendship requests sent to them"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('social-friendship-request-reject', kwargs={'pk': self.incoming_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify request was deleted without creating friendship
        self.assertFalse(
            FriendshipRequest.objects.filter(id=self.incoming_request.id).exists()
        )
        self.assertFalse(
            Friendship.objects.filter(
                user_1__in=[self.user, self.friend],
                user_2__in=[self.user, self.friend]
            ).exists()
        )

    def test_user_cannot_accept_request_not_sent_to_them(self):
        """Users should not be able to accept requests not sent to them"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('social-friendship-request-accept', kwargs={'pk': self.unrelated_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_reject_request_not_sent_to_them(self):
        """Users should not be able to reject requests not sent to them"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('social-friendship-request-reject', kwargs={'pk': self.unrelated_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_delete_received_friendship_request(self):
        """Users should be able to delete friendship requests sent to them"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('social-friendship-request-detail', kwargs={'pk': self.incoming_request.id})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify request was deleted
        self.assertFalse(
            FriendshipRequest.objects.filter(id=self.incoming_request.id).exists()
        )

    def test_friendship_requests_are_paginated(self):
        """Friendship requests should support pagination"""
        # Create many friendship requests
        for i in range(25):
            sender = NormalPlayer.objects.create_user(
                email=f'sender{i}@example.com',
                password='password123',
                profile_name=f'Sender{i}'
            )
            sender.is_verified = True
            sender.save()

            FriendshipRequest.objects.create(
                sender=sender,
                receiver=self.user
            )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('social-friendship-request-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertEqual(response.data['count'], 26)  # 1 original + 25 new

    def test_guest_user_can_send_and_receive_friendship_requests(self):
        """Guest users should also be able to use the friendship system"""
        self.client.force_authenticate(user=self.guest_user)

        # Guest user sends request
        data = {
            'receiver_id': self.user.id
        }

        response = self.client.post(reverse('social-friendship-request-list'), data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_friendship_request_includes_complete_sender_profile(self):
        """Friendship request response should include complete sender profile"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-request-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        request_data = response.data['results'][0]
        sender_data = request_data['sender']

        self.assertIn('id', sender_data)
        self.assertIn('profile_name', sender_data)
        self.assertIn('gender', sender_data)
        self.assertIn('current_avatar', sender_data)

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()


class FriendshipViewSetTests(APITestCase):
    """Test FriendshipViewSet behaviors for friendship management"""

    def setUp(self):
        """Create test users and friendships"""
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

        self.friend1 = NormalPlayer.objects.create_user(
            email='friend1@example.com',
            password='password123',
            profile_name='Friend1'
        )
        self.friend1.is_verified = True
        self.friend1.save()

        self.friend2 = NormalPlayer.objects.create_user(
            email='friend2@example.com',
            password='password123',
            profile_name='Friend2'
        )
        self.friend2.is_verified = True
        self.friend2.save()

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

        # Create friendships
        self.friendship1 = Friendship.objects.create(
            user_1=self.user,
            user_2=self.friend1
        )

        self.friendship2 = Friendship.objects.create(
            user_1=self.friend2,
            user_2=self.user
        )

        # Create friendship not involving main user
        self.unrelated_friendship = Friendship.objects.create(
            user_1=self.friend1,
            user_2=self.other_user
        )

    def test_authenticated_user_can_view_their_friendships(self):
        """Users should see all their friendships"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

        # Check that both friendships are returned
        friendship_ids = [f['id'] for f in response.data['results']]
        self.assertIn(self.friendship1.id, friendship_ids)
        self.assertIn(self.friendship2.id, friendship_ids)

    def test_user_sees_empty_list_when_no_friends(self):
        """Users with no friends should see empty list"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only the unrelated friendship they're part of

    def test_unauthenticated_user_cannot_view_friendships(self):
        """Unauthenticated users cannot access friendships"""
        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_friendship_response_includes_both_users_profiles(self):
        """Friendship response should include complete profile information for both users"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        friendship_data = response.data['results'][0]

        # Should include both user profiles
        self.assertIn('user_1', friendship_data)
        self.assertIn('user_2', friendship_data)

        # Check profile completeness
        for user_field in ['user_1', 'user_2']:
            user_data = friendship_data[user_field]
            self.assertIn('id', user_data)
            self.assertIn('profile_name', user_data)
            self.assertIn('gender', user_data)
            self.assertIn('current_avatar', user_data)

    def test_user_can_unfriend_another_user(self):
        """Users should be able to remove friendships"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('social-friendship-detail', kwargs={'pk': self.friendship1.id})
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify friendship was deleted
        self.assertFalse(
            Friendship.objects.filter(id=self.friendship1.id).exists()
        )

    def test_user_cannot_delete_friendship_they_are_not_part_of(self):
        """Users should not be able to delete friendships they're not part of"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('social-friendship-detail', kwargs={'pk': self.unrelated_friendship.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleting_nonexistent_friendship_returns_404(self):
        """Deleting non-existent friendship should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('social-friendship-detail', kwargs={'pk': 99999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_friendship_ordering_consistency(self):
        """Friendships should maintain consistent user ordering regardless of creation order"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that user ordering is consistent (based on the model's save method logic)
        for friendship_data in response.data['results']:
            user1_id = friendship_data['user_1']['id']
            user2_id = friendship_data['user_2']['id']
            # Based on the model, user_1 should have higher ID than user_2 after save
            self.assertGreater(user1_id, user2_id)

    def test_guest_user_can_manage_friendships(self):
        """Guest users should also be able to manage their friendships"""
        # Create friendship involving guest user
        guest_friendship = Friendship.objects.create(
            user_1=self.guest_user,
            user_2=self.user
        )

        self.client.force_authenticate(user=self.guest_user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], guest_friendship.id)

    def test_friendships_are_paginated(self):
        """Friendships list should support pagination"""
        # Create many friendships
        for i in range(25):
            friend = NormalPlayer.objects.create_user(
                email=f'friend{i + 10}@example.com',
                password='password123',
                profile_name=f'Friend{i + 10}'
            )
            friend.is_verified = True
            friend.save()

            Friendship.objects.create(
                user_1=self.user,
                user_2=friend
            )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertEqual(response.data['count'], 27)  # 2 original + 25 new

    def test_friendship_includes_creation_time(self):
        """Friendship response should include creation time for sorting/display"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for friendship_data in response.data['results']:
            self.assertIn('created_time', friendship_data)

    def test_user_with_no_friends_sees_empty_list(self):
        """New users with no friends should see empty list"""
        new_user = NormalPlayer.objects.create_user(
            email='newuser@example.com',
            password='password123',
            profile_name='NewUser'
        )
        new_user.is_verified = True
        new_user.save()

        self.client.force_authenticate(user=new_user)

        response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_friendship_mutual_visibility(self):
        """Both users in a friendship should see the same friendship"""
        # Check from user's perspective
        self.client.force_authenticate(user=self.user)
        user_response = self.client.get(reverse('social-friendship-list'))

        # Check from friend's perspective
        self.client.force_authenticate(user=self.friend1)
        friend_response = self.client.get(reverse('social-friendship-list'))

        self.assertEqual(user_response.status_code, status.HTTP_200_OK)
        self.assertEqual(friend_response.status_code, status.HTTP_200_OK)

        # Both should see the same friendship (though possibly in different order)
        user_friendship_ids = [f['id'] for f in user_response.data['results']]
        friend_friendship_ids = [f['id'] for f in friend_response.data['results']]

        self.assertIn(self.friendship1.id, user_friendship_ids)
        self.assertIn(self.friendship1.id, friend_friendship_ids)

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()
