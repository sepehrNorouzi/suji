from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):

    def create_user_base(self, email=None, device_id=None, password=None, **extra_fields):
        if not email and not device_id:
            raise ValueError('Users must have an email or device ID')
        username = email or device_id
        if "username" in extra_fields.keys():
            del extra_fields['username']
        user = self.model(
            username=username,
            email=self.normalize_email(email) if email else None,
            device_id=device_id,
            **extra_fields
        )
        user.set_password(password)
        return user

    def create_user(self, email=None, device_id=None, password=None, **extra_fields):
        user = self.create_user_base(email, device_id, password, **extra_fields)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username=email, email=email, password=password, **extra_fields)


class NormalPlayerManager(UserManager):
    def create_user(self, email=None, device_id=None, password=None, **extra_fields):
        extra_fields.setdefault('is_verified', False)
        user = self.create_user_base(email, device_id, password, **extra_fields)
        user.save(using=self._db)
        user.send_email_verification()
        return user


class GuestPlayerManager(UserManager):

    @staticmethod
    def _create_recovery_string(device_id: str) -> str:
        cipher_suite = settings.CIPHER_SUITE
        plaintext_bytes = device_id.encode()
        encrypted_bytes = cipher_suite.encrypt(plaintext_bytes)
        encrypted_string = encrypted_bytes.decode()
        return encrypted_string

    def create_user(self, email=None, device_id=None, password=None, **extra_fields):
        user = self.create_user_base(email, device_id, password, **extra_fields)
        user.recovery_string = GuestPlayerManager._create_recovery_string(device_id)
        user.save(using=self._db)
        return user
