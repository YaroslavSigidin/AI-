"""
API endpoints для настроек напоминаний
"""
from fastapi import APIRouter, Header, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

try:
    from app.user_settings import get_preferences, update_preferences
except ImportError:
    try:
        from user_settings import get_preferences, update_preferences
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from user_settings import get_preferences, update_preferences

router = APIRouter()

def _need_user(x_user_id: str | None):
    uid = (x_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="Missing X-User-Id header")
    try:
        return int(uid)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid X-User-Id")

class RemindersSettingsRequest(BaseModel):
    enabled: bool

@router.get("/api/reminders/settings")
async def get_reminders_settings(x_user_id: str = Header(None, alias="X-User-Id")):
    """Получает настройки напоминаний пользователя"""
    user_id = _need_user(x_user_id)
    prefs = get_preferences(user_id)
    return {
        "enabled": prefs.get("reminders_enabled", True)
    }

@router.post("/api/reminders/settings")
async def update_reminders_settings(
    request: RemindersSettingsRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    """Обновляет настройки напоминаний пользователя"""
    user_id = _need_user(x_user_id)
    
    prefs = get_preferences(user_id)
    prefs["reminders_enabled"] = request.enabled
    update_preferences(user_id, prefs)
    
    return {
        "enabled": request.enabled
    }
