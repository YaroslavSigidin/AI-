import os
import time
import uuid
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import aiohttp

PAY_PRICE_RUB = os.getenv("PAY_PRICE_RUB", "1490.00").strip()
PAY_FREE_LIMIT = int(os.getenv("PAY_FREE_LIMIT", "15").strip())
PAY_SUB_DAYS = int(os.getenv("PAY_SUB_DAYS", "30").strip())

YK_SHOP_ID = os.getenv("YK_SHOP_ID", "").strip()
YK_SECRET_KEY = os.getenv("YK_SECRET_KEY", "").strip()
YK_RETURN_URL = os.getenv("YK_RETURN_URL", "").strip()

DB_PATH = os.getenv("PAYWALL_DB", "paywall.db")
API_BASE = "https://api.yookassa.ru/v3"

class PaywallError(RuntimeError):
    pass

_conn: Optional[sqlite3.Connection] = None

def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            msg_count INTEGER NOT NULL DEFAULT 0,
            paid_until INTEGER NOT NULL DEFAULT 0,
            pending_payment_id TEXT DEFAULT NULL,
            pending_created INTEGER NOT NULL DEFAULT 0
        )
        """)
        _conn.commit()
    return _conn

def _now_ts() -> int:
    return int(time.time())

def _dt(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")

def _price_value() -> float:
    try:
        return float(PAY_PRICE_RUB.replace(",", "."))
    except Exception:
        return 1490.0

def get_state(user_id: int) -> tuple[int, int, Optional[str]]:
    db = _db()
    row = db.execute("SELECT msg_count, paid_until, pending_payment_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        db.execute("INSERT INTO users(user_id, msg_count, paid_until) VALUES(?,?,?)", (user_id, 0, 0))
        db.commit()
        return 0, 0, None
    return int(row[0]), int(row[1]), (row[2] if row[2] else None)

def inc_free_count(user_id: int) -> int:
    db = _db()
    db.execute(
        "INSERT INTO users(user_id, msg_count, paid_until) VALUES(?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET msg_count=users.msg_count+1",
        (user_id, 1, 0)
    )
    db.commit()
    row = db.execute("SELECT msg_count FROM users WHERE user_id=?", (user_id,)).fetchone()
    return int(row[0]) if row else 1

def is_paid(user_id: int) -> bool:
    _, paid_until, _ = get_state(user_id)
    return paid_until > _now_ts()

def activate_paid(user_id: int, days: int = PAY_SUB_DAYS) -> int:
    db = _db()
    paid_until = int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())
    db.execute(
        "INSERT INTO users(user_id, msg_count, paid_until, pending_payment_id, pending_created) VALUES(?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET paid_until=excluded.paid_until, msg_count=0, pending_payment_id=NULL, pending_created=0",
        (user_id, 0, paid_until, None, 0)
    )
    db.commit()
    return paid_until

def status_text(user_id: int) -> str:
    msg_count, paid_until, pending = get_state(user_id)
    if paid_until > _now_ts():
        return f"✅ Подписка активна до: {_dt(paid_until)}"
    left = max(PAY_FREE_LIMIT - msg_count, 0)
    s = (
        f"🆓 Бесплатный лимит: {PAY_FREE_LIMIT}\n"
        f"✉️ Использовано: {msg_count}\n"
        f"⏳ Осталось: {left}\n"
        f"💳 Подписка: {PAY_PRICE_RUB}₽ / мес\n"
        f"Команда оплаты: /pay"
    )
    if pending:
        s += f"\n\n🧾 Есть незавершённый платёж: {pending}\nНажми «Проверить оплату»."
    return s

async def yk_create_payment_amount(user_id: int, amount_rub: float, description: str, metadata: Optional[dict] = None) -> Tuple[str, str]:
    if not (YK_SHOP_ID and YK_SECRET_KEY):
        raise PaywallError("Не заданы YK_SHOP_ID и/или YK_SECRET_KEY в .env")

    idem_key = str(uuid.uuid4())
    # Добавляем webhook URL для автоматической обработки платежей
    webhook_url = os.getenv("YK_WEBHOOK_URL", "").strip()
    
    payload = {
        "amount": {"value": str(amount_rub), "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": (YK_RETURN_URL or "https://t.me")
        },
        "description": description,
        "metadata": {
            "user_id": str(user_id),
            "plan": "monthly",
            **(metadata or {})
        }
    }
    
    # Добавляем webhook URL, если он указан
    if webhook_url:
        payload["receipt"] = None  # Не требуется для webhook
        # Webhook URL будет настроен в личном кабинете YooKassa

    auth = aiohttp.BasicAuth(YK_SHOP_ID, YK_SECRET_KEY)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{API_BASE}/payments",
            json=payload,
            auth=auth,
            headers={"Idempotence-Key": idem_key}
        ) as r:
            raw = await r.text()
            if r.status not in (200, 201):
                raise PaywallError(f"ЮKassa create failed: HTTP {r.status}: {raw[:500]}")
            data = await r.json()

    payment_id = data.get("id")
    conf_url = (data.get("confirmation") or {}).get("confirmation_url")
    if not payment_id or not conf_url:
        raise PaywallError(f"ЮKassa bad response: {data}")

    db = _db()
    db.execute(
        "INSERT INTO users(user_id, msg_count, paid_until, pending_payment_id, pending_created) VALUES(?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET pending_payment_id=excluded.pending_payment_id, pending_created=excluded.pending_created",
        (user_id, 0, 0, payment_id, _now_ts())
    )
    db.commit()

    return conf_url, payment_id


async def yk_create_payment(user_id: int, description: str = "Подписка на 30 дней") -> Tuple[str, str]:
    return await yk_create_payment_amount(user_id, _price_value(), description)

async def yk_check_payment(payment_id: str) -> dict:
    if not (YK_SHOP_ID and YK_SECRET_KEY):
        raise PaywallError("Не заданы YK_SHOP_ID и/или YK_SECRET_KEY в .env")

    auth = aiohttp.BasicAuth(YK_SHOP_ID, YK_SECRET_KEY)
    timeout = aiohttp.ClientTimeout(total=20)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{API_BASE}/payments/{payment_id}", auth=auth) as r:
            raw = await r.text()
            if r.status != 200:
                raise PaywallError(f"ЮKassa get failed: HTTP {r.status}: {raw[:500]}")
            return await r.json()

async def yk_check_and_activate(user_id: int, payment_id: str) -> Tuple[bool, str]:
    info = await yk_check_payment(payment_id)
    status = (info.get("status") or "").lower()

    if status == "succeeded":
        paid_until = activate_paid(user_id, PAY_SUB_DAYS)
        try:
            from referrals import record_paid_event
            amount = float((info.get("amount") or {}).get("value") or _price_value())
            record_paid_event(user_id, amount)
            promo_code = ((info.get("metadata") or {}).get("promo_code") or "").strip()
            if promo_code:
                from referrals import mark_price_promo_used
                mark_price_promo_used(promo_code, user_id)
        except Exception:
            pass
        return True, f"✅ Оплата прошла! Подписка активна до {_dt(paid_until)}"
    if status in ("pending", "waiting_for_capture"):
        return False, "⏳ Платёж ещё не завершён. Подожди 10–20 секунд и нажми «Проверить оплату» ещё раз."
    return False, f"⚠️ Статус платежа: {status or 'unknown'}"

def get_expiring_subscriptions(days_before: int = 3) -> list[tuple[int, int]]:
    """
    Получает список пользователей, у которых подписка истекает через указанное количество дней.
    Возвращает список кортежей (user_id, paid_until_timestamp)
    """
    db = _db()
    now = _now_ts()
    # Вычисляем timestamp для дня, когда подписка истечет
    from datetime import timedelta
    expire_threshold = int((datetime.now(timezone.utc) + timedelta(days=days_before)).timestamp())
    
    rows = db.execute("""
        SELECT user_id, paid_until 
        FROM users 
        WHERE paid_until > ? AND paid_until <= ? AND paid_until > ?
        ORDER BY paid_until ASC
    """, (now, expire_threshold, now)).fetchall()
    
    return [(int(row[0]), int(row[1])) for row in rows]

def get_expired_subscriptions() -> list[int]:
    """
    Получает список пользователей с истекшими подписками.
    Возвращает список user_id
    """
    db = _db()
    now = _now_ts()
    rows = db.execute("""
        SELECT user_id 
        FROM users 
        WHERE paid_until > 0 AND paid_until <= ?
    """, (now,)).fetchall()
    
    return [int(row[0]) for row in rows]

def mark_auto_renewal_attempted(user_id: int, payment_id: str) -> None:
    """Отмечает, что была попытка автоматического продления"""
    db = _db()
    db.execute("""
        UPDATE users 
        SET pending_payment_id=?, pending_created=?
        WHERE user_id=?
    """, (payment_id, _now_ts(), user_id))
    db.commit()
