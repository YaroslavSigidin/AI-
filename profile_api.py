"""
API endpoints для профиля пользователя
"""
from fastapi import APIRouter, Header, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

try:
    from app.profile_store import get_profile, upsert_profile
except ImportError:
    try:
        from profile_store import get_profile, upsert_profile
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from profile_store import get_profile, upsert_profile

router = APIRouter()

def _need_user(x_user_id: str | None):
    uid = (x_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="Missing X-User-Id header")
    try:
        return int(uid)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid X-User-Id")

class ProfileUpdateRequest(BaseModel):
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    experience: Optional[str] = None
    injuries: Optional[str] = None
    equipment: Optional[str] = None

@router.get("/api/profile")
async def get_user_profile(x_user_id: str = Header(None, alias="X-User-Id")):
    """Получает профиль пользователя"""
    user_id = _need_user(x_user_id)
    profile = get_profile(user_id)
    return profile

@router.post("/api/profile")
async def update_user_profile(
    request: ProfileUpdateRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    """Обновляет профиль пользователя"""
    user_id = _need_user(x_user_id)
    
    profile_data = request.dict(exclude_unset=True)
    if not profile_data:
        return {"message": "No data to update"}
    
    upsert_profile(user_id, profile_data)
    return get_profile(user_id)
