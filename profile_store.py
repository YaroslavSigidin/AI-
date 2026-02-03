"""
Хранение профиля пользователя (онбординг) для генерации планов.
Безопасно: если профиля нет — генерация работает как раньше.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, Optional

DB_PATH = (os.getenv("TRACKER_DB_PATH") or "/data/tracker.db").strip()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profile (
          user_id TEXT PRIMARY KEY,
          height_cm INTEGER,
          weight_kg REAL,
          age INTEGER,
          sex TEXT,
          goal TEXT,
          experience TEXT,
          injuries TEXT,
          equipment TEXT,
          schedule TEXT,
          updated_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def get_profile(user_id: int) -> Dict[str, Any]:
    uid = str(user_id)
    conn = _db()
    try:
        row = conn.execute(
            "SELECT height_cm, weight_kg, age, sex, goal, experience, injuries, equipment, schedule, updated_at "
            "FROM user_profile WHERE user_id=?",
            (uid,),
        ).fetchone()
        if not row:
            return {}
        keys = [
            "height_cm",
            "weight_kg",
            "age",
            "sex",
            "goal",
            "experience",
            "injuries",
            "equipment",
            "schedule",
            "updated_at",
        ]
        return {k: row[i] for i, k in enumerate(keys) if row[i] is not None}
    finally:
        conn.close()


def upsert_profile(user_id: int, data: Dict[str, Any]) -> None:
    """
    Частичное обновление профиля.
    data может содержать любые поля из таблицы user_profile (кроме user_id).
    """
    allowed = {
        "height_cm",
        "weight_kg",
        "age",
        "sex",
        "goal",
        "experience",
        "injuries",
        "equipment",
        "schedule",
        "updated_at",
    }
    clean: Dict[str, Any] = {k: v for k, v in (data or {}).items() if k in allowed}
    if not clean:
        return

    uid = str(user_id)
    conn = _db()
    try:
        # SQLite UPSERT
        cols = ["user_id"] + list(clean.keys())
        placeholders = ",".join(["?"] * len(cols))
        updates = ",".join([f"{k}=excluded.{k}" for k in clean.keys()])
        values = [uid] + [clean[k] for k in clean.keys()]
        conn.execute(
            f"INSERT INTO user_profile ({','.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(user_id) DO UPDATE SET {updates}",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def profile_to_prompt(profile: Dict[str, Any]) -> str:
    """
    Сжатое представление профиля для промпта.
    """
    if not profile:
        return ""
    parts = []
    if profile.get("age"):
        parts.append(f"Возраст: {profile['age']}")
    if profile.get("sex"):
        parts.append(f"Пол: {profile['sex']}")
    if profile.get("height_cm"):
        parts.append(f"Рост: {profile['height_cm']} см")
    if profile.get("weight_kg"):
        parts.append(f"Вес: {profile['weight_kg']} кг")
    if profile.get("goal"):
        parts.append(f"Цель: {profile['goal']}")
    if profile.get("experience"):
        parts.append(f"Опыт: {profile['experience']}")
    if profile.get("injuries"):
        parts.append(f"Травмы/ограничения: {profile['injuries']}")
    if profile.get("equipment"):
        parts.append(f"Оборудование: {profile['equipment']}")
    if profile.get("schedule"):
        parts.append(f"График: {profile['schedule']}")
    return "\n".join(parts).strip()

