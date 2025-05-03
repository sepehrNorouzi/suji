from django.contrib import admin

from leaderboard.models import Leaderboard, LeaderboardType, LeaderboardReward


# Register your models here.

@admin.register(LeaderboardReward)
class LeaderboardRewardAdmin(admin.ModelAdmin):
    pass


class LeaderboardRewardInlineAdmin(admin.TabularInline):
    model = LeaderboardReward
    extra = 1


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    raw_id_fields = ['player', ]
    list_display = ['player', 'score', ]
    fieldsets = [(None, {'fields': ['player', 'score']})]

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LeaderboardType)
class LeaderboardTypeAdmin(admin.ModelAdmin):
    inlines = [LeaderboardRewardInlineAdmin, ]
    list_display = ['id', 'name', 'start_time', 'duration', 'is_active', ]
    list_filter = ['is_active', ]
    search_fields = ['name']
