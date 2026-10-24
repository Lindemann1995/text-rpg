from django.contrib import admin

from .models import (
    Guild, GuildMember, GuildApplication, GuildLog,
    GuildChatMessage, GuildUpgrade, GuildUpgradeTemplate,
    GuildUpgradeLevelCost, GuildUISettings, Duel, GuildDailyQuestTemplate, GuildDailyQuest, GuildDailyQuestContribution, 
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

from .models import Castle, CastleSiege

@admin.register(Castle)
class CastleAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'defense_level', 'daily_tax', 'passive_income', 'last_tax_collected', 'debt_deadline')
    list_filter = ('owner', 'defense_level')
    search_fields = ('name', 'slug')
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'description', 'image_path')
        }),
        ('Карта', {
            'fields': ('map_x', 'map_y')
        }),
        ('Экономика и защита', {
            'fields': ('owner', 'daily_tax', 'passive_income', 'defense_level')
        }),
        ('Налоги (новое)', {
            'fields': ('last_tax_collected', 'debt_deadline'),
            'classes': ('collapse',), # Можно свернуть, чтобы не мешало
        }),
        ('Баффы', {
            'fields': ('buff_xp_percent', 'buff_gold_percent')
        }),
    )

@admin.register(CastleSiege)
class CastleSiegeAdmin(admin.ModelAdmin):
    list_display = ('castle', 'attacker_guild', 'defender_guild', 'status', 'started_at')
    list_filter = ('status',)


@admin.register(GuildUISettings)
class GuildUISettingsAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon_taxes', 'icon_bank', 'icon_war')


@admin.register(Duel)
class DuelAdmin(admin.ModelAdmin):
    list_display = ('challenger', 'opponent', 'status', 'winner', 'created_at')
    list_filter = ('status',)


@admin.register(GuildDailyQuestTemplate)
class GuildDailyQuestTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_enemy', 'required_count', 'difficulty', 'is_active')
    list_filter = ('is_active', 'difficulty', 'target_enemy')
    search_fields = ('title',)

@admin.register(GuildDailyQuest)
class GuildDailyQuestAdmin(admin.ModelAdmin):
    list_display = ('guild', 'template', 'date', 'progress', 'is_completed')
    list_filter = ('date', 'is_completed', 'guild')