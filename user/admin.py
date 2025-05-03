from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as _UserAdmin
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from user.models import User, GuestPlayer, NormalPlayer, SupporterPlayerInfo, VipPlayer


# Register your models here.
class UserBaseAdmin(_UserAdmin):
    list_display = ["email", "username", 'device_id', "first_name", "last_name", "is_staff", ]
    fieldsets = [
        (None, {"fields": ("email", "device_id", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    ]
    readonly_fields = ["last_login", "date_joined"]
    list_filter = ['is_superuser', 'is_staff']
    search_fields = ['username', 'email', ]


@admin.register(User)
class UserAdmin(UserBaseAdmin):
    pass


class PlayerAdmin(admin.ModelAdmin):
    list_display = ["email", 'device_id', "first_name", "last_name", "is_staff", ]
    list_filter = UserBaseAdmin.list_filter + ['gender']
    fieldsets = [
        (None, {"fields": ("email", "device_id",)}),
        (_('Block info'), {
            'fields': ('is_blocked',)
        }),
        (_('Profile info'), {
            'fields': (
                'profile_name', 'gender', 'birth_date',
            )
        }),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
        (_("Lucky Wheel"), {"fields": ("last_lucky_wheel_spin", )}),
        (_("Daily reward"), {"fields": ("daily_reward_streak", "last_claimed")}),
    ]

    search_fields = UserBaseAdmin.search_fields


@admin.register(GuestPlayer)
class GuestUserAdmin(PlayerAdmin):
    list_display = ['device_id', "first_name", "last_name", ]
    search_fields = PlayerAdmin.search_fields + ['device_id']


@admin.register(NormalPlayer)
class NormalPlayerAdmin(PlayerAdmin):
    list_display = ["email", "first_name", "last_name", "is_staff", 'is_verified']
    search_fields = PlayerAdmin.search_fields + ['email']
    list_filter = PlayerAdmin.list_filter + ['is_verified']


@admin.register(SupporterPlayerInfo)
class SupporterPlayerInfoAdmin(admin.ModelAdmin):
    list_filter = ['approved', 'used', 'visible', 'reason', ]
    list_display = ['player', 'message_trunc', 'approved', 'approval_date_delta', 'used', 'visible', 'reason', ]
    raw_id_fields = ['player', ]
    actions = ['approve_supports', 'disapprove_supports', ]

    @admin.action(description="Approve selected supports")
    def approve_supports(self, request, queryset):
        for i in queryset:
            i.approve()
        messages.success(request, _(f"Approved {queryset.count()} message(s) successfully."))

    @admin.action(description="Disapprove selected supports")
    def disapprove_supports(self, request, queryset):
        for i in queryset:
            i.disapprove()
        messages.success(request, _(f"Disapproved {queryset.count()} message(s) successfully."))

    def approval_date_delta(self, obj: SupporterPlayerInfo):
        if not obj.approval_date:
            return None

        return (timezone.now() - obj.approval_date).seconds // 360

    def message_trunc(self, obj: SupporterPlayerInfo):
        if not obj.message:
            return None
        return f'{obj.message[:10]}...'

    message_trunc.short_description = "Message"
    approval_date_delta.short_description = "Hours"


@admin.register(VipPlayer)
class VipPlayerAdmin(admin.ModelAdmin):
    list_display = ['player', 'expiration_date']
