#!/bin/bash
# Скрипт автоматического развертывания на TimeWeb

set -e  # Остановка при ошибке

# Загружаем конфигурацию
if [ -f deploy.conf ]; then
    source deploy.conf
else
    echo "❌ Файл deploy.conf не найден!"
    echo "Скопируйте deploy.conf.example в deploy.conf и заполните параметры"
    exit 1
fi

# Проверяем обязательные параметры
if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ] || [ -z "$SERVER_PATH" ]; then
    echo "❌ Ошибка: не заданы параметры SERVER_HOST, SERVER_USER или SERVER_PATH в deploy.conf"
    exit 1
fi

echo "🚀 Начинаю деплой на $SERVER_USER@$SERVER_HOST:$SERVER_PATH"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Создаем список файлов для исключения
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
deploy.sh
*.example
EOF

# Функция для выполнения команд на сервере
run_remote() {
    ssh ${SSH_OPTS} "$SERVER_USER@$SERVER_HOST" "$@"
}

# Синхронизируем файлы
echo -e "${YELLOW}📦 Синхронизация файлов...${NC}"
rsync -avz --delete \
    --exclude-from="$EXCLUDE_FILE" \
    -e "ssh ${SSH_OPTS}" \
    ./ "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo -e "${GREEN}✅ Файлы синхронизированы${NC}"

# Копируем файлы веб-приложения в директорию Caddy
echo -e "${YELLOW}🌐 Копирование файлов веб-приложения...${NC}"
run_remote "cp $SERVER_PATH/tracker.html /root/tg-miniapp/web/tracker.html && cp $SERVER_PATH/tracker.css /root/tg-miniapp/web/tracker.css && cp $SERVER_PATH/tracker.js /root/tg-miniapp/web/tracker.js && cp $SERVER_PATH/referrals_dashboard.html /root/tg-miniapp/web/referrals_dashboard.html && cp $SERVER_PATH/referrals_dashboard.css /root/tg-miniapp/web/referrals_dashboard.css && cp $SERVER_PATH/referrals_dashboard.js /root/tg-miniapp/web/referrals_dashboard.js && cp $SERVER_PATH/trainer_dashboard.html /root/tg-miniapp/web/trainer_dashboard.html && cp $SERVER_PATH/trainer_dashboard.css /root/tg-miniapp/web/trainer_dashboard.css && cp $SERVER_PATH/trainer_dashboard.js /root/tg-miniapp/web/trainer_dashboard.js && cp $SERVER_PATH/privacy_policy.html /root/tg-miniapp/web/privacy_policy.html && cp $SERVER_PATH/terms.html /root/tg-miniapp/web/terms.html && cp $SERVER_PATH/offer.html /root/tg-miniapp/web/offer.html && cp $SERVER_PATH/consent.html /root/tg-miniapp/web/consent.html && cp $SERVER_PATH/legal.css /root/tg-miniapp/web/legal.css" || echo -e "${YELLOW}⚠️  Не удалось скопировать файлы в /root/tg-miniapp/web/ (возможно, директория не существует)${NC}"
echo -e "${GREEN}✅ Файлы веб-приложения обновлены${NC}"

# Перезапускаем Caddy для применения изменений
echo -e "${YELLOW}🔄 Перезапуск Caddy...${NC}"
run_remote "docker restart tg-miniapp-caddy-1" || echo -e "${YELLOW}⚠️  Не удалось перезапустить Caddy${NC}"
echo -e "${GREEN}✅ Caddy перезапущен${NC}"

# Устанавливаем зависимости на сервере (если нужно и НЕ Docker)
# В Docker зависимости устанавливаются при сборке образа
if [ "$INSTALL_DEPS" = "true" ] && ! echo "$RESTART_COMMAND" | grep -q "docker"; then
    echo -e "${YELLOW}📥 Установка зависимостей...${NC}"
    run_remote "cd $SERVER_PATH && pip install --quiet --no-cache-dir -r requirements.txt"
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
fi

# Перезапускаем бота
if [ "$RESTART_COMMAND" ]; then
    echo -e "${YELLOW}🔄 Перезапуск бота...${NC}"
    run_remote "$RESTART_COMMAND"
    echo -e "${GREEN}✅ Бот перезапущен${NC}"
else
    echo -e "${YELLOW}⚠️  Команда перезапуска не задана. Запустите вручную.${NC}"
fi

# Очистка временных файлов
rm -f "$EXCLUDE_FILE"

echo -e "${GREEN}🎉 Деплой завершен успешно!${NC}"
