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
from .models import Enemy, Combat

from .models import Scene, Player, CharacterClass, Choice, Flag
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