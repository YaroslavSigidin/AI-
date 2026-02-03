"""
Модуль для управления умными напоминаниями
"""
import os
import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

DB_PATH = os.getenv("REMINDERS_DB", "reminders.db")

def _connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        reminder_type TEXT NOT NULL,  -- workout, meal, water, custom
        message TEXT NOT NULL,
        time_hour INTEGER NOT NULL,   -- час дня (0-23)
        time_minute INTEGER NOT NULL DEFAULT 0,  -- минута (0-59)
        days_of_week TEXT,            -- JSON массив дней недели [0,1,2,3,4,5,6] (0=понедельник)
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL,
        last_sent INTEGER DEFAULT 0,
        next_send INTEGER NOT NULL
    )
    """)
    con.execute("""
    CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id)
    """)
    con.execute("""
    CREATE INDEX IF NOT EXISTS idx_reminders_next_send ON reminders(next_send)
    """)
    con.commit()
    return con

def _now() -> int:
    return int(time.time())

def _next_send_timestamp(time_hour: int, time_minute: int, days_of_week: Optional[List[int]]) -> int:
    """Вычисляет следующий timestamp для отправки напоминания"""
    now = datetime.now()
    target_time = now.replace(hour=time_hour, minute=time_minute, second=0, microsecond=0)
    
    if days_of_week is None:
        # Ежедневное напоминание
        if target_time <= now:
            target_time += timedelta(days=1)
        return int(target_time.timestamp())
    
    # Напоминание в определенные дни недели
    current_weekday = now.weekday()  # 0=понедельник, 6=воскресенье
    
    # Проверяем сегодня
    if current_weekday in days_of_week and target_time > now:
        return int(target_time.timestamp())
    
    # Ищем следующий день
    days_ahead = 1
    while days_ahead <= 7:
        next_day = (current_weekday + days_ahead) % 7
        if next_day in days_of_week:
            next_date = now + timedelta(days=days_ahead)
            next_target = next_date.replace(hour=time_hour, minute=time_minute, second=0, microsecond=0)
            return int(next_target.timestamp())
        days_ahead += 1
    
    # Если не нашли, берем следующий день из списка
    next_day = min(days_of_week)
    days_ahead = (next_day - current_weekday + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_date = now + timedelta(days=days_ahead)
    next_target = next_date.replace(hour=time_hour, minute=time_minute, second=0, microsecond=0)
    return int(next_target.timestamp())

def create_reminder(
    user_id: int,
    reminder_type: str,
    message: str,
    time_hour: int,
    time_minute: int = 0,
    days_of_week: Optional[List[int]] = None
) -> int:
    """Создает новое напоминание и возвращает его ID"""
    next_send = _next_send_timestamp(time_hour, time_minute, days_of_week)
    
    con = _connect()
    try:
        days_json = None if days_of_week is None else json.dumps(days_of_week)
        cursor = con.execute("""
            INSERT INTO reminders(user_id, reminder_type, message, time_hour, time_minute, days_of_week, is_active, created_at, next_send)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (user_id, reminder_type, message, time_hour, time_minute, days_json, 1, _now(), next_send))
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()

def get_user_reminders(user_id: int, active_only: bool = True) -> List[Dict]:
    """Получает все напоминания пользователя"""
    con = _connect()
    try:
        query = "SELECT reminder_id, reminder_type, message, time_hour, time_minute, days_of_week, is_active, next_send FROM reminders WHERE user_id=?"
        params = [user_id]
        
        if active_only:
            query += " AND is_active=1"
        
        query += " ORDER BY time_hour, time_minute"
        
        rows = con.execute(query, params).fetchall()
        return [
            {
                "reminder_id": row[0],
                "reminder_type": row[1],
                "message": row[2],
                "time_hour": row[3],
                "time_minute": row[4],
                "days_of_week": json.loads(row[5]) if row[5] else None,
                "is_active": bool(row[6]),
                "next_send": row[7]
            }
            for row in rows
        ]
    finally:
        con.close()

def get_due_reminders(now_ts: Optional[int] = None) -> List[Dict]:
    """Получает напоминания, которые нужно отправить сейчас"""
    now_ts = now_ts or _now()
    con = _connect()
    try:
        rows = con.execute("""
            SELECT reminder_id, user_id, reminder_type, message
            FROM reminders
            WHERE is_active=1 AND next_send <= ?
        """, (now_ts,)).fetchall()
        
        reminders = [
            {
                "reminder_id": row[0],
                "user_id": row[1],
                "reminder_type": row[2],
                "message": row[3]
            }
            for row in rows
        ]
        
        # Обновляем next_send для отправленных напоминаний
        for reminder in reminders:
            # Получаем параметры напоминания
            row = con.execute("""
                SELECT time_hour, time_minute, days_of_week
                FROM reminders WHERE reminder_id=?
            """, (reminder["reminder_id"],)).fetchone()
            
            time_hour = row[0]
            time_minute = row[1]
            days_of_week = json.loads(row[2]) if row[2] else None
            
            next_send = _next_send_timestamp(time_hour, time_minute, days_of_week)
            
            con.execute("""
                UPDATE reminders
                SET last_sent=?, next_send=?
                WHERE reminder_id=?
            """, (_now(), next_send, reminder["reminder_id"]))
        
        con.commit()
        return reminders
    finally:
        con.close()

def delete_reminder(reminder_id: int, user_id: int) -> bool:
    """Удаляет напоминание (проверяет владельца)"""
    con = _connect()
    try:
        cursor = con.execute("DELETE FROM reminders WHERE reminder_id=? AND user_id=?", (reminder_id, user_id))
        con.commit()
        return cursor.rowcount > 0
    finally:
        con.close()

def toggle_reminder(reminder_id: int, user_id: int) -> bool:
    """Включает/выключает напоминание"""
    con = _connect()
    try:
        # Получаем текущее состояние
        row = con.execute("SELECT is_active FROM reminders WHERE reminder_id=? AND user_id=?", (reminder_id, user_id)).fetchone()
        if not row:
            return False
        
        new_state = 0 if row[0] else 1
        con.execute("UPDATE reminders SET is_active=? WHERE reminder_id=? AND user_id=?", (new_state, reminder_id, user_id))
        con.commit()
        return True
    finally:
        con.close()

def format_reminder_time(hour: int, minute: int, days_of_week: Optional[List[int]]) -> str:
    """Форматирует время напоминания для отображения"""
    time_str = f"{hour:02d}:{minute:02d}"
    
    if days_of_week is None:
        return f"Ежедневно в {time_str}"
    
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    if len(days_of_week) == 7:
        return f"Ежедневно в {time_str}"
    elif len(days_of_week) == 5 and set(days_of_week) == {0, 1, 2, 3, 4}:
        return f"Будни в {time_str}"
    elif len(days_of_week) == 2 and set(days_of_week) == {5, 6}:
        return f"Выходные в {time_str}"
    else:
        days_str = ", ".join([day_names[d] for d in sorted(days_of_week)])
        return f"{days_str} в {time_str}"
