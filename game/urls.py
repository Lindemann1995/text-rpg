from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import report_player
from . import views
# 🆕 ИМПОРТИРУЕМ КЛАССЫ ДЛЯ КВЕСТОВ
from .views import (
    NPCDetailView, 
    PlayerQuestsView, 
    AcceptQuestView, 
    CompleteQuestView,
    AllQuestsView,
    delete_account, 
)

app_name = 'game'

urlpatterns = [
    # Сцены
    path('chat/history/', views.get_chat_history, name='chat_history'),
    path('player/notifications/', views.get_notifications, name='get_notifications'),
    path('player/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('player/report/', report_player, name='report_player'),
    path('start/', views.start_scene, name='start_scene'),
    path('scene/current/', views.current_scene, name='current_scene'),
    path('scene/choose/', views.choose_in_scene, name='choose_in_scene'),
    path('scene/<slug:slug>/', views.get_scene, name='get_scene'),
    path('player/delete/', delete_account, name='delete_account'),
    # Бой
    path('combat/start/', views.combat_start, name='combat_start'),
    path('combat/<int:combat_id>/action/', views.combat_action, name='combat_action'),
    path('combat/<int:combat_id>/', views.combat_state, name='combat_state'),
    
    # Локации
    path('locations/', views.get_locations, name='get_locations'),
    path('location/<slug:slug>/enemies/', views.location_enemies, name='location_enemies'),
    path('location/<slug:slug>/hunt/', views.location_hunt, name='location_hunt'),
    path('location/<slug:slug>/boss/', views.location_boss, name='location_boss'),
    
    # Аутентификация
    path('auth/register/', views.register, name='register'),
    path('auth/verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    
    # Игрок
    path('player/offline-reward/', views.claim_offline_progress, name='claim_offline_progress'),
    path('player/me/', views.me, name='me'),
    path('player/classes/', views.list_classes, name='list_classes'),
    path('player/choose-class/', views.choose_class, name='choose_class'),
    path('player/rest/', views.player_rest, name='player_rest'),
    
    # Зелья
    path('player/use-potion/', views.use_potion, name='use_potion'),
    path('player/potions/', views.get_potions, name='get_potions'),
    path('shop/buy-potion/', views.buy_potion, name='buy_potion'),
    path('vip/status/', views.vip_status, name='vip_status'),
    path('vip/items/', views.vip_items, name='vip_items'),
    path('vip/activate/', views.vip_activate, name='vip_activate'),
    
    # Торговцы
    path('location/<slug:location_slug>/traders/', views.traders_list, name='traders_list'),
    path('trader/<slug:slug>/', views.trader_detail, name='trader_detail'),
    path('trader/<slug:slug>/buy/', views.trader_buy, name='trader_buy'),
    
    # Инвентарь и экипировка
    path('player/inventory/', views.player_inventory, name='player_inventory'),
    path('player/equipment/', views.player_equipment, name='player_equipment'),
    path('player/equip/', views.player_equip, name='player_equip'),
    path('player/unequip/', views.player_unequip, name='player_unequip'),
    path('player/equip/discard/', views.player_discard, name='player_discard'),

    # 🆕 Квесты и NPC
    path('npc/<slug:npc_slug>/', NPCDetailView.as_view(), name='npc_detail'),
    path('quests/', PlayerQuestsView.as_view(), name='player_quests'),
    path('quests/accept/', AcceptQuestView.as_view(), name='accept_quest'),
    path('quests/complete/', CompleteQuestView.as_view(), name='complete_quest'),
    path('quests/all/', AllQuestsView.as_view(), name='all_quests'),

    # 🛠 КРАФТ
    path('npc/<slug:npc_slug>/recipes/', views.get_npc_recipes, name='get_npc_recipes'),
    path('craft/learn/', views.learn_recipe, name='learn_recipe'),
    path('craft/create/', views.craft_item, name='craft_item'),
    path('craft/scrolls/', views.get_player_scrolls, name='player_scrolls'),
    path('player/upgrade-stat/', views.upgrade_stat, name='upgrade_stat'),
]