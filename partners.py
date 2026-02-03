"""
Партнерская программа для фитнес-клубов
"""
import os
import sqlite3
import time
import secrets
import string
from typing import Optional, Tuple, List, Dict
from pathlib import Path

DB_PATH = os.getenv("PARTNERS_DB", "partners.db")
PARTNER_TRIAL_DAYS = int(os.getenv("PARTNER_TRIAL_DAYS", "7"))  # 7 дней тестового периода

def _connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    
    # Таблица партнеров (фитнес-клубы)
    con.execute("""
    CREATE TABLE IF NOT EXISTS partners (
        partner_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact TEXT,
        created_at INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """)
    
    # Таблица промокодов партнеров
    con.execute("""
    CREATE TABLE IF NOT EXISTS partner_promos (
        code TEXT PRIMARY KEY,
        partner_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        used_at INTEGER,
        used_by_user_id INTEGER,
        is_used INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (partner_id) REFERENCES partners(partner_id)
    )
    """)
    
    # Индекс для быстрого поиска
    con.execute("""
    CREATE INDEX IF NOT EXISTS idx_partner_promos_code ON partner_promos(code)
    """)
    con.execute("""
    CREATE INDEX IF NOT EXISTS idx_partner_promos_partner ON partner_promos(partner_id)
    """)
    
    con.commit()
    return con

def _now() -> int:
    return int(time.time())

def generate_promo_code(prefix: str = "", length: int = 8) -> str:
    """Генерирует уникальный промокод"""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        full_code = f"{prefix}-{code}" if prefix else code
        # Проверяем уникальность
        con = _connect()
        try:
            row = con.execute("SELECT code FROM partner_promos WHERE code=?", (full_code,)).fetchone()
            if not row:
                return full_code
        finally:
            con.close()

def create_partner(name: str, contact: str = "") -> str:
    """Создает нового партнера и возвращает его ID"""
    partner_id = f"CLUB{int(time.time())}"
    con = _connect()
    try:
        con.execute(
            "INSERT INTO partners(partner_id, name, contact, created_at, is_active) VALUES(?,?,?,?,?)",
            (partner_id, name, contact, _now(), 1)
        )
        con.commit()
        return partner_id
    finally:
        con.close()

def create_partner_promos(partner_id: str, count: int = 10) -> List[str]:
    """Создает пачку промокодов для партнера"""
    con = _connect()
    codes = []
    try:
        for _ in range(count):
            code = generate_promo_code(prefix=partner_id)
            con.execute(
                "INSERT INTO partner_promos(code, partner_id, created_at, is_used) VALUES(?,?,?,?)",
                (code, partner_id, _now(), 0)
            )
            codes.append(code)
        con.commit()
        return codes
    finally:
        con.close()

def use_partner_promo(code: str, user_id: int) -> Tuple[bool, str, Optional[int]]:
    """
    Активирует партнерский промокод для пользователя
    Returns: (success, message, days)
    """
    code = (code or "").strip().upper()
    if not code:
        return False, "Промокод не может быть пустым", None
    
    con = _connect()
    try:
        # Проверяем, существует ли промокод и не использован ли он
        row = con.execute(
            "SELECT code, partner_id, is_used, used_by_user_id FROM partner_promos WHERE code=?",
            (code,)
        ).fetchone()
        
        if not row:
            return False, "❌ Промокод не найден", None
        
        is_used = int(row[2])
        if is_used:
            used_by = int(row[3]) if row[3] else None
            if used_by == user_id:
                return False, "⚠️ Вы уже использовали этот промокод", None
            return False, "❌ Этот промокод уже был использован", None
        
        # Активируем промокод
        con.execute(
            "UPDATE partner_promos SET is_used=?, used_at=?, used_by_user_id=? WHERE code=?",
            (1, _now(), user_id, code)
        )
        con.commit()
        
        return True, f"✅ Промокод активирован! Получен тестовый период {PARTNER_TRIAL_DAYS} дней", PARTNER_TRIAL_DAYS
    finally:
        con.close()

def get_partner_stats(partner_id: str) -> Dict:
    """Получает статистику по партнеру"""
    con = _connect()
    try:
        # Общее количество промокодов
        total = con.execute(
            "SELECT COUNT(*) FROM partner_promos WHERE partner_id=?",
            (partner_id,)
        ).fetchone()[0]
        
        # Использованные промокоды
        used = con.execute(
            "SELECT COUNT(*) FROM partner_promos WHERE partner_id=? AND is_used=1",
            (partner_id,)
        ).fetchone()[0]
        
        # Неиспользованные
        unused = total - used
        
        return {
            "total": total,
            "used": used,
            "unused": unused,
            "usage_rate": (used / total * 100) if total > 0 else 0
        }
    finally:
        con.close()

def list_partners() -> List[Dict]:
    """Список всех партнеров"""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT partner_id, name, contact, created_at, is_active FROM partners ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "partner_id": row[0],
                "name": row[1],
                "contact": row[2],
                "created_at": row[3],
                "is_active": bool(row[4])
            }
            for row in rows
        ]
    finally:
        con.close()

def get_partner_info(partner_id: str) -> Optional[Dict]:
    """Информация о партнере"""
    con = _connect()
    try:
        row = con.execute(
            "SELECT partner_id, name, contact, created_at, is_active FROM partners WHERE partner_id=?",
            (partner_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "partner_id": row[0],
            "name": row[1],
            "contact": row[2],
            "created_at": row[3],
            "is_active": bool(row[4]),
            "stats": get_partner_stats(partner_id)
        }
    finally:
        con.close()

def get_partner_promo_codes(partner_id: str, limit: int = 100) -> List[Dict]:
    """Получает список промокодов партнера"""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT code, is_used, used_at, used_by_user_id, created_at FROM partner_promos WHERE partner_id=? ORDER BY created_at DESC LIMIT ?",
            (partner_id, limit)
        ).fetchall()
        return [
            {
                "code": row[0],
                "is_used": bool(row[1]),
                "used_at": row[2],
                "used_by_user_id": row[3],
                "created_at": row[4]
            }
            for row in rows
        ]
    finally:
        con.close()
