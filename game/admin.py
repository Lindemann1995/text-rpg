from django.contrib.admin import AdminSite
from django.db.models import Sum
from django.contrib import admin
from django.utils import timezone
from datetime import timedelta

from .models import (
    CharacterClass, Player, Scene, Choice, Flag, Item, Inventory,
    Location, Enemy, Combat, Trader, EquipmentSlot, EnemyLoot, 
    NPC, DialogueOption, QuestLine, Quest, QuestObjective, PlayerQuest, 
    Recipe, RecipeIngredient, PlayerRecipe, CombatSettings, PlayerReport, PlayerNotification, 
)
from guilds.models import Guild


class CustomAdminSite(AdminSite):
    site_header = "Тень Древних"
    site_title = "Управление"
    index_title = "Добро пожаловать, Повелитель"
    index_template = 'admin/index.html'

    def each_context(self, request):
        # Добавляем онлайн на все страницы
        context = super().each_context(request)
        online_threshold = timezone.now() - timedelta(minutes=5)
        context['online_players'] = Player.objects.filter(last_seen__gte=online_threshold).count()
        return context

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'total_players': Player.objects.count(),
            'total_gold': Player.objects.aggregate(Sum('gold'))['gold__sum'] or 0,
            'total_guilds': Guild.objects.count(),
        })
        return super().index(request, extra_context)

custom_admin_site = CustomAdminSite(name='custom_admin')


# ==========================================
# РЕГИСТРАЦИЯ МОДЕЛЕЙ В КАСТОМНОМ САЙТЕ
# ==========================================

@admin.register(CharacterClass, site=custom_admin_site)
class CharacterClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_strength', 'base_agility', 'base_intelligence']
    search_fields = ['name']


@admin.register(Player, site=custom_admin_site)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['user', 'character_class', 'level', 'gold', 'faction',
                    'role', 'is_banned', 'mute_until']
    list_filter = ['character_class', 'faction', 'is_in_tutorial',
                   'role', 'is_banned']
    search_fields = ['user__username']
    
    fieldsets = (
        ('Основное', {
            'fields': ('user', 'character_class', 'level', 'experience', 'gold', 'faction', 'role')
        }),
        ('Характеристики', {
            'fields': ('strength', 'agility', 'intelligence', 'endurance', 'sanity')
        }),
        ('Ресурсы и текущая сцена', {
            'fields': ('health', 'max_health', 'mana', 'max_mana', 'current_scene', 'current_location')
        }),
        ('Оффлайн-прогресс', {
            'fields': ('last_offline_claim', 'offline_gold_rate')
        }),
        ('Модерация', {
            'fields': ('is_banned', 'ban_until', 'mute_until', 'ban_reason'),
            'classes': ('collapse',),
        }),
        ('Прочее', {
            'fields': ('is_in_tutorial', 'email_verified', 'email_verification_token', 'enemies_killed')
        }),
    )

    actions = ['ban_7_days', 'mute_24_hours', 'unban_player']

    def ban_7_days(self, request, queryset):
        queryset.update(
            is_banned=True,
            ban_until=timezone.now() + timedelta(days=7),
            ban_reason='Забанен через админку (7 дней)',
        )
        self.message_user(request, f'Забанено: {queryset.count()}')
    ban_7_days.short_description = '🔨 Забанить на 7 дней'

    def mute_24_hours(self, request, queryset):
        queryset.update(
            mute_until=timezone.now() + timedelta(hours=24),
            ban_reason='Замучен через админку (24 часа)'
        )
        self.message_user(request, f"Замучено на 24 часа: {queryset.count()} игроков")
    mute_24_hours.short_description = "🔇 Замутить на 24 часа"

    def unban_player(self, request, queryset):
        queryset.update(
            is_banned=False, 
            ban_until=None, 
            mute_until=None,
            ban_reason=''
        )
        self.message_user(request, f"Разбанено: {queryset.count()} игроков")
    unban_player.short_description = "✅ Разбанить"


@admin.register(Scene, site=custom_admin_site)
class SceneAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'location', 'scene_type', 'is_start']
    list_filter = ['scene_type', 'is_tutorial', 'is_start', 'location']
    search_fields = ['title', 'slug', 'text']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Choice, site=custom_admin_site)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['text', 'scene', 'next_scene', 'order']
    list_filter = ['scene']
    search_fields = ['text']


@admin.register(Flag, site=custom_admin_site)
class FlagAdmin(admin.ModelAdmin):
    list_display = ['player', 'name', 'value', 'created_at']
    list_filter = ['name']
    search_fields = ['player__user__username', 'name']


@admin.register(Item, site=custom_admin_site)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'item_type', 'rarity', 'price', 'required_level', 'equip_slot']
    list_filter = ['item_type', 'rarity', 'equip_slot', 'required_classes']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'description', 'icon', 'image_path','item_type', 'rarity', 'price')
        }),
        ('Бонусы к статам', {
            'fields': ('bonus_strength', 'bonus_agility', 'bonus_intelligence', 'bonus_endurance', 'bonus_sanity', 'bonus_health', 'bonus_mana')
        }),
        ('Эффект (для зелий)', {
            'fields': ('effect_type', 'effect_value')
        }),
        ('Экипировка', {
            'fields': ('equip_slot', 'required_classes', 'required_level'),
            'classes': ('collapse',),
        }),
        ('Настройки ресурса', {
            'fields': ('max_stack', 'scroll_unlock'),
            'classes': ('collapse',),
            'description': 'Заполняйте эти поля, если тип предмета = "Ресурс"'
        }),
    )


@admin.register(Inventory, site=custom_admin_site)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['player', 'item', 'quantity', 'is_equipped']
    list_filter = ['is_equipped', 'item__item_type']
    search_fields = ['player__user__username', 'item__name']


@admin.register(Location, site=custom_admin_site)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'min_level', 'is_available', 'is_guild_only']
    list_filter = ['is_available', 'is_guild_only', 'min_level']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'description', 'icon', 'location_type', 'min_level', 'is_available')
        }),
        ('Карта', {
            'fields': ('map_x', 'map_y')
        }),
        ('Доступ (Гильдия)', {
            'fields': ('is_guild_only', 'guild'),
            'description': 'Если поставить галочку "Только для гильдии", локацию увидит только выбранная ниже гильдия.'
        }),
    )


@admin.register(Enemy, site=custom_admin_site)
class EnemyAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'enemy_type', 'location', 'health', 'attack', 'defense', 'image_path', 'flip_image']
    list_filter = ['enemy_type', 'location', 'level']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'description', 'icon', 'enemy_type', 'location')
        }),
        ('Характеристики', {
            'fields': ('level', 'health', 'attack', 'defense', 'xp_reward', 'gold_reward')
        }),
        ('Визуал', {
            'fields': ('image_path', 'bg_image_path', 'flip_image')
        }),
        ('Способности', {
            'fields': ('abilities',)
        }),
    )

@admin.register(Combat, site=custom_admin_site)
class CombatAdmin(admin.ModelAdmin):
    list_display = ['player', 'enemy', 'status', 'turn', 'created_at']
    list_filter = ['status', 'enemy']
    search_fields = ['player__user__username', 'enemy__name']

@admin.register(Trader, site=custom_admin_site)
class TraderAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active']
    list_filter = ['location', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['items']


@admin.register(EquipmentSlot, site=custom_admin_site)
class EquipmentSlotAdmin(admin.ModelAdmin):
    list_display = ['player', 'slot', 'item', 'equipped_at']
    list_filter = ['slot']
    search_fields = ['player__user__username', 'item__name']

@admin.register(EnemyLoot, site=custom_admin_site)
class EnemyLootAdmin(admin.ModelAdmin):
    list_display = ['enemy', 'item', 'min_enemy_level', 'max_enemy_level', 'chance', 'quantity_min', 'quantity_max']
    list_filter = ['enemy', 'item__rarity', 'min_enemy_level']
    search_fields = ['enemy__name', 'item__name']


# ==========================================
# 🧙‍♂️ КВЕСТЫ И NPC
# ==========================================

class QuestObjectiveInline(admin.TabularInline):
    model = QuestObjective
    extra = 1

class DialogueOptionInline(admin.TabularInline):
    model = DialogueOption
    extra = 1

@admin.register(NPC, site=custom_admin_site)
class NPCAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [DialogueOptionInline]
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'description', 'image_path', 'location')
        }),
        ('Диалоги', {
            'fields': ('greeting_text', 'post_quest_dialogue'),
            'description': 'Приветствие — когда только открыли диалог. Диалог после сдачи — когда сдали квест.'
        }),
    )


@admin.register(Quest, site=custom_admin_site)
class QuestAdmin(admin.ModelAdmin):
    list_display = ['title', 'quest_line', 'order_in_line', 'giver_npc', 'required_level']
    list_filter = ['quest_line', 'giver_npc', 'required_level']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [QuestObjectiveInline]
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'slug', 'description', 'giver_npc', 'turn_in_npc', 'required_level', 'is_repeatable')
        }),
        ('Награды', {
            'fields': ('reward_exp', 'reward_gold', 'reward_item', 'reward_item_qty', 'reward_resource', 'reward_resource_qty', 'reward_vip_days')
        }),
    )

@admin.register(PlayerQuest, site=custom_admin_site)
class PlayerQuestAdmin(admin.ModelAdmin):
    list_display = ['player', 'quest', 'status', 'started_at']
    list_filter = ['status', 'quest']
    search_fields = ['player__user__username', 'quest__title']


# ==========================================
# 🛠 АДМИНКА КРАФТА
# ==========================================

class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ['item']

@admin.register(Recipe, site=custom_admin_site)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['name', 'result_item', 'npc', 'required_level', 'gold_cost']
    list_filter = ['npc', 'required_level']
    search_fields = ['name', 'result_item__name']
    inlines = [RecipeIngredientInline]
    autocomplete_fields = ['result_item', 'scroll_item']
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'description', 'npc')
        }),
        ('Результат крафта', {
            'fields': ('result_item', 'result_quantity')
        }),
        ('Изучение', {
            'fields': ('scroll_item', 'required_level', 'gold_cost'),
            'description': 'Свиток, который нужен для изучения, и условия.'
        }),
    )

@admin.register(PlayerRecipe, site=custom_admin_site)
class PlayerRecipeAdmin(admin.ModelAdmin):
    list_display = ['player', 'recipe', 'learned_at']
    list_filter = ['recipe']
    search_fields = ['player__user__username', 'recipe__name']


@admin.register(CombatSettings, site=custom_admin_site)
class CombatSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CombatSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(PlayerReport, site=custom_admin_site)
class PlayerReportAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'reporter', 'target', 'reason', 'is_resolved')
    list_filter = ('reason', 'is_resolved', 'created_at')
    search_fields = ('reporter__user__username', 'target__user__username', 'comment')
    readonly_fields = ('reporter', 'target', 'reason', 'comment', 'created_at')

    # Поле "Ответ модератора" должно быть редактируемым, чтобы мы могли вписать текст
    fields = ('reporter', 'target', 'reason', 'comment', 'moderator_comment', 'is_resolved', 'created_at')

    # 🆕 Перехватываем сохранение, чтобы отправить уведомление, если вписан ответ
    def save_model(self, request, obj, form, change):
        # Вызываем стандартное сохранение
        super().save_model(request, obj, form, change)

        # Если модератор вписал ответ и поставил галочку "Обработана", отправляем уведомление
        if obj.moderator_comment and obj.is_resolved:
            # Уведомление для того, на кого жаловались
            PlayerNotification.objects.create(
                player=obj.target,
                title="Сообщение от модератора",
                message=f"По вашей жалобе: {obj.moderator_comment}"
            )
            # Уведомление для того, кто жаловался
            PlayerNotification.objects.create(
                player=obj.reporter,
                title="Ответ по вашей жалобе",
                message=f"Ваша жалоба на игрока {obj.target.user.username} рассмотрена. Ответ: {obj.moderator_comment}"
            )
            
            # Чтобы не отправлять уведомления повторно при каждом редактировании,
            # можно временно обнулить комментарий (или добавить флаг, но для простоты пока так)
            # Но лучше просто напоминать админу не сохранять дважды.

    actions = ['ban_and_notify', 'mute_and_notify', 'dismiss_and_notify']

    def _send_notifications(self, report, action_text, reason):
        # 1. Уведомление нарушителю
        PlayerNotification.objects.create(
            player=report.target,
            title="Решение по жалобе",
            message=f"На вас поступила жалоба. Результат проверки: {action_text}. Комментарий: {reason}"
        )
        # 2. Уведомление тому, кто пожаловался
        PlayerNotification.objects.create(
            player=report.reporter,
            title="Ваша жалоба рассмотрена",
            message=f"Ваша жалоба на игрока {report.target.user.username} рассмотрена. Результат: {action_text}."
        )

    def ban_and_notify(self, request, queryset):
        for report in queryset:
            if not report.is_resolved:
                report.target.is_banned = True
                report.target.ban_reason = "Забанен по жалобе"
                report.target.save()
                report.is_resolved = True
                report.moderator_comment = "Забанен"
                report.save()
                
                self._send_notifications(report, "Игрок забанен", "Жалоба одобрена")
        self.message_user(request, f"Забанено и отправлено уведомлений: {queryset.count()}")
    ban_and_notify.short_description = "🔨 Забанить и уведомить"

    def mute_and_notify(self, request, queryset):
        for report in queryset:
            if not report.is_resolved:
                report.target.mute_until = timezone.now() + timedelta(hours=24)
                report.target.save()
                report.is_resolved = True
                report.moderator_comment = "Замучен"
                report.save()
                
                self._send_notifications(report, "Игрок замучен на 24 часа", "Жалоба одобрена")
        self.message_user(request, f"Замучено: {queryset.count()}")
    mute_and_notify.short_description = "🔇 Замутить и уведомить"

    def dismiss_and_notify(self, request, queryset):
        for report in queryset:
            if not report.is_resolved:
                report.is_resolved = True
                report.moderator_comment = "Нарушений не найдено"
                report.save()
                
                self._send_notifications(report, "Нарушений не найдено", "Жалоба отклонена")
        self.message_user(request, f"Жалоб отклонено: {queryset.count()}")
    dismiss_and_notify.short_description = "❌ Отклонить и уведомить"