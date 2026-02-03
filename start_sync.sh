#!/bin/bash
# Упрощенный скрипт запуска автоматической синхронизации

# Определяем, какой способ использовать
if command -v fswatch &> /dev/null; then
    echo "✅ Используется fswatch (быстрый вариант)"
    exec ./sync_watch.sh
elif python3 -c "import watchdog" 2>/dev/null; then
    echo "✅ Используется Python watchdog (альтернативный вариант)"
    exec python3 sync_watch.py
else
    echo "❌ Не найдены инструменты для автоматической синхронизации"
    echo ""
    echo "Установите один из вариантов:"
    echo "  1. fswatch (рекомендуется для macOS):"
    echo "     brew install fswatch"
    echo ""
    echo "  2. Python watchdog:"
    echo "     pip install watchdog"
    exit 1
fi
