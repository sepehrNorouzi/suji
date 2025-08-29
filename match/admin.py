from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html


from match.models import Match, MatchType, MatchConfiguration, MatchResult


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'match_type', ]
    list_filter = ['match_type', ]
    readonly_fields = ['uuid', 'players', ]
    search_fields = ['uuid', ]

@admin.register(MatchType)
class MatchTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['name', 'id', 'entry_cost']
    
    fieldsets = [
        (None, {
            'fields': ('name', 'priority', 'is_active')
        }),
        (_('Entry Requirements'), {
            'fields': ('entry_cost', 'min_xp', 'min_cup', 'min_score')
        }),
        (_('Rewards - Winner'), {
            'fields': ('winner_package', 'winner_xp', 'winner_cup', 'winner_score')
        }),
        (_('Rewards - Loser'), {
            'fields': ('loser_package', 'loser_xp', 'loser_cup', 'loser_score')
        }),
        (_('Advanced'), {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
    ]

@admin.register(MatchConfiguration)
class MatchConfigurationAdmin(admin.ModelAdmin):
    list_display = ['__str__', ]

@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display = ['match_uuid', 'match_type']
    filter_horizontal = ['players']
    readonly_fields = ['players', ]

    def has_change_permission(self, request, obj=None):
        return False
