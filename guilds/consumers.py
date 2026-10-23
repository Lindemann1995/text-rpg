import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import GuildMember, GuildChatMessage


class GuildChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.guild_id = self.scope['url_route']['kwargs']['guild_id']
        self.room_group_name = f'guild_{self.guild_id}'

        user = self.scope.get('user')
        print(f"=== WS CONNECT: guild_id={self.guild_id}, user={user}, is_auth={getattr(user, 'is_authenticated', False)} ===")

        member = await self.get_member()
        print(f"=== WS CONNECT: member found = {member} ===")

        if not member:
            print("=== WS CONNECT: MEMBER NOT FOUND, CLOSING 4003 ===")
            await self.close(code=4003)
            return

        self.member_info = member
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print("=== WS CONNECT: ACCEPTED ===")

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = (data.get('message') or '').strip()
        if not message:
            return
        if len(message) > 500:
            message = message[:500]

        username = self.member_info['username']
        rank = self.member_info['rank']
        rank_color = self.member_info['rank_color']
        tag = self.member_info['tag']

        # Сохраняем в историю
        msg_id = await self.save_message(message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'rank': rank,
                'rank_color': rank_color,
                'tag': tag,
                'message_id': msg_id,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'rank': event['rank'],
            'rank_color': event['rank_color'],
            'tag': event['tag'],
            'message_id': event.get('message_id'),
        }))

    async def guild_event(self, event):
        """Системное событие в гильд-чате (вступление, исключение и т.п.)."""
        await self.send(text_data=json.dumps({
            'system': True,
            'message': event['message'],
        }))

    @database_sync_to_async
    def get_member(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            print("=== get_member: user not authenticated ===")
            return None
        
        print(f"=== get_member: searching for user_id={user.id} in guild_id={self.guild_id} ===")
        
        m = GuildMember.objects.select_related('guild', 'player__user').filter(
            guild_id=self.guild_id, player__user=user,
        ).first()
        
        if not m:
            print(f"=== get_member: GuildMember NOT FOUND for user {user.username} in guild {self.guild_id} ===")
            return None
            
        return {
            'username': m.player.user.username,
            'rank': m.rank,
            'rank_color': m.rank_color,
            'tag': m.guild.tag,
        }

    @database_sync_to_async
    def save_message(self, message):
        user = self.scope['user']
        m = GuildMember.objects.select_related('player', 'guild').get(
            guild_id=self.guild_id, player__user=user,
        )
        msg = GuildChatMessage.objects.create(
            guild_id=self.guild_id, 
            player=m.player, 
            message=message,
            rank_color=m.rank_color, # Сохраняем цвет
            tag=m.guild.tag,         # Сохраняем тег
        )
        return msg.id