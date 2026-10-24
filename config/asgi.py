import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path, re_path
from game.consumers import ChatConsumer
from guilds.routing import websocket_urlpatterns as guild_ws
from guilds.middleware import JWTAuthMiddleware
from social.consumers import PrivateChatConsumer

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/chat/", ChatConsumer.as_asgi()),
            path('ws/chat/private/', PrivateChatConsumer.as_asgi()),
            
            # Исправленная строка для гильдейского чата:
            re_path(r"^ws/guild/", JWTAuthMiddleware(URLRouter(guild_ws))),
        ])
    ),
})