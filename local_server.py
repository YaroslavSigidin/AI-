"""
Локальный сервер для тестирования приложения
Запускает FastAPI с всеми API роутерами без Telegram бота и оплат
"""
import os
import sys
from pathlib import Path

# Настраиваем переменные окружения для локальной работы
os.environ.setdefault("TRACKER_DB_PATH", str(Path(__file__).parent / "local_data" / "tracker.db"))
os.environ.setdefault("WORKOUT_STATE_DB", str(Path(__file__).parent / "local_data" / "workout_state.db"))
os.environ.setdefault("USER_SETTINGS_DB", str(Path(__file__).parent / "local_data" / "user_settings.db"))

# Создаем директорию для данных если её нет
local_data_dir = Path(__file__).parent / "local_data"
local_data_dir.mkdir(exist_ok=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Импортируем все роутеры
try:
    from profile_api import router as profile_router
except ImportError:
    print("⚠️ Не удалось импортировать profile_api")
    profile_router = None

try:
    from workout_plan_api import router as workout_plan_router
except ImportError:
    print("⚠️ Не удалось импортировать workout_plan_api")
    workout_plan_router = None

try:
    from stats_api import router as stats_router
except ImportError:
    print("⚠️ Не удалось импортировать stats_api")
    stats_router = None

try:
    from notifications_api import router as notifications_router
except ImportError:
    print("⚠️ Не удалось импортировать notifications_api")
    notifications_router = None

try:
    from reminders_api import router as reminders_router
except ImportError:
    print("⚠️ Не удалось импортировать reminders_api")
    reminders_router = None

try:
    from goals_api import router as goals_router
except ImportError:
    print("⚠️ Не удалось импортировать goals_api")
    goals_router = None

# Создаем FastAPI приложение
app = FastAPI(
    title="Fitness Tracker Local API",
    description="Локальный API для тестирования приложения",
    version="1.0.0"
)

# Настраиваем CORS для локальной разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене нужно ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
if profile_router:
    app.include_router(profile_router)
    print("✅ Подключен profile_api")

if workout_plan_router:
    app.include_router(workout_plan_router)
    print("✅ Подключен workout_plan_api")

if stats_router:
    app.include_router(stats_router)
    print("✅ Подключен stats_api")

if notifications_router:
    app.include_router(notifications_router)
    print("✅ Подключен notifications_api")

if reminders_router:
    app.include_router(reminders_router)
    print("✅ Подключен reminders_api")

if goals_router:
    app.include_router(goals_router)
    print("✅ Подключен goals_api")

# Статические файлы - отдаем через FastAPI
static_dir = Path(__file__).parent

@app.get("/")
async def root():
    """Главная страница - редирект на tracker.html"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/tracker.html")

@app.get("/tracker.html")
async def tracker_html():
    """HTML приложения"""
    html_file = static_dir / "tracker.html"
    if html_file.exists():
        return FileResponse(html_file, media_type="text/html")
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="tracker.html not found")

@app.get("/tracker.js")
async def tracker_js():
    """JavaScript приложения"""
    js_file = static_dir / "tracker.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="tracker.js not found")

@app.get("/tracker.css")
async def tracker_css():
    """CSS стили приложения"""
    css_file = static_dir / "tracker.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="tracker.css not found")

print("✅ Статические файлы доступны через FastAPI")

@app.get("/api/health")
async def health():
    """Проверка работоспособности API"""
    return {
        "status": "ok",
        "message": "Локальный сервер работает",
        "databases": {
            "tracker": os.environ.get("TRACKER_DB_PATH", "не установлен"),
            "workout_state": os.environ.get("WORKOUT_STATE_DB", "не установлен"),
            "user_settings": os.environ.get("USER_SETTINGS_DB", "не установлен")
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Запуск локального сервера...")
    print(f"📁 Базы данных: {local_data_dir}")
    print("🌐 API доступен на: http://localhost:8000")
    print("📊 Health check: http://localhost:8000/api/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
