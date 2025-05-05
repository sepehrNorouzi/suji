from django.contrib import admin

from match.models import Match, MatchType, MatchConfiguration, MatchResult


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'match_type', ]
    list_filter = ['match_type', ]
    readonly_fields = ['uuid', 'players', ]
    search_fields = ['uuid', ]

@admin.register(MatchType)
class MatchTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'id', 'entry_cost']
    search_fields = ['name']

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
