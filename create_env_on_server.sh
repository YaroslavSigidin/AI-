#!/bin/bash
# Скрипт для создания .env файла на сервере

set -e

SERVER_HOST="85.193.89.214"
SERVER_USER="root"
SERVER_PATH="/root/ai_trainer_cursor"

echo "📝 Создание .env файла на сервере"
echo ""
echo "⚠️  ВАЖНО: Этот скрипт создаст БАЗОВЫЙ .env файл"
echo "Вам нужно будет ЗАПОЛНИТЬ переменные значениями вручную!"
echo ""

# Создаем базовый .env файл на сервере
ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
cd /root/ai_trainer_cursor

# Создаем базовый .env файл, если его нет
if [ ! -f .env ]; then
    cat > .env << 'ENVFILE'
# Переменные окружения для бота
# ЗАПОЛНИТЕ ЗНАЧЕНИЯ ВРУЧНУЮ!

# Telegram Bot Token (ОБЯЗАТЕЛЬНО!)
BOT_TOKEN=

# OpenAI/DeepSeek API Key (ОБЯЗАТЕЛЬНО!)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# Yandex Speech-to-Text (используйте IAM-токен или API-ключ)
# Рекомендуется использовать YC_IAM_TOKEN (более безопасно)
YC_IAM_TOKEN=
YC_API_KEY=
YC_STT_LANG=ru-RU

# YooKassa (платежи)
YK_SHOP_ID=
YK_SECRET_KEY=
YK_RETURN_URL=https://t.me

# Цены и лимиты
PAY_PRICE_RUB=1490.00
PAY_FREE_LIMIT=15
PAY_SUB_DAYS=30

# Промокоды
PAY_PROMO_CODES=sigidingo
PROMO_CODES=

# Базы данных
PAYWALL_DB=paywall.db
ACCESS_DB=access.sqlite3

# API
API_BASE_URL=http://api:8000

# Web App URL
WEBAPP_URL=https://sport-helper-robot.online/tracker.html
ENVFILE
    
    echo "✅ Базовый .env файл создан!"
    echo ""
    echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
    echo "1. Подключитесь к серверу: ssh root@85.193.89.214"
    echo "2. Отредактируйте файл: nano /root/ai_trainer_cursor/.env"
    echo "3. Заполните переменные BOT_TOKEN и OPENAI_API_KEY (минимум)"
    echo "4. Перезапустите контейнер: docker restart tg-miniapp-bot-1"
else
    echo "⚠️  .env файл уже существует!"
    echo "Используйте: nano /root/ai_trainer_cursor/.env для редактирования"
fi
EOF

echo ""
echo "✅ Готово!"
