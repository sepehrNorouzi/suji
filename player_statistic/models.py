from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


class PlayerLevel(BaseModel):
    start_xp = models.PositiveIntegerField(default=0, verbose_name=_("Start Xp"))
    reward = models.ForeignKey(to="shop.RewardPackage", on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name=_("Level Up reward"))

    @property
    def index(self) -> int:
        return self.__class__.objects.filter(start_xp__lt=self.start_xp).count() + 1

    @classmethod
    def get_first_level(cls) -> 'PlayerLevel':
        return cls.objects.get_or_create(start_xp=0)[0]

    @classmethod
    def get_xp_cap(cls) -> int:
        return cls.objects.last().start_xp

    @classmethod
    def get_level_from_xp(cls, xp: int) -> 'PlayerLevel':
        return cls.objects.filter(start_xp__lte=xp).last()

    def __le__(self, other) -> bool:
        return self.start_xp <= other.start_xp

    def __ge__(self, other) -> bool:
        return self.start_xp >= other.start_xp

    def __gt__(self, other) -> bool:
        return self.start_xp > other.start_xp

    def __lt__(self, other) -> bool:
        return self.start_xp < other.start_xp

    def __eq__(self, other) -> bool:
        return self.start_xp == other.start_xp

    def __ne__(self, other) -> bool:
        return self.start_xp != other.start_xp

    def __str__(self):
        return f'LEVEL_{self.index}'

    class Meta:
        verbose_name = _("Player Level")
        verbose_name_plural = _("Player Levels")
        ordering = ['start_xp']


class PlayerStatistic(BaseModel):
    prev_xp = models.PositiveIntegerField(verbose_name=_("Prev Xp"), default=0, editable=False)
    player = models.OneToOneField(to='user.User', on_delete=models.CASCADE, verbose_name=_("Player"),
                                  related_name='stats')
    score = models.PositiveIntegerField(verbose_name=_("Score"), default=0)
    xp = models.PositiveIntegerField(verbose_name=_("Xp"), default=0, editable=False)
    cup = models.PositiveIntegerField(verbose_name=_("Cup"), default=0)

    level = models.ForeignKey(to=PlayerLevel, on_delete=models.SET_DEFAULT, default=PlayerLevel.get_first_level,
                              verbose_name=_("Level"), editable=False)

    def __str__(self):
        return f'{self.player} stats'

    def calculate_xp(self) -> int:
        return min(self.xp, PlayerLevel.get_xp_cap())

    def calculate_level(self) -> PlayerLevel:
        return PlayerLevel.get_level_from_xp(xp=self.xp)

    def save(self, *args, **kwargs):
        self.xp = self.calculate_xp()
        if self.xp != self.prev_xp:
            self.level = self.calculate_level()
            self.prev_xp = self.xp

        super(PlayerStatistic, self).save(*args, **kwargs)
