from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from user.models import NormalPlayer, GuestPlayer, SupporterPlayerInfo, VipPlayer

User = get_user_model()


class NormalPlayerAuthViewTests(APITestCase):
    """Test NormalPlayer authentication behaviors"""

    def setUp(self):
        """Clear cache and email outbox before each test"""
        cache.clear()
        mail.outbox = []

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    # SIGNUP TESTS
    def test_signup_with_valid_data_creates_user_and_sends_email(self):
        """When valid signup data is provided, user is created and verification email is sent"""
        data = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'profile_name': 'TestUser',
            'first_name': 'Test',
            'last_name': 'User'
        }

        response = self.client.post('/api/user/auth/player/signup/', data)

        # User should be created but not verified
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)

        # Check user exists in database
        user = NormalPlayer.objects.get(email='test@example.com')
        self.assertFalse(user.is_verified)
        self.assertEqual(user.profile_name, 'TestUser')

        # Verification email should be sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('test@example.com', mail.outbox[0].to)

    def test_signup_with_duplicate_email_returns_error(self):
        """When email already exists, signup should fail"""
        # Create existing user
        NormalPlayer.objects.create_user(
            email='existing@example.com',
            password='password123'
        )

        data = {
            'email': 'existing@example.com',
            'password': 'newpassword123'
        }

        response = self.client.post('/api/user/auth/player/signup/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_signup_with_invalid_email_returns_validation_error(self):
        """When invalid email format is provided, validation error is returned"""
        data = {
            'email': 'invalid-email',
            'password': 'testpassword123'
        }

        response = self.client.post('/api/user/auth/player/signup/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_without_required_fields_returns_validation_error(self):
        """When required fields are missing, validation error is returned"""
        data = {
            'email': 'test@example.com'
            # Missing password
        }

        response = self.client.post('/api/user/auth/player/signup/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # EMAIL VERIFICATION TESTS
    def test_email_verification_with_valid_otp_verifies_user(self):
        """When valid OTP is provided, user should be verified"""
        # Create unverified user
        user = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )

        # Simulate OTP in cache (normally set during signup)
        cache.set(f"{user.id}_EMAIL_VERIFY_OTP", "123456", 120)

        data = {
            'email': 'test@example.com',
            'otp': '123456'
        }

        response = self.client.post('/api/user/auth/player/signup/verify/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)

        # User should now be verified
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_email_verification_with_invalid_otp_returns_error(self):
        """When invalid OTP is provided, verification should fail"""
        user = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        cache.set(f"{user.id}_EMAIL_VERIFY_OTP", "123456", 120)

        data = {
            'email': 'test@example.com',
            'otp': '999999'  # Wrong OTP
        }

        response = self.client.post('/api/user/auth/player/signup/verify/', data)

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
        self.assertIn('error', response.data)

        # User should remain unverified
        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    def test_email_verification_with_nonexistent_email_returns_error(self):
        """When email doesn't exist, verification should fail"""
        data = {
            'email': 'nonexistent@example.com',
            'otp': '123456'
        }

        response = self.client.post('/api/user/auth/player/signup/verify/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_email_verification_with_expired_otp_returns_error(self):
        """When OTP has expired, verification should fail"""
        user = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        # Don't set OTP in cache (simulates expiration)

        data = {
            'email': 'test@example.com',
            'otp': '123456'
        }

        response = self.client.post('/api/user/auth/player/signup/verify/', data)

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    # LOGIN TESTS
    def test_login_with_valid_credentials_returns_tokens(self):
        """When valid credentials are provided, user gets authentication tokens"""
        user = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        user.is_verified = True
        user.save()

        data = {
            'email': 'test@example.com',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/player/login/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('credentials', response.data)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data['credentials'])
        self.assertIn('refresh', response.data['credentials'])

    def test_login_with_unverified_user_returns_error(self):
        """When user is not verified, login should fail"""
        NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        # User remains unverified

        data = {
            'email': 'test@example.com',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/player/login/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_login_with_invalid_credentials_returns_error(self):
        """When invalid credentials are provided, login should fail"""
        user = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        user.is_verified = True
        user.save()

        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }

        response = self.client.post('/api/user/auth/player/login/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_login_with_nonexistent_user_returns_error(self):
        """When user doesn't exist, login should fail"""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/player/login/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    # PASSWORD RECOVERY TESTS
    def test_password_recovery_request_with_valid_email_sends_reset_email(self):
        """When valid email is provided, password reset email is sent"""
        NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )

        data = {
            'email': 'test@example.com',
            'deep_link': 'https://app.example.com/reset?token={token}'
        }

        response = self.client.post('/api/user/auth/player/recovery/request/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # Reset email should be sent
        self.assertGreaterEqual(len(mail.outbox), 1)  # Initial verification + reset email

    def test_password_recovery_request_with_nonexistent_email_returns_error(self):
        """When email doesn't exist, password recovery should fail"""
        data = {
            'email': 'nonexistent@example.com',
            'deep_link': 'https://app.example.com/reset?token={token}'
        }

        response = self.client.post('/api/user/auth/player/recovery/request/', data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_password_recovery_request_with_cooldown_returns_error(self):
        """When recovery is requested too soon, should return cooldown error"""
        user = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )

        # Simulate existing recovery token in cache
        cache.set(f"{user.id}_FORGET_PASSWORD_TOKEN", "existing_token", 120)

        data = {
            'email': 'test@example.com',
            'deep_link': 'https://app.example.com/reset?token={token}'
        }

        response = self.client.post('/api/user/auth/player/recovery/request/', data)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)

    @patch('user.models.NormalPlayer.reset_password')
    def test_password_reset_with_valid_token_resets_password(self, mock_reset):
        """When valid token is provided, password should be reset"""
        mock_reset.return_value = True

        data = {
            'email': 'test@example.com',
            'token': 'valid_token',
            'new_password': 'newpassword123'
        }

        response = self.client.post('/api/user/auth/player/recovery/verify/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    @patch('user.models.NormalPlayer.reset_password')
    def test_password_reset_with_invalid_token_returns_error(self, mock_reset):
        """When invalid token is provided, password reset should fail"""
        mock_reset.return_value = False

        data = {
            'email': 'test@example.com',
            'token': 'invalid_token',
            'new_password': 'newpassword123'
        }

        response = self.client.post('/api/user/auth/player/recovery/verify/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class GuestPlayerAuthViewTests(APITestCase):
    """Test GuestPlayer authentication behaviors"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    # SIGNUP TESTS
    def test_guest_signup_with_valid_device_id_creates_user_and_returns_credentials(self):
        """When valid device_id is provided, guest user is created with credentials"""
        data = {
            'device_id': 'test-device-123',
            'profile_name': 'GuestUser'
        }

        response = self.client.post('/api/user/auth/guest/signup/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('credentials', response.data)
        self.assertIn('password', response.data)  # Randomly generated password
        self.assertIn('recovery_string', response.data)

        # User should exist in database
        user = GuestPlayer.objects.get(device_id='test-device-123')
        self.assertIsNotNone(user.recovery_string)
        self.assertTrue(user.profile_name.startswith('guest-'))  # Auto-generated if not provided

    def test_guest_signup_with_duplicate_device_id_returns_error(self):
        """When device_id already exists, signup should fail"""
        GuestPlayer.objects.create_user(
            device_id='existing-device',
            password='password123'
        )

        data = {
            'device_id': 'existing-device'
        }

        response = self.client.post('/api/user/auth/guest/signup/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_guest_signup_without_device_id_returns_validation_error(self):
        """When device_id is missing, validation error is returned"""
        data = {}

        response = self.client.post('/api/user/auth/guest/signup/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # LOGIN TESTS
    def test_guest_login_with_valid_credentials_returns_tokens(self):
        """When valid device_id and password are provided, user gets authentication tokens"""
        user = GuestPlayer.objects.create_user(
            device_id='test-device-123',
            password='password123'
        )

        data = {
            'device_id': 'test-device-123',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/guest/login/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('credentials', response.data)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data['credentials'])
        self.assertIn('refresh', response.data['credentials'])

    def test_guest_login_with_invalid_credentials_returns_error(self):
        """When invalid credentials are provided, login should fail"""
        GuestPlayer.objects.create_user(
            device_id='test-device-123',
            password='password123'
        )

        data = {
            'device_id': 'test-device-123',
            'password': 'wrongpassword'
        }

        response = self.client.post('/api/user/auth/guest/login/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_guest_login_with_nonexistent_device_returns_error(self):
        """When device_id doesn't exist, login should fail"""
        data = {
            'device_id': 'nonexistent-device',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/guest/login/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    # RECOVERY TESTS
    def test_guest_recovery_with_valid_recovery_string_resets_password_and_returns_credentials(self):
        """When valid recovery_string is provided, password is reset and credentials returned"""
        user = GuestPlayer.objects.create_user(
            device_id='test-device-123',
            password='oldpassword123'
        )
        recovery_string = user.recovery_string

        data = {
            'device_id': 'test-device-123',
            'recovery_string': recovery_string
        }

        response = self.client.post('/api/user/auth/guest/recovery/', data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('credentials', response.data)
        self.assertIn('user', response.data)
        self.assertIn('password', response.data['user'])  # New password

    def test_guest_recovery_with_invalid_recovery_string_returns_error(self):
        """When invalid recovery_string is provided, recovery should fail"""
        GuestPlayer.objects.create_user(
            device_id='test-device-123',
            password='password123'
        )

        data = {
            'device_id': 'test-device-123',
            'recovery_string': 'invalid-recovery-string'
        }

        response = self.client.post('/api/user/auth/guest/recovery/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_guest_recovery_with_nonexistent_device_returns_error(self):
        """When device_id doesn't exist, recovery should fail"""
        data = {
            'device_id': 'nonexistent-device',
            'recovery_string': 'some-recovery-string'
        }

        response = self.client.post('/api/user/auth/guest/recovery/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    # CONVERSION TESTS
    def test_guest_convert_to_normal_with_valid_data_creates_normal_player(self):
        """When guest converts with valid email/password, normal player is created"""
        guest = GuestPlayer.objects.create_user(
            device_id='test-device-123',
            password='password123'
        )

        # Authenticate as guest
        self.client.force_authenticate(user=guest)

        data = {
            'email': 'converted@example.com',
            'password': 'newpassword123',
            'profile_name': 'ConvertedUser'
        }

        response = self.client.post('/api/user/auth/guest/convert/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)

        # Normal player should exist, guest should be converted
        normal_player = NormalPlayer.objects.get(email='converted@example.com')
        self.assertEqual(normal_player.profile_name, 'ConvertedUser')
        self.assertFalse(normal_player.is_verified)  # Should need email verification

    def test_guest_convert_requires_authentication(self):
        """Guest conversion should require authentication"""
        data = {
            'email': 'test@example.com',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/guest/convert/', data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guest_convert_with_existing_email_returns_error(self):
        """When converting to existing email, should return error"""
        # Create existing normal player
        NormalPlayer.objects.create_user(
            email='existing@example.com',
            password='password123'
        )

        # Create and authenticate guest
        guest = GuestPlayer.objects.create_user(
            device_id='test-device-123',
            password='password123'
        )
        self.client.force_authenticate(user=guest)

        data = {
            'email': 'existing@example.com',
            'password': 'newpassword123'
        }

        response = self.client.post('/api/user/auth/guest/convert/', data)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_normal_player_cannot_access_guest_convert(self):
        """Normal players should not be able to access guest conversion"""
        normal_player = NormalPlayer.objects.create_user(
            email='test@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=normal_player)

        data = {
            'email': 'new@example.com',
            'password': 'password123'
        }

        response = self.client.post('/api/user/auth/guest/convert/', data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PlayerProfileViewTests(APITestCase):
    """Test PlayerProfileView behaviors for profile management and viewing"""

    def setUp(self):
        """Create test users for profile testing"""
        self.normal_player = NormalPlayer.objects.create_user(
            email='normal@example.com',
            password='password123',
            profile_name='NormalPlayer',
            first_name='Normal',
            last_name='Player'
        )
        self.normal_player.is_verified = True
        self.normal_player.save()

        self.guest_player = GuestPlayer.objects.create_user(
            device_id='guest-device-123',
            password='password123'
        )

        self.other_player = NormalPlayer.objects.create_user(
            email='other@example.com',
            password='password123',
            profile_name='OtherPlayer'
        )
        self.other_player.is_verified = True
        self.other_player.save()

    # SELF PROFILE TESTS
    def test_authenticated_user_can_view_own_profile(self):
        """When authenticated user requests profile list, they get their own detailed profile"""
        self.client.force_authenticate(user=self.normal_player)

        response = self.client.get('/api/user/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.normal_player.id)
        self.assertEqual(response.data['profile_name'], 'NormalPlayer')
        # Self profile should include additional fields
        self.assertIn('daily_reward_streak', response.data)
        self.assertIn('last_claimed', response.data)
        self.assertIn('invites_count', response.data)

    def test_guest_user_can_view_own_profile(self):
        """Guest users should also be able to view their own profile"""
        self.client.force_authenticate(user=self.guest_player)

        response = self.client.get('/api/user/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.guest_player.id)
        self.assertIn('profile_name', response.data)

    def test_unauthenticated_user_cannot_view_profile(self):
        """Unauthenticated users should not be able to access profiles"""
        response = self.client.get('/api/user/profile/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_includes_vip_status(self):
        """Profile should correctly show VIP status"""
        # Create VIP status for user
        VipPlayer.objects.create(
            player=self.normal_player,
            expiration_date=timezone.now() + timedelta(days=30)
        )

        self.client.force_authenticate(user=self.normal_player)
        response = self.client.get('/api/user/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['vip'])

    def test_profile_shows_expired_vip_as_false(self):
        """Expired VIP status should show as false"""
        VipPlayer.objects.create(
            player=self.normal_player,
            expiration_date=timezone.now() - timedelta(days=1)  # Expired
        )

        self.client.force_authenticate(user=self.normal_player)
        response = self.client.get('/api/user/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['vip'])

    # OTHER PLAYER PROFILE TESTS
    def test_authenticated_user_can_view_other_player_profile(self):
        """Authenticated users should be able to view other players' public profiles"""
        self.client.force_authenticate(user=self.normal_player)

        response = self.client.get(f'/api/user/profile/{self.other_player.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.other_player.id)
        self.assertEqual(response.data['profile_name'], 'OtherPlayer')
        # Other player profile should NOT include sensitive fields
        self.assertNotIn('daily_reward_streak', response.data)
        self.assertNotIn('last_claimed', response.data)
        self.assertNotIn('invites_count', response.data)

    def test_viewing_nonexistent_player_returns_404(self):
        """Requesting non-existent player profile should return 404"""
        self.client.force_authenticate(user=self.normal_player)

        response = self.client.get('/api/user/profile/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_view_other_profiles(self):
        """Unauthenticated users cannot view other player profiles"""
        response = self.client.get(f'/api/user/profile/{self.other_player.id}/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # SELF SUPPORT PACKAGES TESTS
    def test_user_can_view_own_support_packages(self):
        """Users should be able to view all their own support packages"""
        # Create support packages for user
        support1 = SupporterPlayerInfo.objects.create(
            player=self.normal_player,
            reason='purchase',
            visible=True,
            approved=True,
            used=True
        )
        support2 = SupporterPlayerInfo.objects.create(
            player=self.normal_player,
            reason='reward',
            visible=False,  # Not visible to others but user should see their own
            approved=False,  # Not approved but user should see their own
            used=False
        )

        self.client.force_authenticate(user=self.normal_player)
        response = self.client.get('/api/user/profile/supports/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Should see both packages

    def test_user_sees_empty_list_when_no_support_packages(self):
        """Users with no support packages should see empty list"""
        self.client.force_authenticate(user=self.normal_player)

        response = self.client.get('/api/user/profile/supports/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_support_packages_are_paginated(self):
        """Support packages should be properly paginated"""
        # Create multiple support packages
        for i in range(25):  # More than default page size
            SupporterPlayerInfo.objects.create(
                player=self.normal_player,
                reason='purchase',
                visible=True,
                approved=True
            )

        self.client.force_authenticate(user=self.normal_player)
        response = self.client.get('/api/user/profile/supports/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertEqual(response.data['count'], 25)

    def test_unauthenticated_user_cannot_view_support_packages(self):
        """Unauthenticated users cannot view support packages"""
        response = self.client.get('/api/user/profile/supports/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # OTHER PLAYER SUPPORT PACKAGES TESTS
    def test_user_can_view_other_player_public_support_packages(self):
        """Users should only see other players' visible, approved, used support packages"""
        # Create various support packages for other player
        public_support = SupporterPlayerInfo.objects.create(
            player=self.other_player,
            reason='purchase',
            visible=True,
            approved=True,
            used=True
        )
        private_support = SupporterPlayerInfo.objects.create(
            player=self.other_player,
            reason='reward',
            visible=False,  # Should not be visible
            approved=True,
            used=True
        )
        unapproved_support = SupporterPlayerInfo.objects.create(
            player=self.other_player,
            reason='purchase',
            visible=True,
            approved=False,  # Should not be visible
            used=True
        )
        unused_support = SupporterPlayerInfo.objects.create(
            player=self.other_player,
            reason='purchase',
            visible=True,
            approved=True,
            used=False  # Should not be visible
        )

        self.client.force_authenticate(user=self.normal_player)
        response = self.client.get(f'/api/user/profile/{self.other_player.id}/supports/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only public support visible
        self.assertEqual(response.data['results'][0]['id'], public_support.id)

    def test_viewing_nonexistent_player_supports_returns_404(self):
        """Requesting supports for non-existent player should return 404"""
        self.client.force_authenticate(user=self.normal_player)

        response = self.client.get('/api/user/profile/99999/supports/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SupporterPlayerViewTests(APITestCase):
    """Test SupporterPlayerView behaviors for supporter system management"""

    def setUp(self):
        """Create test users and support data"""
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

    # LIST SUPPORTERS TESTS
    def test_authenticated_user_can_list_public_supporters(self):
        """Authenticated users should see list of approved, visible supporters ordered by approval date"""
        # Create various supporter infos
        visible_supporter = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=True,
            approved=True,
            approval_date=timezone.now() - timedelta(days=1)
        )

        recent_supporter = SupporterPlayerInfo.objects.create(
            player=self.other_user,
            reason='honorary',
            visible=True,
            approved=True,
            approval_date=timezone.now()  # More recent
        )

        # This should not appear (not visible)
        SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=False,
            approved=True
        )

        # This should not appear (not approved)
        SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=True,
            approved=False
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/user/supporter/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        # Should be ordered by approval_date (most recent first)
        self.assertEqual(response.data['results'][0]['id'], recent_supporter.id)
        self.assertEqual(response.data['results'][1]['id'], visible_supporter.id)

    def test_unauthenticated_user_cannot_list_supporters(self):
        """Unauthenticated users cannot view supporters list"""
        response = self.client.get('/api/user/supporter/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_supporters_list_is_paginated(self):
        """Supporters list should be properly paginated"""
        # Create many supporters
        for i in range(25):
            SupporterPlayerInfo.objects.create(
                player=self.user,
                reason='purchase',
                visible=True,
                approved=True,
                approval_date=timezone.now()
            )

        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/user/supporter/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertEqual(response.data['count'], 25)

    def test_empty_supporters_list_returns_empty_results(self):
        """When no supporters exist, should return empty list"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/user/supporter/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    # RETRIEVE SUPPORTER TESTS
    def test_authenticated_user_can_retrieve_public_supporter_details(self):
        """Users should be able to view details of public supporters"""
        supporter = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=True,
            approved=True,
            message='Thank you for the great game!',
            instagram_link='@testuser'
        )

        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/user/supporter/{supporter.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], supporter.id)
        self.assertIn('player', response.data)
        self.assertEqual(response.data['message'], 'Thank you for the great game!')

    def test_retrieving_private_supporter_returns_404(self):
        """Trying to retrieve non-visible supporter should return 404"""
        supporter = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=False,  # Not public
            approved=True
        )

        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/user/supporter/{supporter.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieving_unapproved_supporter_returns_404(self):
        """Trying to retrieve unapproved supporter should return 404"""
        supporter = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=True,
            approved=False  # Not approved
        )

        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/user/supporter/{supporter.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieving_nonexistent_supporter_returns_404(self):
        """Trying to retrieve non-existent supporter should return 404"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/user/supporter/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # USE SUPPORTER PACKAGE TESTS
    def test_user_can_use_own_unused_support_package(self):
        """Users should be able to use their own unused support packages"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            visible=False,
            approved=True,
            used=False  # Unused
        )

        self.client.force_authenticate(user=self.user)

        data = {
            'message': 'Thanks for the amazing game!',
            'instagram_link': '@myusername',
            'telegram_link': '@mytelegram',
            'visible': True
        }

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Package should now be marked as used and updated
        support_package.refresh_from_db()
        self.assertTrue(support_package.used)
        self.assertTrue(support_package.visible)
        self.assertEqual(support_package.message, 'Thanks for the amazing game!')
        self.assertEqual(support_package.instagram_link, '@myusername')

    def test_user_cannot_use_already_used_support_package(self):
        """Users cannot use support packages that are already used"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            used=True  # Already used
        )

        self.client.force_authenticate(user=self.user)

        data = {
            'message': 'Test message',
            'visible': True
        }

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_use_other_users_support_package(self):
        """Users cannot use support packages that belong to other users"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.other_user,  # Belongs to other user
            reason='purchase',
            used=False
        )

        self.client.force_authenticate(user=self.user)

        data = {
            'message': 'Test message',
            'visible': True
        }

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_using_support_package_with_minimal_data_works(self):
        """Using support package with minimal required data should work"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            used=False
        )

        self.client.force_authenticate(user=self.user)

        data = {}  # Minimal data

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        support_package.refresh_from_db()
        self.assertTrue(support_package.used)
        self.assertFalse(support_package.visible)  # Default value

    def test_using_nonexistent_support_package_returns_404(self):
        """Trying to use non-existent support package should return 404"""
        self.client.force_authenticate(user=self.user)

        data = {
            'message': 'Test message',
            'visible': True
        }

        response = self.client.post('/api/user/supporter/99999/use/', data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_use_support_package(self):
        """Unauthenticated users cannot use support packages"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            used=False
        )

        data = {
            'message': 'Test message',
            'visible': True
        }

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_support_package_use_validates_data_format(self):
        """Support package use should validate input data properly"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            used=False
        )

        self.client.force_authenticate(user=self.user)

        data = {
            'visible': 'invalid_boolean'  # Invalid boolean value
        }

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_used_support_package_appears_in_public_list_when_visible(self):
        """After using a support package with visible=True, it should appear in public lists"""
        support_package = SupporterPlayerInfo.objects.create(
            player=self.user,
            reason='purchase',
            approved=True,
            used=False,
            visible=False
        )

        self.client.force_authenticate(user=self.user)

        # Use the package and make it visible
        data = {
            'message': 'Great game!',
            'visible': True
        }

        response = self.client.post(f'/api/user/supporter/{support_package.id}/use/', data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Now check if it appears in public supporters list
        response = self.client.get('/api/user/supporter/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['message'], 'Great game!')
