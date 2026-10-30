from django.contrib import admin
from .models import Friendship, PrivateMessage
from game.admin import custom_admin_site

@admin.register(Friendship, site=custom_admin_site)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('from_player', 'to_player', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(PrivateMessage, site=custom_admin_site)
class PrivateMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'message', 'is_read', 'created_at')
    search_fields = ('sender__user__username', 'receiver__user__username', 'message')