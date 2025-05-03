from django.contrib import admin

from common.models import Configuration


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ['app_name', 'game_package_name', 'is_active', 'maintenance_mode', ]

