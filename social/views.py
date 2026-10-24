from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from game.models import Player
from .models import Friendship, PrivateMessage
from django.utils import timezone
from datetime import timedelta


@api_view(['POST'])
def send_friend_request(request):
    username = request.data.get('username')
    if not username:
        return Response({'error': 'Укажи никнейм'}, status=400)
    
    try:
        target = Player.objects.get(user__username=username)
    except Player.DoesNotExist:
        return Response({'error': 'Игрок не найден'}, status=404)
    
    player = request.user.player
    if player == target:
        return Response({'error': 'Нельзя добавить самого себя'}, status=400)
    
    if Friendship.objects.filter(
        (Q(from_player=player, to_player=target) | Q(from_player=target, to_player=player))
    ).exists():
        return Response({'error': 'Заявка уже отправлена или вы уже друзья'}, status=400)

    Friendship.objects.create(from_player=player, to_player=target)
    return Response({'success': True, 'message': f'Заявка отправлена игроку {username}'})


@api_view(['POST'])
def accept_friend_request(request):
    request_id = request.data.get('request_id')
    try:
        friend_req = Friendship.objects.get(id=request_id, to_player=request.user.player, status='pending')
    except Friendship.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=404)
    
    friend_req.status = 'accepted'
    friend_req.save()
    return Response({'success': True, 'message': 'Теперь вы друзья!'})


@api_view(['POST'])
def decline_friend_request(request):
    request_id = request.data.get('request_id')
    try:
        friend_req = Friendship.objects.get(id=request_id, to_player=request.user.player, status='pending')
    except Friendship.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=404)
    
    friend_req.status = 'declined'
    friend_req.save()
    return Response({'success': True})


@api_view(['GET'])
def get_friends_data(request):
    player = request.user.player
    
    # Обновляем время последней активности при заходе
    player.save() 
    
    now = timezone.now()
    online_threshold = now - timedelta(minutes=5)

    friends_list = []
    friendships = Friendship.objects.filter(
        (Q(from_player=player) | Q(to_player=player)),
        status='accepted'
    ).select_related('from_player__user', 'to_player__user')
    
    for f in friendships:
        friend = f.to_player if f.from_player == player else f.from_player
        
        # Проверяем, онлайн ли друг
        is_online = friend.last_seen >= online_threshold
        
        friends_list.append({
            'friendship_id': f.id, # ID для удаления
            'player_id': friend.id,
            'username': friend.user.username,
            'level': friend.level,
            'character_class': friend.character_class.name if friend.character_class else 'Без класса',
            'is_online': is_online,
        })
        
    # Сортируем: сначала онлайн, потом оффлайн
    friends_list.sort(key=lambda x: x['is_online'], reverse=True)
        
    incoming = Friendship.objects.filter(to_player=player, status='pending').select_related('from_player__user')
    incoming_list = [{
        'request_id': req.id,
        'from_username': req.from_player.user.username,
        'from_level': req.from_player.level,
        'from_class': req.from_player.character_class.name if req.from_player.character_class else 'Без класса',
    } for req in incoming]

    return Response({
        'friends': friends_list,
        'incoming_requests': incoming_list,
    })


@api_view(['POST'])
def remove_friend(request):
    friendship_id = request.data.get('friendship_id')
    try:
        # Ищем дружбу, где я либо отправитель, либо получатель
        friendship = Friendship.objects.get(
            Q(from_player=request.user.player) | Q(to_player=request.user.player),
            id=friendship_id
        )
        friendship.delete()
        return Response({'success': True, 'message': 'Удален из друзей'})
    except Friendship.DoesNotExist:
        return Response({'error': 'Дружба не найдена'}, status=404)


@api_view(['GET'])
def get_private_messages(request, username):
    player = request.user.player
    try:
        other_player = Player.objects.get(user__username=username)
    except Player.DoesNotExist:
        return Response({'error': 'Игрок не найден'}, status=404)
        
    PrivateMessage.objects.filter(sender=other_player, receiver=player, is_read=False).update(is_read=True)

    messages = PrivateMessage.objects.filter(
        (Q(sender=player, receiver=other_player) | Q(sender=other_player, receiver=player))
    ).order_by('created_at')
    
    data = [{
        'id': msg.id,
        'sender': msg.sender.user.username,
        'message': msg.message,
        'is_mine': msg.sender == player,
        'created_at': msg.created_at.strftime('%H:%M')
    } for msg in messages]
    
    return Response({'messages': data})