#!/bin/bash

# Скрипт для запуска локального прототипа приложения

# Не используем set -e, так как проверка портов может вернуть ненулевой код

echo "🚀 Запуск локального прототипа приложения..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден. Установите Python 3.8 или выше.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✅ Python версия: $(python3 --version)${NC}"

# Проверяем зависимости
echo -e "${YELLOW}📦 Проверка зависимостей...${NC}"
if [ ! -f "requirements_local.txt" ]; then
    echo -e "${RED}❌ Файл requirements_local.txt не найден${NC}"
    exit 1
fi

# Устанавливаем зависимости если нужно
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}📥 Установка зависимостей...${NC}"
    pip3 install -r requirements_local.txt
else
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
fi

# Создаем директорию для данных
LOCAL_DATA_DIR="./local_data"
mkdir -p "$LOCAL_DATA_DIR"
echo -e "${GREEN}✅ Директория для данных: $LOCAL_DATA_DIR${NC}"

# Загружаем переменные окружения из .env.local если есть
if [ -f ".env.local" ]; then
    echo -e "${GREEN}✅ Загружены переменные из .env.local${NC}"
    export $(cat .env.local | grep -v '^#' | xargs)
fi

# Устанавливаем переменные окружения по умолчанию если не установлены
export TRACKER_DB_PATH="${TRACKER_DB_PATH:-$LOCAL_DATA_DIR/tracker.db}"
export WORKOUT_STATE_DB="${WORKOUT_STATE_DB:-$LOCAL_DATA_DIR/workout_state.db}"
export USER_SETTINGS_DB="${USER_SETTINGS_DB:-$LOCAL_DATA_DIR/user_settings.db}"

echo -e "${GREEN}📊 Настройки баз данных:${NC}"
echo "   TRACKER_DB_PATH: $TRACKER_DB_PATH"
echo "   WORKOUT_STATE_DB: $WORKOUT_STATE_DB"
echo "   USER_SETTINGS_DB: $USER_SETTINGS_DB"

# Функция для очистки при выходе
cleanup() {
    echo -e "\n${YELLOW}🛑 Остановка серверов...${NC}"
    kill $FASTAPI_PID 2>/dev/null || true
    if [ -n "$HTTP_PID" ]; then
        kill $HTTP_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Проверяем доступность портов
check_port() {
    local port=$1
    # Проверяем через lsof (macOS/Linux)
    if command -v lsof &> /dev/null; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            return 1  # Порт занят
        else
            return 0  # Порт свободен
        fi
    # Альтернативная проверка через netstat (если lsof недоступен)
    elif command -v netstat &> /dev/null; then
        if netstat -an 2>/dev/null | grep -q ":$port.*LISTEN"; then
            return 1  # Порт занят
        else
            return 0  # Порт свободен
        fi
    # Если ни lsof, ни netstat не доступны, пробуем подключиться
    else
        if python3 -c "import socket; s=socket.socket(); s.settimeout(0.1); result=s.connect_ex(('localhost', $port)); s.close(); exit(0 if result != 0 else 1)" 2>/dev/null; then
            return 0  # Порт свободен
        else
            return 1  # Порт занят
        fi
    fi
}

# Проверяем порт 8000 для FastAPI
FASTAPI_PORT=8000
if ! check_port $FASTAPI_PORT; then
    echo -e "${YELLOW}⚠️  Порт $FASTAPI_PORT занят, пробуем 8001...${NC}"
    FASTAPI_PORT=8001
    if ! check_port $FASTAPI_PORT; then
        echo -e "${RED}❌ Порты 8000 и 8001 заняты. Освободите один из них или измените порт в скрипте.${NC}"
        exit 1
    fi
fi

# Проверяем порт 8080 для HTTP сервера
HTTP_PORT=8080
if ! check_port $HTTP_PORT; then
    echo -e "${YELLOW}⚠️  Порт $HTTP_PORT занят, пробуем 8081...${NC}"
    HTTP_PORT=8081
    if ! check_port $HTTP_PORT; then
        echo -e "${RED}❌ Порты 8080 и 8081 заняты. Освободите один из них или измените порт в скрипте.${NC}"
        exit 1
    fi
fi

# Запускаем FastAPI сервер в фоне с указанным портом
echo -e "${YELLOW}🌐 Запуск FastAPI сервера на порту $FASTAPI_PORT...${NC}"
uvicorn local_server:app --host 0.0.0.0 --port $FASTAPI_PORT > /tmp/fastapi_local.log 2>&1 &
FASTAPI_PID=$!
sleep 3

# Проверяем что FastAPI запустился
if ! kill -0 $FASTAPI_PID 2>/dev/null; then
    echo -e "${RED}❌ Не удалось запустить FastAPI сервер${NC}"
    echo -e "${YELLOW}📋 Логи:${NC}"
    tail -20 /tmp/fastapi_local.log
    exit 1
fi

# Проверяем что сервер отвечает
if ! curl -s http://localhost:$FASTAPI_PORT/api/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Сервер запущен, но не отвечает на health check. Проверьте логи.${NC}"
else
    echo -e "${GREEN}✅ FastAPI сервер запущен (PID: $FASTAPI_PID, порт: $FASTAPI_PORT)${NC}"
fi

# FastAPI уже отдает статику, поэтому HTTP сервер не нужен
# Но оставляем возможность запустить его отдельно если нужно
USE_SEPARATE_HTTP=${USE_SEPARATE_HTTP:-false}

if [ "$USE_SEPARATE_HTTP" = "true" ]; then
    # Запускаем HTTP сервер для статики в фоне с указанным портом
    echo -e "${YELLOW}📁 Запуск HTTP сервера для статики на порту $HTTP_PORT...${NC}"
    cd "$(dirname "$0")"
    python3 -m http.server $HTTP_PORT > /tmp/http_local.log 2>&1 &
    HTTP_PID=$!
    sleep 2

    # Проверяем что HTTP сервер запустился
    if ! kill -0 $HTTP_PID 2>/dev/null; then
        echo -e "${RED}❌ Не удалось запустить HTTP сервер${NC}"
        echo -e "${YELLOW}📋 Логи:${NC}"
        tail -10 /tmp/http_local.log
        kill $FASTAPI_PID 2>/dev/null || true
        exit 1
    fi

    echo -e "${GREEN}✅ HTTP сервер запущен (PID: $HTTP_PID, порт: $HTTP_PORT)${NC}"
    APP_URL="http://localhost:$HTTP_PORT/tracker.html"
else
    # Используем FastAPI для всего (статики + API)
    HTTP_PID=""
    APP_URL="http://localhost:$FASTAPI_PORT/tracker.html"
    echo -e "${GREEN}✅ Используем FastAPI для статики и API (один порт: $FASTAPI_PORT)${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Локальный прототип запущен!${NC}"
echo ""
echo -e "${GREEN}📱 Приложение:${NC}   $APP_URL"
echo -e "${GREEN}🌐 API:${NC}          http://localhost:$FASTAPI_PORT/api/"
echo -e "${GREEN}📊 Health check:${NC} http://localhost:$FASTAPI_PORT/api/health"
echo ""
echo -e "${YELLOW}💡 Для остановки нажмите Ctrl+C${NC}"
echo -e "${YELLOW}📋 Логи FastAPI:${NC} tail -f /tmp/fastapi_local.log"
if [ "$USE_SEPARATE_HTTP" = "true" ]; then
    echo -e "${YELLOW}📋 Логи HTTP:${NC}    tail -f /tmp/http_local.log"
fi
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""

# Ждем завершения
wait
