#!/bin/bash
# Скрипт для настройки Docker контейнера на сервере

set -e

echo "📋 Этот скрипт поможет настроить Docker контейнер с bind mount"
echo ""

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден!"
    echo ""
    echo "Создайте .env файл на сервере с переменными окружения:"
    echo "  BOT_TOKEN=ваш_токен"
    echo "  OPENAI_API_KEY=ваш_ключ"
    echo "  # и другие переменные..."
    echo ""
    echo "Файл .env НЕ должен попадать в Git (уже в .gitignore)"
    exit 1
fi

CONTAINER_NAME="tg-miniapp-bot-1"
IMAGE_NAME="tg-miniapp-bot"
SERVER_PATH="/root/ai_trainer_cursor"

echo "🛑 Останавливаю старый контейнер..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

echo "🔨 Собираю Docker образ..."
docker build -t "$IMAGE_NAME" .

echo "🚀 Запускаю контейнер с bind mount в $SERVER_PATH..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --env-file "$SERVER_PATH/.env" \
    -v "$SERVER_PATH:/app" \
    -w /app \
    "$IMAGE_NAME" \
    python bot.py

echo "✅ Контейнер запущен!"
echo ""
echo "Проверка статуса:"
docker ps | grep "$CONTAINER_NAME" || echo "Контейнер не найден"

echo ""
echo "Логи (последние 20 строк):"
docker logs --tail 20 "$CONTAINER_NAME" 2>&1 || echo "Не удалось получить логи"
