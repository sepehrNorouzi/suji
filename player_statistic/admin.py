from django.contrib import admin

from player_statistic.models import PlayerLevel, PlayerStatistic


@admin.register(PlayerLevel)
class PlayerLevelAdmin(admin.ModelAdmin):
    list_display = ('start_xp', 'index', 'reward', )


@admin.register(PlayerStatistic)
class PlayerStatisticAdmin(admin.ModelAdmin):
    list_display = ('player', 'level', 'xp', 'score', 'cup', )
    raw_id_fields = ('player', )
    search_fields = ('player__username', )
    