from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

app_name = 'game'

urlpatterns = [
    # Сцены
    path('start/', views.start_scene, name='start_scene'),
    path('scene/current/', views.current_scene, name='current_scene'),    # ← ДО slug!
    path('scene/choose/', views.choose_in_scene, name='choose_in_scene'), # ← ДО slug!
    path('scene/<slug:slug>/', views.get_scene, name='get_scene'),        # ← В САМОМ КОНЦЕ
    # Бой
    path('combat/start/', views.combat_start, name='combat_start'),
    path('combat/<int:combat_id>/action/', views.combat_action, name='combat_action'),
    path('combat/<int:combat_id>/', views.combat_state, name='combat_state'),
    # Локации
    path('location/<slug:slug>/hunt/', views.location_hunt, name='location_hunt'),
    path('location/<slug:slug>/boss/', views.location_boss, name='location_boss'),
    # Аутентификация
    path('auth/register/', views.register, name='register'),
    path('auth/verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    
    # Игрок
    path('player/me/', views.me, name='me'),
    path('player/classes/', views.list_classes, name='list_classes'),
    path('player/choose-class/', views.choose_class, name='choose_class'),
    path('player/rest/', views.player_rest, name='player_rest'),
    # Зелья
    path('player/use-potion/', views.use_potion, name='use_potion'),
    path('player/potions/', views.get_potions, name='get_potions'),
    path('shop/buy-potion/', views.buy_potion, name='buy_potion'),
    # Торговцы
    path('location/<slug:location_slug>/traders/', views.traders_list, name='traders_list'),
    path('trader/<slug:slug>/', views.trader_detail, name='trader_detail'),
    path('trader/<slug:slug>/buy/', views.trader_buy, name='trader_buy'),
    
    # Инвентарь и экипировка
    path('player/inventory/', views.player_inventory, name='player_inventory'),
    path('player/equipment/', views.player_equipment, name='player_equipment'),
    path('player/equip/', views.player_equip, name='player_equip'),
    path('player/unequip/', views.player_unequip, name='player_unequip'),
]