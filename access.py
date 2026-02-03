import os
import time
import sqlite3
from typing import Tuple

DB_PATH = os.getenv("ACCESS_DB", "access.sqlite3")

FREE_LIMIT = int(os.getenv("FREE_LIMIT", "15"))
FREE_PERIOD_DAYS = int(os.getenv("FREE_PERIOD_DAYS", "30"))
PROMO_DAYS = int(os.getenv("PROMO_DAYS", "3650"))

PROMO_CODES_RAW = os.getenv("PROMO_CODES", "").strip()

def _now() -> int:
    return int(time.time())

def _connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        period_start INTEGER NOT NULL,
        used INTEGER NOT NULL,
        paid_until INTEGER NOT NULL
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS promo_uses(
        code TEXT PRIMARY KEY,
        used INTEGER NOT NULL
    )
    """)
    return con

def _parse_codes():
    """
    PROMO_CODES format:
      CODE:MAXUSES,CODE2:0
    MAXUSES 0 => unlimited
    """
    codes = {}
    if not PROMO_CODES_RAW:
        return codes
    for part in PROMO_CODES_RAW.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            code, mx = part.split(":", 1)
            code = code.strip()
            try:
                mxn = int(mx.strip())
            except:
                mxn = 0
            if code:
                codes[code] = max(mxn, 0)
        else:
            codes[part] = 0
    return codes

PROMO_CODES = _parse_codes()

def _get_user(con, user_id: int):
    row = con.execute(
        "SELECT user_id, period_start, used, paid_until FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()
    if row:
        return {"user_id": row[0], "period_start": row[1], "used": row[2], "paid_until": row[3]}
    # new user
    now = _now()
    u = {"user_id": user_id, "period_start": now, "used": 0, "paid_until": 0}
    con.execute(
        "INSERT INTO users(user_id, period_start, used, paid_until) VALUES(?,?,?,?)",
        (user_id, u["period_start"], u["used"], u["paid_until"])
    )
    con.commit()
    return u

def is_paid(user_id: int) -> bool:
    con = _connect()
    try:
        u = _get_user(con, user_id)
        return int(u["paid_until"]) > _now()
    finally:
        con.close()

def grant_paid(user_id: int, days: int) -> None:
    con = _connect()
    try:
        u = _get_user(con, user_id)
        now = _now()
        base = max(int(u["paid_until"]), now)
        paid_until = base + int(days) * 86400
        con.execute("UPDATE users SET paid_until=? WHERE user_id=?", (paid_until, user_id))
        con.commit()
    finally:
        con.close()

def apply_promo(user_id: int, code: str) -> Tuple[bool, str]:
    code = (code or "").strip()
    if not code:
        return False, "Промокод пустой."
    if code not in PROMO_CODES:
        return False, "Неверный промокод."
    max_uses = PROMO_CODES[code]

    con = _connect()
    try:
        row = con.execute("SELECT used FROM promo_uses WHERE code=?", (code,)).fetchone()
        used = int(row[0]) if row else 0

        if max_uses != 0 and used >= max_uses:
            return False, "Этот промокод уже исчерпан."

        # inc use
        if row:
            con.execute("UPDATE promo_uses SET used=? WHERE code=?", (used + 1, code))
        else:
            con.execute("INSERT INTO promo_uses(code, used) VALUES(?,?)", (code, 1))

        # grant long paid
        u = _get_user(con, user_id)
        now = _now()
        base = max(int(u["paid_until"]), now)
        paid_until = base + int(PROMO_DAYS) * 86400
        con.execute("UPDATE users SET paid_until=? WHERE user_id=?", (paid_until, user_id))
        con.commit()

        return True, f"✅ Промо активировано. Доступ открыт на {PROMO_DAYS} дней."
    finally:
        con.close()

def check_and_hit(user_id: int) -> Tuple[bool, int]:
    """
    Returns (allowed, remaining_free)
    """
    con = _connect()
    try:
        u = _get_user(con, user_id)
        now = _now()

        # paid?
        if int(u["paid_until"]) > now:
            return True, 999999

        period_len = int(FREE_PERIOD_DAYS) * 86400
        period_start = int(u["period_start"])

        if now - period_start >= period_len:
            # reset period
            period_start = now
            used = 0
            con.execute("UPDATE users SET period_start=?, used=? WHERE user_id=?", (period_start, used, user_id))
            con.commit()
        else:
            used = int(u["used"])

        if used >= int(FREE_LIMIT):
            return False, 0

        used += 1
        con.execute("UPDATE users SET used=? WHERE user_id=?", (used, user_id))
        con.commit()
        remaining = max(int(FREE_LIMIT) - used, 0)
        return True, remaining
    finally:
        con.close()

def status_text(user_id: int) -> str:
    con = _connect()
    try:
        u = _get_user(con, user_id)
        now = _now()
        paid_until = int(u["paid_until"])
        if paid_until > now:
            days_left = int((paid_until - now) / 86400)
            return f"⭐ Подписка активна. Осталось ~{days_left} дней."
        # free
        period_len = int(FREE_PERIOD_DAYS) * 86400
        left_time = max(period_len - (now - int(u["period_start"])), 0)
        days_to_reset = int(left_time / 86400) + 1
        remaining = max(int(FREE_LIMIT) - int(u["used"]), 0)
        return f"🆓 Бесплатно: осталось {remaining} сообщений. Сброс через ~{days_to_reset} дн."
    finally:
        con.close()
