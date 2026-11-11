import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Player
from social.models import GlobalChatMessage
from game.services.vip import get_vip_color  # 🆕 Импорт функции цвета

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'global_chat'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        username = data.get('username')
        
        if not message or not username:
            return

        # 1. Получаем роль и цвет игрока из БД
        role, color = await self.get_user_data(username)

        # 2. СОХРАНЯЕМ СООБЩЕНИЕ В БД (с цветом)
        saved = await self.save_message(username, message, color)
        if not saved:
            return

        # 3. Отправляем сообщение всем в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': saved.id,
                'message': message,
                'username': username,
                'role': role,
                'color': color,  # 🆕 Передаем цвет
                'created_at': saved.created_at.isoformat(),
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'id': event['id'],
            'message': event['message'],
            'username': event['username'],
            'role': event['role'],
            'color': event.get('color', ''),  # 🆕 Отдаем цвет клиенту
            'created_at': event['created_at'],
        }))

    @database_sync_to_async
    def get_user_data(self, username):
        try:
            player = Player.objects.get(user__username=username)
            # 🆕 Получаем цвет через сервис VIP
            return player.role, get_vip_color(player)
        except Player.DoesNotExist:
            return 'player', ''

    @database_sync_to_async
    def save_message(self, username, message_text, author_color):
        try:
            player = Player.objects.get(user__username=username)
            return GlobalChatMessage.objects.create(
                player=player, 
                message=message_text,
                author_color=author_color  # 🆕 Сохраняем цвет
            )
        except Player.DoesNotExist:
            print(f"Ошибка: игрок {username} не найден при сохранении сообщения")
            return None