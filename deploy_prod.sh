#!/bin/bash
set -e

echo "🚀 Деплой на PROD (text-rpg)"

cd /home/dev/text-rpg/

# Бэкап БД через Docker (безопасно)
echo "💾 Бэкап БД..."
mkdir -p ~/backups
BACKUP_FILE=~/backups/text_rpg_$(date +%Y%m%d_%H%M%S).sql
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U text_rpg_user text_rpg_db > "$BACKUP_FILE"

# Обновление кода
git pull origin main

# Пересборка и запуск
docker compose -f docker-compose.prod.yml up -d --build

echo "✅ PROD обновлён!"