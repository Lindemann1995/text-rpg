from django.contrib import admin
from .models import (
    CharacterClass, Player, Scene, Choice, Flag, Item, Inventory,
    Location, Enemy, Combat,
)


@admin.register(CharacterClass)
class CharacterClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_strength', 'base_agility', 'base_intelligence']
    search_fields = ['name']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['user', 'character_class', 'level', 'experience', 'gold', 'faction']
    list_filter = ['character_class', 'faction', 'is_in_tutorial']
    search_fields = ['user__username']

class ChoiceInline(admin.TabularInline):
    model = Choice
    fk_name = 'scene'  # ← вот эта строка
    extra = 1
    fields = ['text', 'next_scene', 'order', 'required_flag', 'set_flag']

@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'location', 'scene_type', 'is_start']
    list_filter = ['scene_type', 'is_tutorial', 'is_start', 'location']
    search_fields = ['title', 'slug', 'text']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ChoiceInline]


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
    list_display = ['name', 'item_type', 'rarity', 'price']
    list_filter = ['item_type', 'rarity']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['player', 'item', 'quantity', 'is_equipped']
    list_filter = ['is_equipped', 'item__item_type']
    search_fields = ['player__user__username', 'item__name']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'min_level', 'is_available']
    list_filter = ['is_available', 'min_level']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Enemy)
class EnemyAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'enemy_type', 'location', 'health', 'attack', 'defense']
    list_filter = ['enemy_type', 'location', 'level']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Combat)
class CombatAdmin(admin.ModelAdmin):
    list_display = ['player', 'enemy', 'status', 'turn', 'created_at']
    list_filter = ['status', 'enemy']
    search_fields = ['player__user__username', 'enemy__name']