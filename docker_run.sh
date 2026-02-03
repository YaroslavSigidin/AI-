#!/bin/bash
# Скрипт для пересоздания Docker контейнера с правильной конфигурацией

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONTAINER_NAME="tg-miniapp-bot-1"
IMAGE_NAME="tg-miniapp-bot"

echo "🛑 Останавливаю и удаляю старый контейнер..."

docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден!"
    echo "Создайте .env файл с переменными окружения (BOT_TOKEN, OPENAI_API_KEY и т.д.)"
    exit 1
fi

echo "🔨 Собираю Docker образ..."
docker build -t "$IMAGE_NAME" .

echo "🚀 Запускаю контейнер с bind mount..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --env-file .env \
    -v "$(pwd):/app" \
    -w /app \
    -p 8010:8010 \
    "$IMAGE_NAME" \
    python bot.py

echo "✅ Контейнер запущен!"
echo ""
echo "Проверка статуса:"
docker ps | grep "$CONTAINER_NAME"

echo ""
echo "Логи (последние 20 строк):"
docker logs --tail 20 "$CONTAINER_NAME"
