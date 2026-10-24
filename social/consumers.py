import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken
from game.models import Player
from .models import PrivateMessage

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Достаем токен из URL (?token=...)
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if not token:
            await self.close()
            return

        # 2. Валидируем токен и получаем пользователя
        self.user = await self.get_user_from_token(token)
        if not self.user:
            await self.close()
            return

        # Имя группы для отправки сообщений (твой личный канал)
        self.room_group_name = f'private_{self.user.username}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        receiver_username = data.get('receiver')
        message_text = data.get('message')
        
        if not receiver_username or not message_text:
            return

        # Сохраняем сообщение в БД
        msg = await self.save_message(receiver_username, message_text)
        if not msg:
            return

        # Отправляем сообщение получателю (ему прилетит в реальном времени)
        await self.channel_layer.group_send(
            f'private_{receiver_username}',
            {
                'type': 'chat_message',
                'message': message_text,
                'sender': self.user.username,
                'created_at': msg.created_at.strftime('%H:%M')
            }
        )
        
        # Отправляем эхо себе (чтобы твое сообщение сразу появилось в чате)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_text,
                'sender': self.user.username,
                'created_at': msg.created_at.strftime('%H:%M')
            }
        )

    async def chat_message(self, event):
        # Отправляем данные обратно во Flutter
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'created_at': event['created_at']
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            access_token = AccessToken(token)
            return User.objects.get(id=access_token['user_id'])
        except Exception:
            return None

    @database_sync_to_async
    def save_message(self, receiver_username, message):
        try:
            receiver = Player.objects.get(user__username=receiver_username)
            sender = self.user.player
            return PrivateMessage.objects.create(sender=sender, receiver=receiver, message=message)
        except Player.DoesNotExist:
            return None