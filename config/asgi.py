import os
from django.core.asgi import get_asgi_application

# 1. Сначала загружаем настройки
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 2. Инициализируем Django (это должно быть ДО импорта consumers)
django_asgi_app = get_asgi_application()

# 3. Только теперь импортируем остальное
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from game.consumers import ChatConsumer

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/chat/", ChatConsumer.as_asgi()),
        ])
    ),
})