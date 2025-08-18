from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html


from match.models import Match, MatchType, MatchConfiguration, MatchResult, MatchmakingTicket


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'match_type', ]
    list_filter = ['match_type', ]
    readonly_fields = ['uuid', 'players', ]
    search_fields = ['uuid', ]

@admin.register(MatchType)
class MatchTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['name', 'id', 'entry_cost', 'max_players', 'min_players', 'pool_name']
    
    fieldsets = [
        (None, {
            'fields': ('name', 'priority', 'is_active')
        }),
        (_('Entry Requirements'), {
            'fields': ('entry_cost', 'min_xp', 'min_cup', 'min_score')
        }),
        (_('Matchmaking Configuration'), {
            'fields': (
                'pool_name', 'max_players', 'min_players', 
                'matchmaking_timeout', 'search_fields_config'
            ),
            'classes': ('collapse',)
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

@admin.register(MatchmakingTicket)
class MatchmakingTicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_id_short', 'player', 'match_type', 'status', 
        'created_time', 'updated_time', 'has_assignment'
    ]
    list_filter = ['status', 'match_type', 'created_time']
    search_fields = ['ticket_id', 'player__username', 'player__email']
    readonly_fields = [
        'ticket_id', 'search_fields', 'assignment', 
        'created_time', 'updated_time'
    ]
    raw_id_fields = ['player']
    
    fieldsets = [
        (None, {
            'fields': ('ticket_id', 'player', 'match_type', 'status')
        }),
        (_('Search Configuration'), {
            'fields': ('search_fields',),
            'classes': ('collapse',)
        }),
        (_('Assignment Data'), {
            'fields': ('assignment',),
            'classes': ('collapse',)
        }),
        (_('Error Information'), {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_time', 'updated_time'),
            'classes': ('collapse',)
        }),
    ]
    
    def ticket_id_short(self, obj):
        """Display shortened ticket ID"""
        if len(obj.ticket_id) > 20:
            return f"{obj.ticket_id[:20]}..."
        return obj.ticket_id
    ticket_id_short.short_description = _('Ticket ID')
    
    def has_assignment(self, obj):
        """Check if ticket has assignment data - returns boolean for Django admin"""
        return bool(obj.assignment)
    has_assignment.short_description = _('Has Assignment')
    has_assignment.boolean = True  # This tells Django to display as a boolean icon
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('player', 'match_type')
    
    actions = ['cancel_tickets', 'mark_as_error']
    
    @admin.action(description=_('Cancel selected tickets'))
    def cancel_tickets(self, request, queryset):
        """Cancel selected tickets"""
        updated = 0
        for ticket in queryset.filter(status=MatchmakingTicket.TicketStatus.PENDING):
            ticket.cancel()
            updated += 1
        
        self.message_user(
            request,
            _(f'Successfully cancelled {updated} tickets.')
        )
    
    @admin.action(description=_('Mark selected tickets as error'))
    def mark_as_error(self, request, queryset):
        """Mark selected tickets as error"""
        updated = 0
        for ticket in queryset.filter(status=MatchmakingTicket.TicketStatus.PENDING):
            ticket.mark_error("Manually marked as error by admin")
            updated += 1
        
        self.message_user(
            request,
            _(f'Successfully marked {updated} tickets as error.')
        )

