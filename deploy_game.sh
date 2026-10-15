#!/bin/bash
# deploy_game.sh — безопасный деплой «Тень Древних» на прод
# Использование: ./deploy_game.sh

set -e  # остановиться при любой ошибке

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🚀 Деплой Тень Древних${NC}"
echo "----------------------------"

cd ~/text-rpg

# 1. Бэкап БД
echo -e "${YELLOW}💾 Бэкап БД...${NC}"
mkdir -p ~/backups
DB_PASSWORD=$(grep DB_PASSWORD .env | cut -d '=' -f2)
BACKUP_FILE=~/backups/text_rpg_$(date +%Y%m%d_%H%M%S).sql
PGPASSWORD="$DB_PASSWORD" pg_dump -U text_rpg_user -h localhost text_rpg_db > "$BACKUP_FILE"
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo -e "${GREEN}✅ Бэкап: $BACKUP_FILE ($BACKUP_SIZE)${NC}"

# 2. git pull
echo -e "${YELLOW}📦 Обновление кода из Git...${NC}"
git pull origin main

# 3. Установка Python-зависимостей
echo -e "${YELLOW}🐍 Установка зависимостей...${NC}"
source venv/bin/activate
pip install -r requirements.txt --upgrade --quiet

# 4. Миграции
echo -e "${YELLOW}🗄️ Миграции...${NC}"
python manage.py migrate

# 5. Загрузка фикстур (сцен, классов, выборов)
echo -e "${YELLOW}📚 Загрузка контента (fixtures)...${NC}"
if [ -f game/fixtures/initial_data.json ]; then
    python manage.py loaddata game/fixtures/initial_data.json
    echo -e "${GREEN}✅ Контент загружен${NC}"
else
    echo -e "${YELLOW}⚠️ Фикстуры не найдены, пропускаем${NC}"
fi

# 6. Статика
echo -e "${YELLOW}📦 Сборка статики...${NC}"
python manage.py collectstatic --noinput

# 7. Проверка Django
echo -e "${YELLOW}🔍 Проверка Django...${NC}"
python manage.py check --deploy 2>&1 | head -20 || true

# 8. Перезапуск Daphne
echo -e "${YELLOW}🔄 Перезапуск Daphne...${NC}"
sudo systemctl restart text-rpg

echo ""
echo -e "${GREEN}✅ Деплой завершён!${NC}"
echo -e "${GREEN}🌐 Проверь: https://api.code-nest.ru${NC}"
echo -e "${YELLOW}💾 Бэкап: $BACKUP_FILE${NC}"
