import json
import secrets
from datetime import timedelta
from django.contrib import messages
import uuid
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.core.mail import send_mail
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from social.models import GlobalChatMessage
from guilds.models import Guild
from guilds.services import get_guild_bonuses

from .combat import start_combat, player_attack, player_defend, player_flee
from .models import (
    Scene, Player, CharacterClass, Choice, Flag,
    Location, Enemy, Combat, Item, Inventory,
    Trader, EquipmentSlot,
    NPC, Quest, PlayerQuest, QuestLine, Recipe, RecipeIngredient, PlayerRecipe, OnlineHistory, PlayerReport, PlayerNotification,
)
from .serializers import (
    RegisterSerializer, PlayerSerializer, CharacterClassSerializer,
    NPCSerializer, QuestSerializer, PlayerQuestSerializer, AllQuestsSerializer
)


def apply_regen(player):
    """Ленивая регенерация HP. Восстанавливает 5% HP каждые 3 минуты."""
    max_hp = player.effective_max_health
    if player.health >= max_hp:
        return

    now = timezone.now()
    # Считаем время от последней регенерации, а не от последнего сохранения
    time_passed = (now - player.last_regen_at).total_seconds()

    if time_passed >= 180:
        ticks = int(time_passed // 180)
        regen_amount = int(max_hp * 0.05) * ticks
        player.health += regen_amount

        if player.health > max_hp:
            player.health = max_hp

        # Обновляем время последней регенерации и сохраняем ТОЛЬКО нужные поля
        player.last_regen_at = now
        player.save(update_fields=['health', 'last_regen_at'])
        print(f"=== РЕГЕНЕРАЦИЯ: {player.user.username} восстановил {regen_amount} HP. Теперь {player.health}/{max_hp} ===")


def scene_to_dict(scene):
    """Превращает сцену в словарь для JSON"""
    choices_data = []
    for choice in scene.choices.all().order_by('order'):
        choices_data.append({
            'id': choice.id,
            'text': choice.text,
            'next_scene_slug': choice.next_scene.slug if choice.next_scene else None,
            'set_flag': choice.set_flag,
        })

    return {
        'id': scene.id,
        'slug': scene.slug,
        'title': scene.title,
        'text': scene.text,
        'location': scene.location,
        'scene_type': scene.scene_type,
        'choices': choices_data,
    }


def start_scene(request):
    """Возвращает стартовую сцену"""
    scene = Scene.objects.filter(is_start=True).first()
    if not scene:
        return JsonResponse({'error': 'Стартовая сцена не найдена'}, status=404)

    return JsonResponse(scene_to_dict(scene), json_dumps_params={'ensure_ascii': False})


def get_scene(request, slug):
    """Возвращает сцену по её slug"""
    try:
        scene = Scene.objects.get(slug=slug)
    except Scene.DoesNotExist:
        return JsonResponse({'error': f'Сцена "{slug}" не найдена'}, status=404)

    return JsonResponse(scene_to_dict(scene), json_dumps_params={'ensure_ascii': False})


def get_tokens_for_user(user):
    """Генерирует JWT-токены для пользователя"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Регистрация нового игрока"""
    serializer = RegisterSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()

    # 🆕 Фиксируем согласие с политикой
    player = user.player
    player.privacy_accepted_at = timezone.now()
    player.privacy_version = '1.0'
    player.save(update_fields=['privacy_accepted_at', 'privacy_version'])

    token = secrets.token_urlsafe(32)
    player = user.player
    player.email_verification_token = token
    player.save()

    try:
        starter_sword = Item.objects.get(slug='rusty_sword')
        Inventory.objects.create(player=player, item=starter_sword, quantity=1, is_equipped=True)
        EquipmentSlot.objects.create(player=player, slot='weapon', item=starter_sword)
        player.strength += starter_sword.bonus_strength
        player.save()
    except Item.DoesNotExist:
        print("ОШИБКА: Стартовый меч не найден в базе!")

    verification_url = f'https://dev.api.code-nest.ru/api/auth/verify-email/{token}/'
    send_mail(
        subject='Подтверждение email — Тень Древних',
        message=f'Привет, {user.username}!\n\nПодтверди email: {verification_url}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    tokens = get_tokens_for_user(user)

    return Response({
        'message': 'Игрок создан. Проверь консоль сервера для подтверждения email.',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        },
        'tokens': tokens,
        'email_verified': False,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    """Подтверждение email по токену"""
    try:
        player = Player.objects.get(email_verification_token=token)
    except Player.DoesNotExist:
        return Response({
            'error': 'Неверный или устаревший токен'
        }, status=status.HTTP_400_BAD_REQUEST)

    player.email_verified = True
    player.email_verification_token = ''
    player.save()

    return Response({
        'message': 'Email успешно подтверждён!',
        'username': player.user.username,
    })


@api_view(['GET'])
def me(request):
    """Профиль текущего игрока"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({
            'error': 'Профиль игрока не найден'
        }, status=status.HTTP_404_NOT_FOUND)

    # Обновляем время последней активности (чтобы работал онлайн-статус)
    player.save()

    apply_regen(player)

    # 🆕 Записываем онлайн раз в минуту
    last_record = OnlineHistory.objects.order_by('-timestamp').first()
    if not last_record or (timezone.now() - last_record.timestamp) > timedelta(minutes=1):
        online_count = Player.objects.filter(
            last_seen__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        OnlineHistory.objects.create(online=online_count)

    serializer = PlayerSerializer(player)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_classes(request):
    """Список всех классов персонажей"""
    classes = CharacterClass.objects.all()
    serializer = CharacterClassSerializer(classes, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def choose_class(request):
    """Выбор класса персонажа"""
    class_id = request.data.get('class_id')

    if not class_id:
        return Response({
            'error': 'Не указан class_id'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        character_class = CharacterClass.objects.get(id=class_id)
    except CharacterClass.DoesNotExist:
        return Response({
            'error': 'Класс не найден'
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({
            'error': 'Профиль игрока не найден'
        }, status=status.HTTP_404_NOT_FOUND)

    player.character_class = character_class
    player.strength = character_class.base_strength
    player.agility = character_class.base_agility
    player.intelligence = character_class.base_intelligence
    player.endurance = character_class.base_endurance
    player.sanity = character_class.base_sanity
    player.save()

    serializer = PlayerSerializer(player)
    return Response({
        'message': f'Класс "{character_class.name}" выбран!',
        'player': serializer.data,
    })


@api_view(['GET'])
def current_scene(request):
    """Текущая сцена игрока"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль игрока не найден'}, status=404)

    apply_regen(player)

    if not player.current_scene:
        start = Scene.objects.filter(is_start=True).first()
        if not start:
            return Response({'error': 'Стартовая сцена не найдена'}, status=404)
        player.current_scene = start
        player.save()

    serializer_data = scene_to_dict(player.current_scene)

    serializer_data['player'] = {
        'username': player.user.username,
        'level': player.level,
        'gold': player.gold,
        'health': player.health,
        'max_health': player.max_health,
        'mana': player.mana,
        'max_mana': player.max_mana,
        'character_class': player.character_class.name if player.character_class else None,
    }

    return Response(serializer_data)


@api_view(['POST'])
def choose_in_scene(request):
    """Сделать выбор в текущей сцене"""
    choice_id = request.data.get('choice_id')

    if not choice_id:
        return Response({'error': 'Не указан choice_id'}, status=400)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль игрока не найден'}, status=404)

    if not player.current_scene:
        return Response({'error': 'Игрок не находится в сцене'}, status=400)

    try:
        choice = Choice.objects.get(id=choice_id, scene=player.current_scene)
    except Choice.DoesNotExist:
        return Response({'error': 'Такого выбора нет в текущей сцене'}, status=404)

    if choice.set_flag:
        Flag.objects.update_or_create(
            player=player,
            name=choice.set_flag,
            defaults={'value': '1'},
        )

    if choice.next_scene:
        player.current_scene = choice.next_scene
        player.save()

        return Response({
            'message': f'Выбор сделан: {choice.text}',
            'set_flag': choice.set_flag or None,
            'next_scene': scene_to_dict(choice.next_scene),
        })
    else:
        return Response({
            'message': f'Выбор сделан: {choice.text}',
            'set_flag': choice.set_flag or None,
            'next_scene': None,
            'is_end': True,
        })


@api_view(['POST'])
def combat_start(request):
    """Начать бой с врагом (по enemy_slug)"""
    enemy_slug = request.data.get('enemy_slug')

    if not enemy_slug:
        return Response({'error': 'Не указан enemy_slug'}, status=400)

    try:
        enemy = Enemy.objects.get(slug=enemy_slug)
    except Enemy.DoesNotExist:
        return Response({'error': 'Враг не найден'}, status=404)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль игрока не найден'}, status=404)

    apply_regen(player)

    active = Combat.objects.filter(player=player, status='active').first()
    if active:
        active.status = 'fled'
        active.finished_at = timezone.now()
        active.save()

    combat = start_combat(player, enemy)

    return Response({
        'combat_id': combat.id,
        'enemy_name': enemy.name,
        'enemy_hp': enemy.health,
        'enemy_image': enemy.image_path,
        'enemy_bg': enemy.bg_image_path,
        'enemy_flip': enemy.flip_image,
        'enemy_scale': enemy.scale,
        'player_hp': player.health,
        'player_max_hp': player.effective_max_health,
        'log': combat.log,
    })


@api_view(['POST'])
def combat_action(request, combat_id):
    """Сделать ход в бою (attack / defend / flee)"""
    action = request.data.get('action')

    if action not in ['attack', 'defend', 'flee']:
        return Response({'error': 'Неверное действие'}, status=400)

    try:
        combat = Combat.objects.get(id=combat_id, player=request.user.player)
    except Combat.DoesNotExist:
        return Response({'error': 'Бой не найден'}, status=404)

    if action == 'attack':
        result = player_attack(combat)
    elif action == 'defend':
        result = player_defend(combat)
    else:
        result = player_flee(combat)

    return Response(result)


@api_view(['GET'])
def combat_state(request, combat_id):
    """Получить состояние боя"""
    try:
        combat = Combat.objects.get(id=combat_id, player=request.user.player)
    except Combat.DoesNotExist:
        return Response({'error': 'Бой не найден'}, status=404)

    from .combat import _combat_to_dict
    return Response(_combat_to_dict(combat))


@api_view(['GET'])
def get_locations(request):
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    from guilds.services import get_guild, get_guild_bonuses
    player_guild = get_guild(player)
    bonuses = get_guild_bonuses(player)

    locations = Location.objects.filter(is_available=True).filter(
        Q(is_guild_only=False) | Q(is_guild_only=True, guild=player_guild)
    ).order_by('min_level')

    result = []
    for loc in locations:
        enemies = loc.enemies.filter(enemy_type='normal')

        if not enemies.exists() and loc.is_guild_only:
            enemies = Enemy.objects.filter(location__isnull=True, enemy_type='normal')

        enemies_data = []
        for e in enemies:
            loot_list = []
            for loot in e.loot_table.all():
                if loot.chance > 0:
                    loot_list.append({
                        'slug': loot.item.slug,
                        'name': loot.item.name,
                        'image_path': loot.item.image_path,
                        'rarity': loot.item.rarity,
                    })

            level_diff = player.level - e.level
            xp_reward = e.xp_reward
            gold_reward = e.gold_reward

            if level_diff >= 10:
                xp_reward = max(1, xp_reward // 10)
                gold_reward = max(0, gold_reward // 10)
            elif level_diff <= -5:
                xp_reward = int(xp_reward * 1.5)
                gold_reward = int(gold_reward * 1.5)

            xp_reward = int(xp_reward * bonuses['xp_multiplier'])
            gold_reward = int(gold_reward * bonuses['gold_multiplier'])

            enemies_data.append({
                'slug': e.slug,
                'name': e.name,
                'level': e.level,
                'health': e.health,
                'attack': e.attack,
                'defense': e.defense,
                'description': e.description,
                'image_path': e.image_path,
                'xp_reward': xp_reward,
                'gold_reward': gold_reward,
                'loot': loot_list,
            })

        result.append({
            'id': loc.id,
            'name': loc.name,
            'slug': loc.slug,
            'description': loc.description,
            'min_level': loc.min_level,
            'enemies': enemies_data,
            'location_type': loc.location_type,
        })

    return Response(result)


@api_view(['POST'])
def location_hunt(request, slug):
    import random
    try:
        location = Location.objects.get(slug=slug)
    except Location.DoesNotExist:
        return Response({'error': 'Локация не найдена'}, status=404)

    enemies = list(location.enemies.filter(enemy_type='normal'))

    if not enemies and location.is_guild_only:
        enemies = list(Enemy.objects.filter(location__isnull=True, enemy_type='normal'))

    if not enemies:
        return Response({'error': 'В этой локации нет врагов'}, status=404)

    enemy = random.choice(enemies)

    return Response({
        'enemy_slug': enemy.slug,
        'enemy_name': enemy.name,
        'enemy_level': enemy.level,
        'enemy_hp': enemy.health,
        'enemy_icon': enemy.icon,
    })


@api_view(['POST'])
def location_boss(request, slug):
    """Босс локации (проверка уровня)"""
    try:
        location = Location.objects.get(slug=slug)
    except Location.DoesNotExist:
        return Response({'error': 'Локация не найдена'}, status=404)

    boss = location.enemies.filter(enemy_type='boss').first()

    if not boss:
        return Response({'error': 'В этой локации нет босса'}, status=404)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль игрока не найден'}, status=404)

    required_level = location.min_level + 5

    if player.level < required_level:
        return Response({
            'error': f'Для боя с боссом нужен уровень {required_level}+',
            'player_level': player.level,
            'required_level': required_level,
        }, status=403)

    return Response({
        'enemy_slug': boss.slug,
        'enemy_name': boss.name,
        'enemy_level': boss.level,
        'enemy_hp': boss.health,
        'enemy_icon': boss.icon,
        'is_boss': True,
    })


@api_view(['POST'])
def player_rest(request):
    """Отдых — восстановление HP за золото"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль игрока не найден'}, status=404)

    if player.health >= player.max_health:
        return Response({
            'error': 'У тебя уже полное здоровье',
            'player_hp': player.health,
            'player_max_hp': player.max_health,
        }, status=400)

    cost = 10 * player.level

    if player.gold < cost:
        return Response({
            'error': f'Нужно {cost} золота (у тебя {player.gold})',
            'cost': cost,
            'player_gold': player.gold,
        }, status=400)

    player.gold -= cost
    player.health = player.effective_max_health
    player.save()

    return Response({
        'message': f'Ты отдохнул. Восстановлено {player.max_health} HP.',
        'cost': cost,
        'player_hp': player.health,
        'player_max_hp': player.max_health,
        'player_gold': player.gold,
    })


@api_view(['POST'])
def use_potion(request):
    """Использовать зелье в бою или вне боя"""
    potion_slug = request.data.get('potion_slug')

    if not potion_slug:
        return Response({'error': 'Не указан potion_slug'}, status=400)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    try:
        item = Item.objects.get(slug=potion_slug, item_type='potion')
    except Item.DoesNotExist:
        return Response({'error': 'Зелье не найдено'}, status=404)

    try:
        inv = Inventory.objects.get(player=player, item=item)
    except Inventory.DoesNotExist:
        return Response({'error': 'У тебя нет этого зелья'}, status=400)

    if inv.quantity <= 0:
        return Response({'error': 'Зелья закончились'}, status=400)

    if item.effect_type == 'heal_hp':
        if player.health >= player.max_health:
            return Response({'error': 'У тебя полное HP'}, status=400)
        old_hp = player.health
        player.health = min(player.max_health, player.health + item.effect_value)
        healed = player.health - old_hp
        message = f'Восстановлено {healed} HP'
    elif item.effect_type == 'heal_mp':
        if player.mana >= player.max_mana:
            return Response({'error': 'У тебя полная мана'}, status=400)
        old_mp = player.mana
        player.mana = min(player.max_mana, player.mana + item.effect_value)
        healed = player.mana - old_mp
        message = f'Восстановлено {healed} MP'
    else:
        return Response({'error': 'Неизвестный эффект'}, status=400)

    inv.quantity -= 1
    if inv.quantity <= 0:
        inv.delete()
    else:
        inv.save()

    player.save()

    return Response({
        'message': message,
        'player_hp': player.health,
        'player_max_hp': player.max_health,
        'player_mana': player.mana,
        'player_max_mana': player.max_mana,
        'remaining': inv.quantity if inv.id else 0,
    })


@api_view(['GET'])
def get_potions(request):
    """Список зелий игрока"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    potions = Inventory.objects.filter(
        player=player,
        item__item_type='potion'
    ).select_related('item')

    result = []
    for inv in potions:
        result.append({
            'item_id': inv.item.id,
            'slug': inv.item.slug,
            'name': inv.item.name,
            'icon': inv.item.icon,
            'effect_type': inv.item.effect_type,
            'effect_value': inv.item.effect_value,
            'quantity': inv.quantity,
        })

    return Response({'potions': result})


@api_view(['POST'])
def buy_potion(request):
    """Купить зелье у торговца"""
    potion_slug = request.data.get('potion_slug')

    if not potion_slug:
        return Response({'error': 'Не указан potion_slug'}, status=400)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    try:
        item = Item.objects.get(slug=potion_slug, item_type='potion')
    except Item.DoesNotExist:
        return Response({'error': 'Зелье не найдено'}, status=404)

    if player.gold < item.price:
        return Response({
            'error': f'Нужно {item.price} золота (у тебя {player.gold})',
        }, status=400)

    inv, created = Inventory.objects.get_or_create(
        player=player,
        item=item,
        defaults={'quantity': 0}
    )

    if inv.quantity >= 10:
        return Response({'error': 'Максимум 10 зелий в инвентаре'}, status=400)

    player.gold -= item.price
    inv.quantity += 1
    inv.save()
    player.save()

    return Response({
        'message': f'Куплено: {item.name}',
        'player_gold': player.gold,
        'quantity': inv.quantity,
    })


@api_view(['GET'])
def traders_list(request, location_slug):
    """Список торговцев в локации"""
    try:
        location = Location.objects.get(slug=location_slug)
    except Location.DoesNotExist:
        return Response({'error': 'Локация не найдена'}, status=404)

    traders = location.traders.filter(is_active=True)

    return Response({
        'location': location.name,
        'traders': [
            {
                'id': t.id,
                'slug': t.slug,
                'name': t.name,
                'description': t.description,
                'icon': t.icon,
                'items_count': t.items.count(),
            }
            for t in traders
        ]
    })


@api_view(['GET'])
def trader_detail(request, slug):
    """Товары конкретного торговца"""
    try:
        trader = Trader.objects.get(slug=slug, is_active=True)
    except Trader.DoesNotExist:
        return Response({'error': 'Торговец не найден'}, status=404)

    items = []
    for item in trader.items.all():
        items.append({
            'id': item.id,
            'slug': item.slug,
            'name': item.name,
            'description': item.description,
            'icon': item.icon,
            'image_path': item.image_path,
            'item_type': item.item_type,
            'rarity': item.rarity,
            'price': item.price,
            'bonus_strength': item.bonus_strength,
            'bonus_agility': item.bonus_agility,
            'bonus_intelligence': item.bonus_intelligence,
            'bonus_endurance': item.bonus_endurance,
            'bonus_sanity': item.bonus_sanity,
            'bonus_health': item.bonus_health,
            'bonus_mana': item.bonus_mana,
            'equip_slot': item.equip_slot,
            'required_level': item.required_level,
            'required_classes': [c.name for c in item.required_classes.all()],
        })

    return Response({
        'trader': {
            'slug': trader.slug,
            'name': trader.name,
            'description': trader.description,
            'icon': trader.icon,
        },
        'items': items,
    })


@api_view(['POST'])
def trader_buy(request, slug):
    """Купить предмет у торговца"""
    item_slug = request.data.get('item_slug')

    if not item_slug:
        return Response({'error': 'Не указан item_slug'}, status=400)

    try:
        trader = Trader.objects.get(slug=slug, is_active=True)
    except Trader.DoesNotExist:
        return Response({'error': 'Торговец не найден'}, status=404)

    try:
        item = trader.items.get(slug=item_slug)
    except Item.DoesNotExist:
        return Response({'error': 'Товар не найден у этого торговца'}, status=404)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    if player.gold < item.price:
        return Response({
            'error': f'Нужно {item.price} золота (у тебя {player.gold})'
        }, status=400)

    player.gold -= item.price
    player.save()

    inv, created = Inventory.objects.get_or_create(
        player=player,
        item=item,
        defaults={'quantity': 0}
    )
    inv.quantity += 1
    inv.save()

    return Response({
        'message': f'Куплено: {item.name}',
        'player_gold': player.gold,
        'quantity': inv.quantity,
    })


@api_view(['GET'])
def player_inventory(request):
    """Инвентарь игрока"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    inv_items = Inventory.objects.filter(
        player=player
    ).select_related('item')

    inv_items = inv_items.filter(is_equipped=False)

    result = []
    for inv in inv_items:
        item = inv.item
        result.append({
            'item_id': item.id,
            'slug': item.slug,
            'name': item.name,
            'icon': item.icon,
            'item_type': item.item_type,
            'rarity': item.rarity,
            'quantity': inv.quantity,
            'is_equipped': inv.is_equipped,
            'image_path': item.image_path,
            'equip_slot': item.equip_slot,
            'required_level': item.required_level,
            'required_classes': [c.name for c in item.required_classes.all()],
            'bonus_strength': item.bonus_strength,
            'bonus_agility': item.bonus_agility,
            'bonus_intelligence': item.bonus_intelligence,
            'bonus_endurance': item.bonus_endurance,
            'bonus_sanity': item.bonus_sanity,
            'bonus_health': item.bonus_health,
            'bonus_mana': item.bonus_mana,
        })

    return Response({'items': result})


@api_view(['POST'])
def player_equip(request):
    """Надеть предмет"""
    item_slug = request.data.get('item_slug')

    if not item_slug:
        return Response({'error': 'Не указан item_slug'}, status=400)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    try:
        item = Item.objects.get(slug=item_slug)
    except Item.DoesNotExist:
        return Response({'error': 'Предмет не найден'}, status=404)

    try:
        inv = Inventory.objects.get(player=player, item=item)
    except Inventory.DoesNotExist:
        return Response({'error': 'У тебя нет этого предмета'}, status=400)

    if not item.equip_slot:
        return Response({'error': 'Этот предмет нельзя надеть'}, status=400)

    if player.level < item.required_level:
        return Response({'error': f'Нужен уровень {item.required_level}'}, status=400)

    allowed_classes = item.required_classes.all()
    if allowed_classes.exists():
        if not player.character_class:
            return Response({'error': 'Сначала выбери класс'}, status=400)
        if player.character_class not in allowed_classes:
            return Response({'error': f'Этот предмет только для: {", ".join([c.name for c in allowed_classes])}'}, status=400)

    old_eq = EquipmentSlot.objects.filter(player=player, slot=item.equip_slot).first()
    if old_eq and old_eq.item:
        old_item = old_eq.item
        player.strength -= old_item.bonus_strength
        player.agility -= old_item.bonus_agility
        player.intelligence -= old_item.bonus_intelligence
        player.endurance -= old_item.bonus_endurance
        player.sanity -= old_item.bonus_sanity
        player.max_health -= old_item.bonus_health
        player.max_mana -= old_item.bonus_mana

    EquipmentSlot.objects.filter(player=player, slot=item.equip_slot).delete()
    EquipmentSlot.objects.create(player=player, slot=item.equip_slot, item=item)

    player.strength += item.bonus_strength
    player.agility += item.bonus_agility
    player.intelligence += item.bonus_intelligence
    player.endurance += item.bonus_endurance
    player.sanity += item.bonus_sanity
    player.max_health += item.bonus_health
    player.max_mana += item.bonus_mana
    player.save()

    Inventory.objects.filter(player=player, item__equip_slot=item.equip_slot).update(is_equipped=False)
    inv.is_equipped = True
    inv.save()

    return Response({'message': f'Надето: {item.name}', 'slot': item.equip_slot})


@api_view(['POST'])
def player_unequip(request):
    """Снять предмет"""
    slot = request.data.get('slot')

    if not slot:
        return Response({'error': 'Не указан slot'}, status=400)

    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    eq = EquipmentSlot.objects.filter(player=player, slot=slot).first()
    if not eq or not eq.item:
        return Response({'error': 'В этом слоте ничего нет'}, status=400)

    item = eq.item

    player.strength -= item.bonus_strength
    player.agility -= item.bonus_agility
    player.intelligence -= item.bonus_intelligence
    player.endurance -= item.bonus_endurance
    player.sanity -= item.bonus_sanity
    player.max_health -= item.bonus_health
    player.max_mana -= item.bonus_mana

    if player.character_class:
        if player.strength < player.character_class.base_strength:
            player.strength = player.character_class.base_strength
        if player.agility < player.character_class.base_agility:
            player.agility = player.character_class.base_agility
        if player.intelligence < player.character_class.base_intelligence:
            player.intelligence = player.character_class.base_intelligence
        if player.endurance < player.character_class.base_endurance:
            player.endurance = player.character_class.base_endurance
        if player.sanity < player.character_class.base_sanity:
            player.sanity = player.character_class.base_sanity
    else:
        if player.strength < 1: player.strength = 1
        if player.agility < 1: player.agility = 1
        if player.intelligence < 1: player.intelligence = 1
        if player.endurance < 1: player.endurance = 1
        if player.sanity < 1: player.sanity = 1

    if player.health > player.max_health: player.health = player.max_health
    if player.mana > player.max_mana: player.mana = player.max_mana
    if player.health < 1: player.health = 1
    if player.mana < 1: player.mana = 1

    player.save()
    Inventory.objects.filter(player=player, item=item).update(is_equipped=False)
    eq.delete()

    return Response({'message': 'Снято'})


@api_view(['GET'])
def player_equipment(request):
    """Что надето на игроке"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    slots = EquipmentSlot.objects.filter(player=player).select_related('item')

    result = {}
    for eq in slots:
        result[eq.slot] = {
            'slug': eq.item.slug if eq.item else None,
            'name': eq.item.name if eq.item else None,
            'icon': eq.item.icon if eq.item else None,
            'rarity': eq.item.rarity if eq.item else None,
            'equip_slot': eq.slot,
            'image_path': eq.item.image_path if eq.item else None,
            'bonus_strength': eq.item.bonus_strength if eq.item else 0,
            'bonus_endurance': eq.item.bonus_endurance if eq.item else 0,
            'bonus_agility': eq.item.bonus_agility if eq.item else 0,
            'bonus_intelligence': eq.item.bonus_intelligence if eq.item else 0,
            'bonus_sanity': eq.item.bonus_sanity if eq.item else 0,
            'bonus_health': eq.item.bonus_health if eq.item else 0,
            'bonus_mana': eq.item.bonus_mana if eq.item else 0,
        }

    return Response({'equipment': result})


@api_view(['GET'])
def location_enemies(request, slug):
    """Список врагов в локации"""
    try:
        location = Location.objects.get(slug=slug)
    except Location.DoesNotExist:
        return Response({'error': 'Локация не найдена'}, status=404)

    enemies = location.enemies.all()

    result = []
    for enemy in enemies:
        result.append({
            'slug': enemy.slug,
            'name': enemy.name,
            'level': enemy.level,
            'hp': enemy.health,
            'icon': '👹',
        })

    return Response({'enemies': result})


@api_view(['POST'])
def claim_offline_progress(request):
    """Сбор оффлайн-награды"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    now = timezone.now()
    time_passed = now - player.last_offline_claim
    hours_passed = int(time_passed.total_seconds() // 3600)

    if hours_passed < 1:
        return Response({'error': 'Ты уходил меньше чем на час. Возвращайся позже!'}, status=400)

    max_hours = 12
    hours_to_reward = min(hours_passed, max_hours)

    gold_reward = hours_to_reward * player.offline_gold_rate

    player.gold += gold_reward
    player.last_offline_claim = now
    player.save()

    return Response({
        'message': f'Пока тебя не было ({hours_to_reward} ч.), ты заработал {gold_reward} золота!',
        'gold_earned': gold_reward,
        'hours': hours_to_reward,
        'total_gold': player.gold
    })


# ==========================================
# 🆕 ЭНДПОИНТЫ ДЛЯ NPC И КВЕСТОВ
# ==========================================

class NPCDetailView(APIView):
    """Получить NPC и его диалоги"""
    permission_classes = [IsAuthenticated]

    def get(self, request, npc_slug):
        npc = get_object_or_404(NPC, slug=npc_slug)
        serializer = NPCSerializer(npc)
        return Response(serializer.data)


class PlayerQuestsView(APIView):
    """Получить список всех квестов игрока (в процессе и готовых к сдаче)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        player = request.user.player
        quests = PlayerQuest.objects.filter(player=player).exclude(status='completed')
        serializer = PlayerQuestSerializer(quests, many=True)
        return Response(serializer.data)


class AllQuestsView(APIView):
    """Получить список ВСЕХ квестов в игре (для вкладки 'Общие')"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        player = request.user.player

        all_quests = Quest.objects.filter(required_level__lte=player.level).order_by('required_level')

        player_quests = PlayerQuest.objects.filter(player=player)

        taken_ids = set()
        completed_ids = set()

        for pq in player_quests:
            if pq.status == 'completed':
                completed_ids.add(pq.quest_id)
            else:
                taken_ids.add(pq.quest_id)

        serializer = AllQuestsSerializer(all_quests, many=True)
        data = serializer.data

        filtered_data = []
        for quest_data in data:
            quest_id = quest_data['id']
            quest_obj = all_quests.get(id=quest_id)

            if quest_id in completed_ids and not quest_obj.is_repeatable:
                continue

            quest_data['is_taken'] = quest_id in taken_ids
            quest_data['is_new'] = (quest_id not in taken_ids) and (quest_id not in completed_ids)

            filtered_data.append(quest_data)

        return Response(filtered_data)


class AcceptQuestView(APIView):
    """Взять квест у NPC"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        player = request.user.player
        quest_id = request.data.get('quest_id')

        quest = get_object_or_404(Quest, id=quest_id)

        if player.level < quest.required_level:
            return Response({'error': f'Нужен {quest.required_level} уровень'}, status=400)

        if PlayerQuest.objects.filter(player=player, quest=quest).exists():
            return Response({'error': 'Квест уже взят'}, status=400)

        pq = PlayerQuest.objects.create(player=player, quest=quest)

        return Response({
            'success': True,
            'message': 'Квест принят',
            'quest_id': pq.id
        })


class CompleteQuestView(APIView):
    """Сдать квест NPC и получить награду"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        player = request.user.player
        player_quest_id = request.data.get('player_quest_id')

        pq = get_object_or_404(PlayerQuest, id=player_quest_id, player=player)

        if pq.status != 'ready':
            return Response({'error': 'Квест еще не выполнен'}, status=400)

        quest = pq.quest

        player.experience += quest.reward_exp
        player.gold += quest.reward_gold

        dropped_items = []

        if quest.reward_item and quest.reward_item_qty > 0:
            inv, created = Inventory.objects.get_or_create(player=player, item=quest.reward_item, defaults={'quantity': 0})
            inv.quantity += quest.reward_item_qty
            inv.save()

            dropped_items.append({
                'slug': quest.reward_item.slug,
                'name': quest.reward_item.name,
                'quantity': quest.reward_item_qty,
                'rarity': quest.reward_item.rarity,
            })

        if quest.reward_resource and quest.reward_resource_qty > 0:
            inv, created = Inventory.objects.get_or_create(player=player, item=quest.reward_resource, defaults={'quantity': 0})
            inv.quantity += quest.reward_resource_qty
            inv.save()

            dropped_items.append({
                'slug': quest.reward_resource.slug,
                'name': quest.reward_resource.name,
                'quantity': quest.reward_resource_qty,
                'rarity': quest.reward_resource.rarity,
            })

        player.save()

        pq.status = 'completed'
        pq.completed_at = timezone.now()
        pq.save()

        return Response({
            'success': True,
            'message': 'Квест сдан!',
            'exp': quest.reward_exp,
            'gold': quest.reward_gold,
            'dropped_items': dropped_items
        })


# ==========================================
# 🛠 API ДЛЯ КРАФТА
# ==========================================

@api_view(['GET'])
def get_npc_recipes(request, npc_slug):
    """Получить список изученных рецептов у конкретного NPC"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    try:
        npc = NPC.objects.get(slug=npc_slug)
    except NPC.DoesNotExist:
        return Response({'error': 'NPC не найден'}, status=404)

    if player.level < 7:
        return Response({
            'error': 'Достигните 7 уровня, чтобы крафтить предметы.',
            'required_level': 7,
            'player_level': player.level
        }, status=403)

    learned_recipes = PlayerRecipe.objects.filter(
        player=player,
        recipe__npc=npc
    ).select_related('recipe', 'recipe__result_item')

    recipes_data = []
    for pr in learned_recipes:
        recipe = pr.recipe
        result_item = recipe.result_item

        ingredients = []
        for ing in recipe.ingredients.all():
            inv = Inventory.objects.filter(player=player, item=ing.item).first()
            has_qty = inv.quantity if inv else 0

            ingredients.append({
                'slug': ing.item.slug,
                'name': ing.item.name,
                'image_path': ing.item.image_path,
                'required': ing.quantity,
                'has': has_qty
            })

        recipes_data.append({
            'id': recipe.id,
            'name': recipe.name,
            'description': recipe.description,
            'result_item': {
                'slug': result_item.slug,
                'name': result_item.name,
                'image_path': result_item.image_path,
                'rarity': result_item.rarity,
                'bonus_strength': result_item.bonus_strength,
                'bonus_agility': result_item.bonus_agility,
            },
            'ingredients': ingredients
        })

    return Response({'recipes': recipes_data})


@api_view(['POST'])
def learn_recipe(request):
    """Изучение рецепта из свитка"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    if player.level < 7:
        return Response({'error': 'Достигните 7 уровня, чтобы изучать рецепты.'}, status=403)

    scroll_slug = request.data.get('scroll_slug')
    if not scroll_slug:
        return Response({'error': 'Не указан scroll_slug'}, status=400)

    try:
        recipe = Recipe.objects.get(scroll_item__slug=scroll_slug)
    except Recipe.DoesNotExist:
        return Response({'error': 'Этот свиток не открывает никаких рецептов'}, status=404)

    if PlayerRecipe.objects.filter(player=player, recipe=recipe).exists():
        return Response({'error': 'Этот рецепт уже изучен'}, status=400)

    try:
        inv = Inventory.objects.get(player=player, item=recipe.scroll_item)
    except Inventory.DoesNotExist:
        return Response({'error': 'У вас нет этого свитка'}, status=400)
    if inv.quantity <= 0:
        return Response({'error': 'У вас нет этого свитка'}, status=400)

    if player.gold < recipe.gold_cost:
        return Response({'error': f'Не хватает золота. Нужно: {recipe.gold_cost}'}, status=400)

    player.gold -= recipe.gold_cost

    inv.quantity -= 1
    if inv.quantity <= 0:
        inv.delete()
    else:
        inv.save()

    player.save()

    PlayerRecipe.objects.create(player=player, recipe=recipe)

    return Response({
        'success': True,
        'message': f'Рецепт "{recipe.name}" изучен!',
        'recipe_id': recipe.id
    })


@api_view(['POST'])
def craft_item(request):
    """Скрафтить предмет по рецепту"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    recipe_id = request.data.get('recipe_id')
    if not recipe_id:
        return Response({'error': 'Не указан recipe_id'}, status=400)

    try:
        recipe = Recipe.objects.get(id=recipe_id)
    except Recipe.DoesNotExist:
        return Response({'error': 'Рецепт не найден'}, status=404)

    player_recipe = PlayerRecipe.objects.filter(player=player, recipe=recipe).first()
    if not player_recipe:
        return Response({'error': 'Вы не изучили этот рецепт'}, status=403)

    if player.level < recipe.required_level:
        return Response({'error': f'Нужен {recipe.required_level} уровень'}, status=400)

    missing_ingredients = []
    for ing in recipe.ingredients.all():
        inv = Inventory.objects.filter(player=player, item=ing.item).first()
        has_qty = inv.quantity if inv else 0
        if has_qty < ing.quantity:
            missing_ingredients.append(f'{ing.item.name} (нужно {ing.quantity}, есть {has_qty})')

    if missing_ingredients:
        return Response({
            'error': 'Не хватает ресурсов: ' + ', '.join(missing_ingredients)
        }, status=400)

    for ing in recipe.ingredients.all():
        inv = Inventory.objects.get(player=player, item=ing.item)
        inv.quantity -= ing.quantity
        if inv.quantity <= 0:
            inv.delete()
        else:
            inv.save()

    result_inv, created = Inventory.objects.get_or_create(
        player=player, item=recipe.result_item, defaults={'quantity': 0}
    )
    result_inv.quantity += recipe.result_quantity
    result_inv.save()

    player_recipe.delete()

    return Response({
        'success': True,
        'message': f'Вы создали: {recipe.result_item.name} x{recipe.result_quantity}',
        'item': {
            'slug': recipe.result_item.slug,
            'name': recipe.result_item.name,
            'image_path': recipe.result_item.image_path,
            'rarity': recipe.result_item.rarity,
            'quantity': recipe.result_quantity,
        }
    })


@api_view(['GET'])
def get_player_scrolls(request):
    """Получить список свитков (рецептов) в инвентаре игрока"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    scrolls = Inventory.objects.filter(
        player=player,
        item__learns_recipes__isnull=False
    ).select_related('item')

    result = []
    for inv in scrolls:
        item = inv.item
        recipe = item.learns_recipes.first()

        is_learned = PlayerRecipe.objects.filter(player=player, recipe=recipe).exists()

        result.append({
            'slug': item.slug,
            'name': item.name,
            'description': item.description,
            'image_path': item.image_path,
            'rarity': item.rarity,
            'quantity': inv.quantity,
            'recipe_name': recipe.name if recipe else 'Неизвестный рецепт',
            'recipe_id': recipe.id if recipe else None,
            'is_learned': is_learned,
        })

    return Response({'scrolls': result})


@api_view(['POST'])
def upgrade_stat(request):
    """Прокачка характеристики за очко"""
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    stat_name = request.data.get('stat')

    if player.stat_points <= 0:
        return Response({'error': 'У вас нет свободных очков'}, status=400)

    if stat_name not in ['strength', 'agility', 'intelligence', 'endurance', 'sanity']:
        return Response({'error': 'Неверная характеристика'}, status=400)

    current_val = getattr(player, stat_name)
    setattr(player, stat_name, current_val + 1)
    player.stat_points -= 1
    player.save()

    return Response({
        'success': True,
        'message': f'Характеристика {stat_name} увеличена!',
        'stat_points': player.stat_points,
        'new_value': getattr(player, stat_name),
    })


def admin_dashboard(request):
    total_players = Player.objects.count()
    total_gold = Player.objects.aggregate(Sum('gold'))['gold__sum'] or 0
    total_guilds = Guild.objects.count()

    context = {
        'total_players': total_players,
        'total_gold': total_gold,
        'total_guilds': total_guilds,
    }
    return render(request, 'admin/dashboard.html', context)


@staff_member_required
def beautiful_dashboard(request):
    total_players = Player.objects.count()
    new_players = Player.objects.filter(created_at__gte=timezone.now() - timedelta(days=1)).count()
    total_gold = Player.objects.aggregate(Sum('gold'))['gold__sum'] or 0
    total_guilds = Guild.objects.count()

    history = OnlineHistory.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).order_by('timestamp')

    labels = [h.timestamp.strftime('%H:%M') for h in history]
    data = [h.online for h in history]

    context = {
        'total_players': total_players,
        'new_players': new_players,
        'total_gold': total_gold,
        'total_guilds': total_guilds,
        'labels': json.dumps(labels),
        'data': json.dumps(data),
    }
    return render(request, 'dashboard.html', context)

@staff_member_required
def manage_roles(request):
    if request.method == 'POST':
        player_id = request.POST.get('player_id')
        new_role = request.POST.get('role')
        try:
            player = Player.objects.get(id=player_id)
            player.role = new_role
            player.save()

            # 🆕 Синхронизация с правами Django
            if new_role == 'admin':
                player.user.is_staff = True
                player.user.is_superuser = True
                player.user.save()
                # Добавляем в группу "Администратор" (если есть)
                admin_group, _ = Group.objects.get_or_create(name='Администратор')
                player.user.groups.add(admin_group)
            elif new_role == 'moderator':
                player.user.is_staff = True
                player.user.is_superuser = False
                player.user.save()
                # Добавляем в группу "Модератор"
                mod_group, _ = Group.objects.get_or_create(name='Модератор')
                player.user.groups.add(mod_group)
            else:
                # Если роль "Игрок" или "VIP" — снимаем права
                player.user.is_staff = False
                player.user.is_superuser = False
                player.user.save()
                # Убираем из групп
                player.user.groups.remove(*player.user.groups.all())

            messages.success(request, f'Роль игрока {player.user.username} изменена на {new_role}')
        except Player.DoesNotExist:
            messages.error(request, 'Игрок не найден')
        return redirect('manage_roles')

    players = Player.objects.select_related('user').all()
    return render(request, 'admin/manage_roles.html', {'players': players})

@staff_member_required
def chat_moderation(request):
    if request.method == 'POST':
        report_id = request.POST.get('report_id')
        player_id = request.POST.get('player_id')
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        duration = int(request.POST.get('duration', 0))

        try:
            player = Player.objects.get(id=player_id)
            if action == 'ban':
                player.is_banned = True
                player.ban_until = timezone.now() + timedelta(hours=duration) if duration > 0 else None
                player.ban_reason = reason
                player.save()
            elif action == 'mute':
                player.mute_until = timezone.now() + timedelta(hours=duration) if duration > 0 else None
                player.ban_reason = reason
                player.save()
            elif action == 'unban':
                player.is_banned = False
                player.ban_until = None
                player.mute_until = None
                player.ban_reason = ''
                player.save()

            if report_id:
                report = PlayerReport.objects.get(id=report_id)
                report.is_resolved = True
                report.moderator_comment = f'Действие: {action}. Причина: {reason}'
                report.save()

            messages.success(request, f'Действие "{action}" применено к {player.user.username}')
        except (Player.DoesNotExist, PlayerReport.DoesNotExist):
            messages.error(request, 'Игрок или жалоба не найдены')
        return redirect('chat_moderation')

    # Показываем только НЕОБРАБОТАННЫЕ жалобы
    reports = PlayerReport.objects.filter(is_resolved=False).select_related('reporter__user', 'target__user').order_by('-created_at')

    # Плюс список всех игроков для ручного поиска
    all_players = Player.objects.select_related('user').order_by('-level')

    return render(request, 'admin/chat_moderation.html', {
        'reports': reports,
        'all_players': all_players,
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_player(request):
    """Отправить жалобу на игрока"""
    try:
        reporter = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    target_username = request.data.get('target_username')
    reason = request.data.get('reason', 'other')
    comment = request.data.get('comment', '')

    if not target_username:
        return Response({'error': 'Не указан ник игрока'}, status=400)

    if target_username == reporter.user.username:
        return Response({'error': 'Нельзя пожаловаться на самого себя'}, status=400)

    try:
        target = Player.objects.get(user__username=target_username)
    except Player.DoesNotExist:
        return Response({'error': 'Игрок с таким ником не найден'}, status=404)

    # Проверяем, не отправлял ли он уже жалобу на этого игрока за последние 24 часа
    one_minute_ago = timezone.now() - timedelta(minutes=1)
    if PlayerReport.objects.filter(reporter=reporter, target=target, created_at__gte=one_minute_ago).exists():
        return Response({'error': 'Вы уже жаловались на этого игрока. Подождите минуту.'}, status=400)

    # Создаем жалобу
    report = PlayerReport.objects.create(
        reporter=reporter,
        target=target,
        reason=reason,
        comment=comment
    )

    return Response({
        'success': True,
        'message': 'Жалоба отправлена. Модераторы проверят её.',
        'report_id': report.id
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    notes = PlayerNotification.objects.filter(player=player)[:50]
    
    result = []
    for n in notes:
        result.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
        })

    return Response({'notifications': result})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    PlayerNotification.objects.filter(player=player, is_read=False).update(is_read=True)
    return Response({'success': True})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request):
    # Берем последние 50 сообщений
    messages = GlobalChatMessage.objects.select_related('player__user').order_by('-created_at')[:50]
    
    result = []
    for msg in reversed(messages): # Переворачиваем, чтобы старые были сверху
        local_dt = timezone.localtime(msg.created_at)  # 🆕 UTC → Europe/Moscow
        result.append({
            'id': msg.id,
            'username': msg.player.user.username,
            'message': msg.message,
            'role': msg.player.role,
            'time': local_dt.strftime('%H:%M'),
            'created_at': msg.created_at.isoformat(),  # 🆕 для клиента (ISO 8601 UTC)
        })
    
    return Response({'messages': result})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """
    Мягкое удаление аккаунта (анонимизация).
    Требуется подтверждение пароля для безопасности.
    """
    try:
        player = request.user.player
    except Player.DoesNotExist:
        return Response({'error': 'Профиль не найден'}, status=404)

    password = request.data.get('password')
    
    if not password or not request.user.check_password(password):
        return Response({'error': 'Неверный пароль'}, status=400)

    user = request.user
    
    # 1. Анонимизируем User
    user.is_active = False
    user.username = f"DeletedUser_{user.id}_{uuid.uuid4().hex[:4]}"
    user.email = f"deleted_{user.id}@deleted.local"
    user.set_unusable_password()
    user.save()

    # 2. Анонимизируем Player (если есть специфичные поля)
    player.email_verified = False
    player.email_verification_token = ''
    player.is_banned = True # Чтобы на всякий случай заблокировать
    player.ban_reason = 'Аккаунт удален пользователем'
    player.save()

    # 3. Логируем (когда сделаем аудит, перенесем туда)
    print(f"=== АККАУНТ УДАЛЕН: ID {user.id} ===")

    return Response({
        'success': True, 
        'message': 'Аккаунт успешно удален. Все персональные данные анонимизированы.'
    })