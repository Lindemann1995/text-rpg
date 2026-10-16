from django.http import JsonResponse
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
import secrets
from .combat import start_combat, player_attack, player_defend, player_flee
from .models import (
    Scene, Player, CharacterClass, Choice, Flag,
    Location, Enemy, Combat, Item, Inventory,
    Trader, EquipmentSlot,
)
from .serializers import RegisterSerializer, PlayerSerializer, CharacterClassSerializer


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
    
    # Генерируем токен для подтверждения email
    token = secrets.token_urlsafe(32)
    player = user.player
    player.email_verification_token = token
    player.save()
    
    # "Отправляем" письмо (в консоль)
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
    
    # Устанавливаем класс
    player.character_class = character_class
    
    # Применяем базовые статы класса
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
    
    # Если игрок ещё не начинал — ставим стартовую сцену
    if not player.current_scene:
        start = Scene.objects.filter(is_start=True).first()
        if not start:
            return Response({'error': 'Стартовая сцена не найдена'}, status=404)
        player.current_scene = start
        player.save()
    
    serializer_data = scene_to_dict(player.current_scene)
    
    # Добавляем информацию об игроке
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
    
    # Ищем выбор среди выборов текущей сцены
    try:
        choice = Choice.objects.get(id=choice_id, scene=player.current_scene)
    except Choice.DoesNotExist:
        return Response({'error': 'Такого выбора нет в текущей сцене'}, status=404)
    
    # Сохраняем флаг, если есть
    if choice.set_flag:
        Flag.objects.update_or_create(
            player=player,
            name=choice.set_flag,
            defaults={'value': '1'},
        )
    
    # Переходим к следующей сцене
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
    
    # Проверка: нет ли уже активного боя
    active = Combat.objects.filter(player=player, status='active').first()
    if active:
        return Response({
            'error': 'У тебя уже есть активный бой',
            'combat_id': active.id,
        }, status=400)
    
    combat = start_combat(player, enemy)
    
    return Response({
        'combat_id': combat.id,
        'enemy_name': enemy.name,
        'enemy_hp': enemy.health,
        'player_hp': player.health,
        'player_max_hp': player.max_health,
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
    else:  # flee
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

@api_view(['POST'])
def location_hunt(request, slug):
    """Случайный враг из локации (не босс)"""
    import random
    
    try:
        location = Location.objects.get(slug=slug)
    except Location.DoesNotExist:
        return Response({'error': 'Локация не найдена'}, status=404)
    
    # Все обычные враги локации
    enemies = list(location.enemies.filter(enemy_type='normal'))
    
    if not enemies:
        return Response({'error': 'В этой локации нет врагов'}, status=404)
    
    # Случайный враг
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
    
    # Босс требует уровень выше min_level локации
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
    
    # Если HP уже полное
    if player.health >= player.max_health:
        return Response({
            'error': 'У тебя уже полное здоровье',
            'player_hp': player.health,
            'player_max_hp': player.max_health,
        }, status=400)
    
    # Стоимость: 10 золота × уровень
    cost = 10 * player.level
    
    if player.gold < cost:
        return Response({
            'error': f'Нужно {cost} золота (у тебя {player.gold})',
            'cost': cost,
            'player_gold': player.gold,
        }, status=400)
    
    # Списываем золото, восстанавливаем HP
    player.gold -= cost
    player.health = player.max_health
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
    
    # Ищем зелье в инвентаре
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
    
    # Применяем эффект
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
    
    # Уменьшаем количество
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
    
    # Проверяем лимит (макс 10 зелий в инвентаре)
    inv, created = Inventory.objects.get_or_create(
        player=player,
        item=item,
        defaults={'quantity': 0}
    )
    
    if inv.quantity >= 10:
        return Response({'error': 'Максимум 10 зелий в инвентаре'}, status=400)
    
    # Списываем золото, добавляем зелье
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
    
    # Списываем золото
    player.gold -= item.price
    player.save()
    
    # Добавляем в инвентарь
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
    
    # Проверка: предмет в инвентаре?
    try:
        inv = Inventory.objects.get(player=player, item=item)
    except Inventory.DoesNotExist:
        return Response({'error': 'У тебя нет этого предмета'}, status=400)
    
    # Проверка слота
    if not item.equip_slot:
        return Response({'error': 'Этот предмет нельзя надеть'}, status=400)
    
    # Проверка уровня
    if player.level < item.required_level:
        return Response({
            'error': f'Нужен уровень {item.required_level}'
        }, status=400)
    
    # Проверка класса
    allowed_classes = item.required_classes.all()
    if allowed_classes.exists():
        if not player.character_class:
            return Response({'error': 'Сначала выбери класс'}, status=400)
        if player.character_class not in allowed_classes:
            return Response({
                'error': f'Этот предмет только для: {", ".join([c.name for c in allowed_classes])}'
            }, status=400)
    
    # Снимаем текущий предмет из этого слота
    EquipmentSlot.objects.filter(player=player, slot=item.equip_slot).delete()
    
    # Снимаем старую экипировку (сбрасываем is_equipped)
    Inventory.objects.filter(player=player, item__equip_slot=item.equip_slot).update(is_equipped=False)
    
    # Надеваем новый
    EquipmentSlot.objects.create(
        player=player,
        slot=item.equip_slot,
        item=item,
    )
    inv.is_equipped = True
    inv.save()
    
    return Response({
        'message': f'Надето: {item.name}',
        'slot': item.equip_slot,
    })


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
    if not eq:
        return Response({'error': 'В этом слоте ничего нет'}, status=400)
    
    if eq.item:
        Inventory.objects.filter(player=player, item=eq.item).update(is_equipped=False)
    
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
        }
    
    return Response({'equipment': result})