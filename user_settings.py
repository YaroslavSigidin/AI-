"""
Модуль для управления настройками и предпочтениями пользователей
Контекстная память бота
"""
import os
import json
import sqlite3
import time
from typing import Optional, Dict, Any
from pathlib import Path

DB_PATH = os.getenv("USER_SETTINGS_DB", "user_settings.db")

def _connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        preferences TEXT,  -- JSON с предпочтениями
        goals TEXT,        -- JSON с целями
        stats TEXT,        -- JSON со статистикой использования
        updated_at INTEGER NOT NULL DEFAULT 0
    )
    """)
    con.commit()
    return con

def _now() -> int:
    return int(time.time())

def _default_preferences() -> Dict[str, Any]:
    """Возвращает предпочтения по умолчанию"""
    return {
        "favorite_exercises": [],      # Предпочитаемые упражнения
        "preferred_style": "friendly",  # Стиль общения: friendly, professional, casual
        "voice_preferred": True,        # Предпочитает голосовой ввод
        "reminders_enabled": True,      # Включены ли напоминания
        "timezone": "MSK",              # Часовой пояс
    }

def _default_goals() -> Dict[str, Any]:
    """Возвращает цели по умолчанию"""
    return {
        "target_weight": None,          # Целевой вес (кг)
        "target_calories": None,        # Целевое количество калорий в день
        "workouts_per_week": None,      # Количество тренировок в неделю
        "workout_days": [],             # Дни недели для тренировок (0-6, где 0=понедельник)
        "primary_goal": None,           # Основная цель: weight_loss, muscle_gain, maintenance, endurance
    }

def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Получает все настройки пользователя"""
    con = _connect()
    try:
        row = con.execute(
            "SELECT preferences, goals, stats, updated_at FROM user_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()
        
        if not row:
            # Создаем настройки по умолчанию
            prefs = _default_preferences()
            goals = _default_goals()
            stats = {}
            updated_at = _now()
            con.execute(
                "INSERT INTO user_settings(user_id, preferences, goals, stats, updated_at) VALUES(?,?,?,?,?)",
                (user_id, json.dumps(prefs), json.dumps(goals), json.dumps(stats), updated_at)
            )
            con.commit()
            return {
                "preferences": prefs,
                "goals": goals,
                "stats": stats,
                "updated_at": updated_at
            }
        
        return {
            "preferences": json.loads(row[0] or "{}"),
            "goals": json.loads(row[1] or "{}"),
            "stats": json.loads(row[2] or "{}"),
            "updated_at": int(row[3] or 0)
        }
    finally:
        con.close()

def update_preferences(user_id: int, prefs: Dict[str, Any]) -> None:
    """Обновляет предпочтения пользователя (сливает с существующими)"""
    current = get_user_settings(user_id)
    updated_prefs = {**current["preferences"], **prefs}
    
    con = _connect()
    try:
        con.execute(
            "UPDATE user_settings SET preferences=?, updated_at=? WHERE user_id=?",
            (json.dumps(updated_prefs), _now(), user_id)
        )
        con.commit()
    finally:
        con.close()

def update_goals(user_id: int, goals: Dict[str, Any]) -> None:
    """Обновляет цели пользователя (сливает с существующими)"""
    current = get_user_settings(user_id)
    updated_goals = {**current["goals"], **goals}
    
    con = _connect()
    try:
        con.execute(
            "UPDATE user_settings SET goals=?, updated_at=? WHERE user_id=?",
            (json.dumps(updated_goals), _now(), user_id)
        )
        con.commit()
    finally:
        con.close()

def update_stats(user_id: int, stats_updates: Dict[str, Any]) -> None:
    """Обновляет статистику пользователя (сливает с существующими)"""
    current = get_user_settings(user_id)
    updated_stats = {**current["stats"], **stats_updates}
    
    con = _connect()
    try:
        con.execute(
            "UPDATE user_settings SET stats=?, updated_at=? WHERE user_id=?",
            (json.dumps(updated_stats), _now(), user_id)
        )
        con.commit()
    finally:
        con.close()

def get_preferences(user_id: int) -> Dict[str, Any]:
    """Получает предпочтения пользователя"""
    settings = get_user_settings(user_id)
    prefs = settings["preferences"]
    # Убеждаемся, что все ключи присутствуют
    default = _default_preferences()
    return {**default, **prefs}

def get_goals(user_id: int) -> Dict[str, Any]:
    """Получает цели пользователя"""
    settings = get_user_settings(user_id)
    goals = settings["goals"]
    # Убеждаемся, что все ключи присутствуют
    default = _default_goals()
    return {**default, **goals}

def track_activity(user_id: int, activity_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Отслеживает активность пользователя для улучшения контекстной памяти"""
    metadata = metadata or {}
    stats_updates = {
        "last_activity": _now(),
        "last_activity_type": activity_type,
        f"{activity_type}_count": (get_user_settings(user_id)["stats"].get(f"{activity_type}_count", 0) + 1),
        **metadata
    }
    update_stats(user_id, stats_updates)

def get_context_summary(user_id: int) -> str:
    """Возвращает краткое резюме контекста пользователя для ИИ"""
    prefs = get_preferences(user_id)
    goals = get_goals(user_id)
    stats = get_user_settings(user_id)["stats"]
    
    parts = []
    
    # Предпочтения
    if prefs.get("favorite_exercises"):
        parts.append(f"Любимые упражнения: {', '.join(prefs['favorite_exercises'])}")
    
    if prefs.get("preferred_style") != "friendly":
        parts.append(f"Стиль общения: {prefs['preferred_style']}")
    
    # Цели
    if goals.get("primary_goal"):
        goal_names = {
            "weight_loss": "похудение",
            "muscle_gain": "набор массы",
            "maintenance": "поддержание формы",
            "endurance": "выносливость"
        }
        parts.append(f"Основная цель: {goal_names.get(goals['primary_goal'], goals['primary_goal'])}")
    
    if goals.get("target_weight"):
        parts.append(f"Целевой вес: {goals['target_weight']} кг")
    
    if goals.get("workouts_per_week"):
        parts.append(f"Планируемые тренировки: {goals['workouts_per_week']} раз в неделю")
    
    # Статистика
    total_activities = sum(v for k, v in stats.items() if k.endswith("_count") and isinstance(v, int))
    if total_activities > 0:
        parts.append(f"Всего записей: {total_activities}")
    
    if parts:
        return " | ".join(parts)
    return "Новый пользователь"
