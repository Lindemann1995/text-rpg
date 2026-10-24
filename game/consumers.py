import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Player
from social.models import GlobalChatMessage # 🆕 Импортируем модель чата

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

        # 1. Получаем роль игрока из БД
        role = await self.get_user_role(username)

        # 2. 🆕 СОХРАНЯЕМ СООБЩЕНИЕ В БД
        await self.save_message(username, message)

        # 3. Отправляем сообщение всем в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'role': role,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'role': event['role'],
        }))

    @database_sync_to_async
    def get_user_role(self, username):
        try:
            player = Player.objects.get(user__username=username)
            return player.role
        except Player.DoesNotExist:
            return 'player'

    # 🆕 НОВЫЙ МЕТОД ДЛЯ СОХРАНЕНИЯ
    @database_sync_to_async
    def save_message(self, username, message_text):
        try:
            player = Player.objects.get(user__username=username)
            GlobalChatMessage.objects.create(player=player, message=message_text)
        except Player.DoesNotExist:
            print(f"Ошибка: игрок {username} не найден при сохранении сообщения")