from django.contrib import admin

from .models import (
    Guild, GuildMember, GuildApplication, GuildLog,
    GuildChatMessage, GuildUpgrade, GuildUpgradeTemplate,
    GuildUpgradeLevelCost
)


@admin.register(Guild)
class GuildAdmin(admin.ModelAdmin):
    list_display = ('tag', 'name', 'leader', 'level', 'treasury_gold', 'is_open', 'created_at')
    search_fields = ('name', 'tag')
    list_filter = ('is_open',)


@admin.register(GuildMember)
class GuildMemberAdmin(admin.ModelAdmin):
    list_display = ('guild', 'player', 'rank', 'joined_at', 'contributed_gold')
    list_filter = ('rank', 'guild')
    search_fields = ('player__user__username',)


@admin.register(GuildApplication)
class GuildApplicationAdmin(admin.ModelAdmin):
    list_display = ('guild', 'player', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(GuildLog)
class GuildLogAdmin(admin.ModelAdmin):
    list_display = ('guild', 'actor', 'action', 'created_at')
    list_filter = ('action',)


@admin.register(GuildChatMessage)
class GuildChatMessageAdmin(admin.ModelAdmin):
    list_display = ('guild', 'player', 'message', 'created_at')


@admin.register(GuildUpgrade)
class GuildUpgradeAdmin(admin.ModelAdmin):
    list_display = ('guild', 'template', 'level')
    list_filter = ('template', 'guild')


@admin.register(GuildUpgradeTemplate)
class GuildUpgradeTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'upgrade_type', 'icon')


@admin.register(GuildUpgradeLevelCost)
class GuildUpgradeLevelCostAdmin(admin.ModelAdmin):
    list_display = ('template', 'target_level', 'gold_cost', 'item', 'quantity')
    list_filter = ('template', 'target_level')