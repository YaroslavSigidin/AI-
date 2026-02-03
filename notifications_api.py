"""
API endpoint для настроек уведомлений - используется в Web App
"""
import os
from fastapi import APIRouter, Header, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

# Импортируем notifications модуль
# Если модуль не найден, используем fallback
try:
    from notifications import (
        get_frequency, set_frequency, get_settings,
        FREQUENCY_3_PER_DAY, FREQUENCY_1_PER_DAY, FREQUENCY_1_PER_WEEK, FREQUENCY_DISABLED,
        FREQUENCY_OPTIONS
    )
except ImportError:
    # Fallback для случая, если модуль не установлен
    import sys
    import os
    # Добавляем путь к модулю
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from notifications import (
            get_frequency, set_frequency, get_settings,
            FREQUENCY_3_PER_DAY, FREQUENCY_1_PER_DAY, FREQUENCY_1_PER_WEEK, FREQUENCY_DISABLED,
            FREQUENCY_OPTIONS
        )
    except ImportError:
        # Если все еще не работает, создаем заглушки
        def get_frequency(user_id: int) -> str:
            return "1_per_day"
        def set_frequency(user_id: int, frequency: str) -> bool:
            return True
        def get_settings(user_id: int):
            return {
                "frequency": "1_per_day",
                "frequency_label": "1 раз в день",
                "is_enabled": True
            }
        FREQUENCY_3_PER_DAY = "3_per_day"
        FREQUENCY_1_PER_DAY = "1_per_day"
        FREQUENCY_1_PER_WEEK = "1_per_week"
        FREQUENCY_DISABLED = "disabled"
        FREQUENCY_OPTIONS = {
            FREQUENCY_3_PER_DAY: "3 раза в день",
            FREQUENCY_1_PER_DAY: "1 раз в день",
            FREQUENCY_1_PER_WEEK: "1 раз в неделю",
            FREQUENCY_DISABLED: "Отключено"
        }

router = APIRouter()

def _need_user(x_user_id: str | None):
    uid = (x_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="Missing X-User-Id header")
    try:
        return int(uid)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid X-User-Id")

class NotificationSettingsRequest(BaseModel):
    frequency: str

@router.get("/api/notifications/settings")
async def get_notification_settings(x_user_id: str = Header(None, alias="X-User-Id")):
    """Получает настройки уведомлений пользователя"""
    user_id = _need_user(x_user_id)
    settings = get_settings(user_id)
    return {
        "frequency": settings["frequency"],
        "frequency_label": settings["frequency_label"],
        "is_enabled": settings["is_enabled"],
        "options": [
            {"value": FREQUENCY_3_PER_DAY, "label": FREQUENCY_OPTIONS[FREQUENCY_3_PER_DAY]},
            {"value": FREQUENCY_1_PER_DAY, "label": FREQUENCY_OPTIONS[FREQUENCY_1_PER_DAY]},
            {"value": FREQUENCY_1_PER_WEEK, "label": FREQUENCY_OPTIONS[FREQUENCY_1_PER_WEEK]},
            {"value": FREQUENCY_DISABLED, "label": FREQUENCY_OPTIONS[FREQUENCY_DISABLED]},
        ]
    }

@router.post("/api/notifications/settings")
async def update_notification_settings(
    request: NotificationSettingsRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    """Обновляет настройки уведомлений пользователя"""
    user_id = _need_user(x_user_id)
    success = set_frequency(user_id, request.frequency)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid frequency value")
    
    settings = get_settings(user_id)
    return {
        "frequency": settings["frequency"],
        "frequency_label": settings["frequency_label"],
        "is_enabled": settings["is_enabled"]
    }
