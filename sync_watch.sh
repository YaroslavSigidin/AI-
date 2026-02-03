#!/bin/bash
# Скрипт автоматической синхронизации файлов при сохранении

set -e

# Проверяем наличие конфигурации
if [ ! -f deploy.conf ]; then
    echo "❌ Файл deploy.conf не найден!"
    echo "Скопируйте deploy.conf.example в deploy.conf и заполните параметры"
    exit 1
fi

source deploy.conf

# Проверяем обязательные параметры
if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ] || [ -z "$SERVER_PATH" ]; then
    echo "❌ Ошибка: не заданы параметры в deploy.conf"
    exit 1
fi

# Проверяем наличие fswatch (для macOS)
if ! command -v fswatch &> /dev/null; then
    echo "⚠️  fswatch не установлен. Устанавливаю через Homebrew..."
    if command -v brew &> /dev/null; then
        brew install fswatch
    else
        echo "❌ Homebrew не найден. Установите fswatch вручную:"
        echo "   brew install fswatch"
        exit 1
    fi
fi

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 Запуск автоматической синхронизации...${NC}"
echo -e "${BLUE}📁 Локальная папка: $(pwd)${NC}"
echo -e "${BLUE}🌐 Удаленный сервер: $SERVER_USER@$SERVER_HOST:$SERVER_PATH${NC}"
echo -e "${YELLOW}💡 Для остановки нажмите Ctrl+C${NC}"
echo ""

# Функция полной синхронизации (при первом запуске)
full_sync() {
    echo -e "${YELLOW}📦 Первоначальная синхронизация...${NC}"
    
    EXCLUDE_FILE=$(mktemp)
    cat > "$EXCLUDE_FILE" << EOF
.bak.*
*.bak.*
.git/
.gitignore
.env
*.db
*.sqlite
*.sqlite3
*.log
*.pid
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.DS_Store
deploy.conf
*.example
EOF
    
    rsync -avz --delete \
        --exclude-from="$EXCLUDE_FILE" \
        -e "ssh ${SSH_OPTS}" \
        ./ "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/" 2>/dev/null
    
    rm -f "$EXCLUDE_FILE"
    echo -e "${GREEN}✅ Первоначальная синхронизация завершена${NC}"
    echo -e "${BLUE}👀 Ожидание изменений файлов...${NC}"
    echo ""
}

# Запускаем первоначальную синхронизацию
full_sync

# Функция синхронизации
do_sync() {
    EXCLUDE_FILE=$(mktemp)
    cat > "$EXCLUDE_FILE" << EOF
.bak.*
*.bak.*
.git/
.gitignore
.env
*.db
*.sqlite
*.sqlite3
*.log
*.pid
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.DS_Store
deploy.conf
*.example
EOF
    
    rsync -avz --delete \
        --exclude-from="$EXCLUDE_FILE" \
        -e "ssh ${SSH_OPTS}" \
        ./ "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/" 2>/dev/null && \
        echo -e "${GREEN}✓${NC} $(date +%H:%M:%S) Синхронизировано" || \
        echo -e "${YELLOW}⚠${NC} $(date +%H:%M:%S) Ошибка синхронизации"
    
    rm -f "$EXCLUDE_FILE"
}

# Запускаем мониторинг изменений
# Используем debounce чтобы не синхронизировать слишком часто
LAST_SYNC=0
SYNC_DELAY=2  # Минимальная задержка между синхронизациями (секунды)

fswatch -o . | while read f; do
    CURRENT_TIME=$(date +%s)
    if [ $((CURRENT_TIME - LAST_SYNC)) -ge $SYNC_DELAY ]; then
        do_sync
        LAST_SYNC=$CURRENT_TIME
    fi
done
