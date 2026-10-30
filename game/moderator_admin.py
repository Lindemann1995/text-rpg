from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.models import User, Group
from .models import Player
from guilds.models import GuildApplication


# Просто используем стандартный AdminSite, но с другим именем
moderator_site = AdminSite(name='moderator')
moderator_site.site_header = "Панель Модератора"
moderator_site.site_title = "Модерация | Тень Древних"
moderator_site.index_title = "Добро пожаловать, Страж"


# Регистрируем Player на модераторском сайте
@admin.register(Player, site=moderator_site)
class PlayerModeratorAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'gold', 'role')
    search_fields = ('user__username', 'user__email')
    list_filter = ('role',)
    actions = ['ban_player']

    def ban_player(self, request, queryset):
        self.message_user(request, f"Выбрано игроков: {queryset.count()} (бан пока не настроен)")

    ban_player.short_description = "🔨 Забанить (заглушка)"


@admin.register(GuildApplication, site=moderator_site)
class GuildApplicationModeratorAdmin(admin.ModelAdmin):
    list_display = ('player', 'guild', 'status', 'created_at')
    list_filter = ('status',)