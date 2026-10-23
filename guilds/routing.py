from django.urls import re_path

from .consumers import GuildChatConsumer


websocket_urlpatterns = [
    re_path(r'^(?P<guild_id>\d+)/$', GuildChatConsumer.as_asgi()),
]