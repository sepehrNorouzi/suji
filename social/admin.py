from django.contrib import admin

from social.models import FriendshipRequest, Friendship


# Register your models here.
@admin.register(FriendshipRequest)
class FriendshipRequestAdmin(admin.ModelAdmin):
    search_fields = ['sender__username', 'receiver__username']
    list_display = ['sender', 'receiver', ]
    raw_id_fields = ['sender', 'receiver']


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    search_fields = ['user_1__username', 'user_2__username']
