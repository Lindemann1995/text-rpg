from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
import traceback
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()

class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Достаем токен из строки запроса (ws://...?token=eyJ...)
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)

# 🆕 НАШ ОБРАБОТЧИК ОШИБОК ДЛЯ ОТПРАВКИ НА ПОЧТУ
class CustomErrorNotifierMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Логируем в консоль, чтобы видеть ошибку в терминале
        logger.error(f"Перехвачена ошибка: {exception}", exc_info=True)

        # Формируем тело письма
        error_trace = traceback.format_exc()
        subject = f"[Тень Древних] Ошибка 500: {request.path}"
        message = (
            f"Произошла ошибка на сервере!\n\n"
            f"URL: {request.path}\n"
            f"Метод: {request.method}\n"
            f"Ошибка: {exception}\n\n"
            f"Трейсбек:\n{error_trace}"
        )

        # Отправляем письмо (если DEBUG=False, чтобы не спамить при разработке)
        if not settings.DEBUG:
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMINS[0][1]],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Не удалось отправить письмо об ошибке: {e}")

        return None