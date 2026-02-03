"""
Модуль для управления настройками уведомлений и мотивирующими сообщениями
"""
import os
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

DB_PATH = os.getenv("NOTIFICATIONS_DB", "notifications.db")

# Частоты уведомлений
FREQUENCY_3_PER_DAY = "3_per_day"  # 3 раза в день
FREQUENCY_1_PER_DAY = "1_per_day"  # 1 раз в день
FREQUENCY_1_PER_WEEK = "1_per_week"  # 1 раз в неделю
FREQUENCY_DISABLED = "disabled"  # Отключено

FREQUENCY_OPTIONS = {
    FREQUENCY_3_PER_DAY: "3 раза в день",
    FREQUENCY_1_PER_DAY: "1 раз в день",
    FREQUENCY_1_PER_WEEK: "1 раз в неделю",
    FREQUENCY_DISABLED: "Отключено"
}

def _connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("""
        CREATE TABLE IF NOT EXISTS notification_settings (
            user_id INTEGER PRIMARY KEY,
            frequency TEXT NOT NULL DEFAULT '1_per_day',
            last_sent INTEGER DEFAULT 0,
            last_sent_date TEXT DEFAULT '',
            sent_count_today INTEGER DEFAULT 0,
            updated_at INTEGER NOT NULL DEFAULT 0
        )
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_notif_user ON notification_settings(user_id)
    """)
    con.commit()
    return con

def _now() -> int:
    return int(time.time())

def _today_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

def get_frequency(user_id: int) -> str:
    """Получает частоту уведомлений для пользователя"""
    con = _connect()
    try:
        row = con.execute(
            "SELECT frequency FROM notification_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if row:
            return row[0]
        # По умолчанию
        con.execute(
            "INSERT INTO notification_settings(user_id, frequency, updated_at) VALUES(?, ?, ?)",
            (user_id, FREQUENCY_1_PER_DAY, _now())
        )
        con.commit()
        return FREQUENCY_1_PER_DAY
    finally:
        con.close()

def set_frequency(user_id: int, frequency: str) -> bool:
    """Устанавливает частоту уведомлений"""
    if frequency not in FREQUENCY_OPTIONS:
        return False
    con = _connect()
    try:
        con.execute("""
            INSERT INTO notification_settings(user_id, frequency, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                frequency=excluded.frequency,
                updated_at=excluded.updated_at
        """, (user_id, frequency, _now()))
        con.commit()
        return True
    finally:
        con.close()

def can_send_notification(user_id: int) -> Tuple[bool, str]:
    """
    Проверяет, можно ли отправить уведомление пользователю.
    Возвращает (можно_ли, причина)
    """
    frequency = get_frequency(user_id)
    
    if frequency == FREQUENCY_DISABLED:
        return False, "Уведомления отключены"
    
    con = _connect()
    try:
        row = con.execute(
            "SELECT last_sent, last_sent_date, sent_count_today FROM notification_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()
        
        if not row:
            return True, ""
        
        last_sent, last_sent_date, sent_count_today = row
        today = _today_str()
        
        # Если сегодня еще не отправляли - можно
        if last_sent_date != today:
            return True, ""
        
        # Проверяем частоту
        if frequency == FREQUENCY_1_PER_WEEK:
            # Раз в неделю - проверяем, прошла ли неделя
            if last_sent and (time.time() - last_sent) < 7 * 24 * 3600:
                return False, "Уже отправлено на этой неделе"
            return True, ""
        
        elif frequency == FREQUENCY_1_PER_DAY:
            # 1 раз в день - если сегодня уже отправляли, нельзя
            if last_sent_date == today:
                return False, "Уже отправлено сегодня"
            return True, ""
        
        elif frequency == FREQUENCY_3_PER_DAY:
            # 3 раза в день - проверяем количество сегодня
            if sent_count_today >= 3:
                return False, "Достигнут лимит на сегодня (3 раза)"
            
            # Проверяем интервал между отправками (минимум 4 часа)
            if last_sent and (time.time() - last_sent) < 4 * 3600:
                return False, "Слишком рано после предыдущего уведомления"
            return True, ""
        
        return True, ""
    finally:
        con.close()

def mark_notification_sent(user_id: int) -> None:
    """Отмечает, что уведомление было отправлено"""
    con = _connect()
    try:
        today = _today_str()
        now = _now()
        
        # Получаем текущее количество отправок сегодня
        row = con.execute(
            "SELECT sent_count_today, last_sent_date FROM notification_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()
        
        if row:
            sent_count, last_sent_date = row
            if last_sent_date == today:
                # Увеличиваем счетчик
                new_count = sent_count + 1
            else:
                # Новый день - сбрасываем счетчик
                new_count = 1
        else:
            new_count = 1
        
        con.execute("""
            INSERT INTO notification_settings(user_id, last_sent, last_sent_date, sent_count_today, updated_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_sent=excluded.last_sent,
                last_sent_date=excluded.last_sent_date,
                sent_count_today=excluded.sent_count_today,
                updated_at=excluded.updated_at
        """, (user_id, now, today, new_count, now))
        con.commit()
    finally:
        con.close()

def get_users_for_notification() -> List[int]:
    """Получает список пользователей, которым можно отправить уведомление"""
    con = _connect()
    try:
        # Получаем всех пользователей с включенными уведомлениями
        rows = con.execute("""
            SELECT user_id, frequency, last_sent, last_sent_date, sent_count_today
            FROM notification_settings
            WHERE frequency != ?
        """, (FREQUENCY_DISABLED,)).fetchall()
        
        result = []
        today = _today_str()
        now = _now()
        
        for row in rows:
            user_id, frequency, last_sent, last_sent_date, sent_count_today = row
            
            # Проверяем, можно ли отправить
            if frequency == FREQUENCY_1_PER_WEEK:
                if last_sent and (now - last_sent) < 7 * 24 * 3600:
                    continue
            elif frequency == FREQUENCY_1_PER_DAY:
                if last_sent_date == today:
                    continue
            elif frequency == FREQUENCY_3_PER_DAY:
                if last_sent_date == today and sent_count_today >= 3:
                    continue
                if last_sent and (now - last_sent) < 4 * 3600:
                    continue
            
            result.append(user_id)
        
        return result
    finally:
        con.close()

def get_settings(user_id: int) -> Dict[str, Any]:
    """Получает настройки уведомлений для пользователя"""
    frequency = get_frequency(user_id)
    con = _connect()
    try:
        row = con.execute(
            "SELECT last_sent, last_sent_date, sent_count_today FROM notification_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()
        
        last_sent = row[0] if row else 0
        last_sent_date = row[1] if row else ""
        sent_count_today = row[2] if row else 0
        
        return {
            "frequency": frequency,
            "frequency_label": FREQUENCY_OPTIONS.get(frequency, frequency),
            "last_sent": last_sent,
            "last_sent_date": last_sent_date,
            "sent_count_today": sent_count_today,
            "is_enabled": frequency != FREQUENCY_DISABLED
        }
    finally:
        con.close()
