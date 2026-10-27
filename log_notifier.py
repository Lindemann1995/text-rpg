import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ==== НАСТРОЙКИ ====
TELEGRAM_TOKEN = '9117019046:AAFMxVBuo_R4GJJdUQ05BwqwUgo91YS2_Qk' # Токен от BotFather (после /revoke)
TELEGRAM_CHAT_ID = '1987927404'
LOG_FILE = 'django_errors.log'
# ===================

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

def watch_logs():
    print("Скрипт запущен. Слежу за файлом...")
    
    # Открываем файл и прыгаем в конец (чтобы не отправлять старые ошибки)
    if not os.path.exists(LOG_FILE):
        print(f"Файл {LOG_FILE} не найден. Жду...")
        while not os.path.exists(LOG_FILE):
            time.sleep(10)
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(5) # Ждем 5 секунд, если новых строк нет
                continue
            
            # Если появилась новая ошибка — шлем в Telegram
            if line.strip():
                send_telegram_message(f"🚨 <b>Ошибка на сервере:</b>\n<pre>{line}</pre>")

if __name__ == '__main__':
    watch_logs()