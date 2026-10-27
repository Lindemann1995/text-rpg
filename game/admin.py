from django.contrib import admin
from .models import (
    CharacterClass, Player, Scene, Choice, Flag, Item, Inventory,
    Location, Enemy, Combat, Trader, EquipmentSlot, EnemyLoot, 
    NPC, DialogueOption, QuestLine, Quest, QuestObjective, PlayerQuest, Recipe, RecipeIngredient, PlayerRecipe, CombatSettings, 
)


@admin.register(CharacterClass)
class CharacterClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_strength', 'base_agility', 'base_intelligence']
    search_fields = ['name']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['user', 'character_class', 'level', 'experience', 'gold', 'faction', 'role'] # <--- Добавили role
    list_filter = ['character_class', 'faction', 'is_in_tutorial', 'role'] # <--- Добавили role
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
        ('Оффлайн-прогресс', { # <--- НОВЫЙ БЛОК
            'fields': ('last_offline_claim', 'offline_gold_rate')
        }),
        ('Прочее', {
            'fields': ('is_in_tutorial', 'email_verified', 'email_verification_token', 'enemies_killed')
        }),
    )

@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'location', 'scene_type', 'is_start']
    list_filter = ['scene_type', 'is_tutorial', 'is_start', 'location']
    search_fields = ['title', 'slug', 'text']
    prepopulated_fields = {'slug': ('title',)}
    # inlines = [ChoiceInline]


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['text', 'scene', 'next_scene', 'order']
    list_filter = ['scene']
    search_fields = ['text']


@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = ['player', 'name', 'value', 'created_at']
    list_filter = ['name']
    search_fields = ['player__user__username', 'name']


@admin.register(Item)
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
        # --- НОВЫЙ БЛОК ДЛЯ РЕСУРСОВ ---
        ('Настройки ресурса', {
            'fields': ('max_stack', 'scroll_unlock'),
            'classes': ('collapse',),
            'description': 'Заполняйте эти поля, если тип предмета = "Ресурс"'
        }),
    )


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['player', 'item', 'quantity', 'is_equipped']
    list_filter = ['is_equipped', 'item__item_type']
    search_fields = ['player__user__username', 'item__name']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'min_level', 'is_available', 'is_guild_only'] # <--- добавили в список
    list_filter = ['is_available', 'is_guild_only', 'min_level'] # <--- добавили фильтр
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    # 🆕 Добавляем поля в форму редактирования
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


@admin.register(Enemy)
class EnemyAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'enemy_type', 'location', 'health', 'attack', 'defense', 'image_path', 'flip_image'] # <-- Добавили в список для быстрого просмотра
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
            'fields': ('image_path', 'bg_image_path', 'flip_image') # <-- ДОБАВИЛИ СЮДА!
        }),
        ('Способности', {
            'fields': ('abilities',)
        }),
    )

@admin.register(Combat)
class CombatAdmin(admin.ModelAdmin):
    list_display = ['player', 'enemy', 'status', 'turn', 'created_at']
    list_filter = ['status', 'enemy']
    search_fields = ['player__user__username', 'enemy__name']

@admin.register(Trader)
class TraderAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active']
    list_filter = ['location', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['items']


@admin.register(EquipmentSlot)
class EquipmentSlotAdmin(admin.ModelAdmin):
    list_display = ['player', 'slot', 'item', 'equipped_at']
    list_filter = ['slot']
    search_fields = ['player__user__username', 'item__name']

@admin.register(EnemyLoot)
class EnemyLootAdmin(admin.ModelAdmin):
    list_display = ['enemy', 'item', 'min_enemy_level', 'max_enemy_level', 'chance', 'quantity_min', 'quantity_max']
    list_filter = ['enemy', 'item__rarity', 'min_enemy_level']
    search_fields = ['enemy__name', 'item__name']


# ==========================================
# 🧙‍♂️ КВЕСТЫ И NPC
# ==========================================

# Инлайн для шагов квеста (добавляются прямо внутри квеста)
class QuestObjectiveInline(admin.TabularInline):
    model = QuestObjective
    extra = 1 # Сколько пустых строк показывать по умолчанию

# Инлайн для диалогов NPC (добавляются прямо внутри NPC)
class DialogueOptionInline(admin.TabularInline):
    model = DialogueOption
    extra = 1

@admin.register(NPC)
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


@admin.register(Quest)
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

@admin.register(PlayerQuest)
class PlayerQuestAdmin(admin.ModelAdmin):
    list_display = ['player', 'quest', 'status', 'started_at']
    list_filter = ['status', 'quest']
    search_fields = ['player__user__username', 'quest__title']

# ==========================================
# 🛠 АДМИНКА КРАФТА
# ==========================================

# Инлайн для ингредиентов (добавляются прямо внутри рецепта)
class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ['item'] # Удобный поиск предметов

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['name', 'result_item', 'npc', 'required_level', 'gold_cost']
    list_filter = ['npc', 'required_level']
    search_fields = ['name', 'result_item__name']
    inlines = [RecipeIngredientInline] # Добавляем ингредиенты прямо на странице рецепта
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

@admin.register(PlayerRecipe)
class PlayerRecipeAdmin(admin.ModelAdmin):
    list_display = ['player', 'recipe', 'learned_at']
    list_filter = ['recipe']
    search_fields = ['player__user__username', 'recipe__name']

from django.contrib import admin
from .models import CombatSettings

@admin.register(CombatSettings)
class CombatSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Запрещаем создавать больше одной записи настроек
        return not CombatSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удалять настройки
        return False