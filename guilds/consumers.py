import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import GuildChatMessage, Guild, GuildMember
from game.models import Player

class GuildChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.guild_id = self.scope['url_route']['kwargs']['guild_id']
        self.room_group_name = f'guild_{self.guild_id}'

        # Получаем пользователя
        self.user = self.scope.get('user')
        
        # Если user анонимный (токен не подтянулся), пробуем через токен
        if not self.user or self.user.is_anonymous:
            from urllib.parse import parse_qs
            query_string = self.scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]
            if token:
                self.user = await self.get_user_from_token(token)

        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        # Безопасно проверяем, в гильдии ли он
        is_member = await self.check_membership()
        if not is_member:
            await self.close()
            return

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
        message = data.get('message')
        if not message:
            return

        # 🆕 ВСЕ данные готовим в одном синхронном методе
        msg_data = await self.prepare_message_data(message)
        if not msg_data:
            return

        # Отправляем в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': msg_data['message'],
                'username': msg_data['username'],
                'rank_color': msg_data['rank_color'],
                'tag': msg_data['tag'],
                'time': msg_data['time'],
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'username': event.get('username', 'Unknown'),
            'rank_color': event.get('rank_color', '#FFFFFF'),
            'tag': event.get('tag', ''),
            'time': event.get('time', '--:--'),
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth.models import User
        try:
            access_token = AccessToken(token)
            return User.objects.get(id=access_token['user_id'])
        except Exception:
            return None

    @database_sync_to_async
    def check_membership(self):
        try:
            return GuildMember.objects.filter(player=self.user.player, guild_id=self.guild_id).exists()
        except Exception:
            return False

    @database_sync_to_async
    def prepare_message_data(self, message):
        """🆕 Вся работа с БД тут (в одном синхронном потоке)"""
        try:
            player = self.user.player
            guild = Guild.objects.get(id=self.guild_id)
            member = GuildMember.objects.get(player=player, guild=guild)

            # Сохраняем сообщение в БД
            GuildChatMessage.objects.create(
                guild=guild,
                player=player,
                message=message,
                rank_color=member.rank_color,
                tag=guild.tag,
            )

            return {
                'message': message,
                'username': self.user.username,
                'rank_color': member.rank_color,
                'tag': guild.tag,
                'time': timezone.now().strftime('%H:%M'),
            }
        except Exception as e:
            print(f"Ошибка подготовки сообщения: {e}")
            return None