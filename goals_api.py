"""
API endpoints для целей пользователя (weekly workout goals)
"""
from fastapi import APIRouter, Header, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

try:
    from app.user_settings import get_goals, update_goals
except ImportError:
    try:
        from user_settings import get_goals, update_goals
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from user_settings import get_goals, update_goals

router = APIRouter()

def _need_user(x_user_id: str | None):
    uid = (x_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="Missing X-User-Id header")
    try:
        return int(uid)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid X-User-Id")

class GoalsUpdateRequest(BaseModel):
    weekly_workouts: Optional[int] = None

@router.get("/api/goals")
async def get_user_goals(x_user_id: str = Header(None, alias="X-User-Id")):
    """Получает цели пользователя"""
    user_id = _need_user(x_user_id)
    try:
        goals = get_goals(user_id)
        return goals
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get goals: {str(e)}")

@router.post("/api/goals")
async def update_user_goals(
    request: GoalsUpdateRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    """Обновляет цели пользователя"""
    user_id = _need_user(x_user_id)
    try:
        goals_dict = {}
        if request.weekly_workouts is not None:
            goals_dict["weekly_workouts"] = request.weekly_workouts
        
        if goals_dict:
            update_goals(user_id, goals_dict)
        
        return get_goals(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update goals: {str(e)}")
