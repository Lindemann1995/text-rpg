import traceback
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

class ASGIErrorNotifier:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                if message['status'] >= 500:
                    # Ошибка 500! Отправляем письмо
                    try:
                        path = scope.get('path', '/')
                        method = scope.get('method', 'GET')
                        subject = f"[Тень Древних] Ошибка 500: {path}"
                        message_text = f"Произошла ошибка 500.\nURL: {path}\nМетод: {method}"
                        
                        if not settings.DEBUG:
                            send_mail(
                                subject, message_text,
                                settings.DEFAULT_FROM_EMAIL,
                                [settings.ADMINS[0][1]],
                                fail_silently=False,
                            )
                    except Exception as e:
                        logger.error(f"Не удалось отправить письмо: {e}")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # Ловим исключение, если оно вылетело до отправки статуса
            try:
                path = scope.get('path', '/')
                method = scope.get('method', 'GET')
                subject = f"[Тень Древних] КРИТИЧЕСКАЯ ОШИБКА: {path}"
                message_text = f"Ошибка: {e}\nТрейсбек:\n{traceback.format_exc()}"
                
                if not settings.DEBUG:
                    send_mail(
                        subject, message_text,
                        settings.DEFAULT_FROM_EMAIL,
                        [settings.ADMINS[0][1]],
                        fail_silently=False,
                    )
            except Exception as mail_err:
                logger.error(f"Не удалось отправить письмо: {mail_err}")
            
            # Отправляем 500 клиенту, чтобы не было зависания
            await send({
                'type': 'http.response.start',
                'status': 500,
                'headers': [(b'content-type', b'text/plain')],
            })
            await send({
                'type': 'http.response.body',
                'body': b'Internal Server Error',
            })