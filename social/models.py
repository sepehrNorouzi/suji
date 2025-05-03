from typing import Union

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel
from exceptions.social import AlreadyFriendError
from user.models import User


class FriendshipRequest(BaseModel):
    sender = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='requested_friendships')
    receiver = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='friendship_requests')

    class Meta:
        verbose_name = _('Friendship Request')
        verbose_name_plural = _('Friendship Requests')
        ordering = ['created_time', ]

    def reject(self):
        self.delete()
        return

    def accept(self):
        friendship = Friendship.create_friendship(self.sender, self.receiver)
        self.delete()
        return friendship

    @classmethod
    def create(cls, sender_id: int, receiver_id: int):
        if Friendship.check_friendship(sender_id, receiver_id):
            raise AlreadyFriendError(_(f"{receiver_id} already friends with {sender_id}."))
        return cls.objects.create(sender_id=sender_id, receiver_id=receiver_id)

    def __str__(self):
        return f'{self.sender} requested {self.receiver}'


class Friendship(BaseModel):
    user_1 = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='l_friends')
    user_2 = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name='r_friends')

    def save(self, *args, **kwargs):
        if self.user_1.id < self.user_2.id:
            self.user_1, self.user_2 = self.user_2, self.user_1
        super(Friendship, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _('Friendship')
        verbose_name_plural = _('Friendships')
        unique_together = (('user_1', 'user_2'),)

    def __str__(self):
        return f'{self.user_1} - {self.user_2}'

    @classmethod
    def _check_friendship_with_id(cls, user_1_id: int, user_2_id: int) -> bool:
        if user_1_id < user_2_id:
            return cls.objects.filter(user_1_id=user_1_id, user_2_id=user_2_id).exists()
        return cls.objects.filter(user_2_id=user_1_id, user_1_id=user_2_id).exists()

    @classmethod
    def _check_friendship_with_user_instance(cls, user_1: User, user_2: User) -> bool:
        if user_1.id < user_2.id:
            return cls.objects.filter(user_1=user_1, user_2=user_2).exists()
        return cls.objects.filter(user_2=user_1, user_1=user_2).exists()

    @classmethod
    def check_friendship(cls, user_1: Union[User, int], user_2: Union[User, int]) -> bool:
        if isinstance(user_1, User) and isinstance(user_2, User):
            return cls._check_friendship_with_user_instance(user_1, user_2)
        elif isinstance(user_1, int) and isinstance(user_2, int):
            return cls._check_friendship_with_id(user_1, user_2)

        raise ValueError(f"Arguments must both be either integer or User instance.")

    @classmethod
    def create_friendship(cls, user_1, user_2):
        return cls.objects.create(user_1=user_1, user_2=user_2)

    @classmethod
    def list_friends(cls, user):
        return cls.objects.filter(user_1=user) | cls.objects.filter(user_2=user)
