import os
import sqlite3
import time
import secrets
import string
import hashlib
import hmac
import base64
from typing import Optional, Dict, List

DB_PATH = os.getenv("REFERRALS_DB", "referrals.db")
PRICE_PROMO_AMOUNTS = [1000, 2000, 3000, 4000, 5000]
SESSION_TTL_DAYS = 30


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("""
    CREATE TABLE IF NOT EXISTS trainers (
        trainer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        trainer_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS user_referrals (
        user_id INTEGER PRIMARY KEY,
        trainer_id TEXT NOT NULL,
        promo_code TEXT NOT NULL,
        bound_at INTEGER NOT NULL,
        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id),
        FOREIGN KEY (promo_code) REFERENCES promo_codes(code)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS paid_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        trainer_id TEXT NOT NULL,
        amount_rub REAL NOT NULL,
        paid_at INTEGER NOT NULL,
        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS trainer_price_promos (
        code TEXT PRIMARY KEY,
        trainer_id TEXT NOT NULL,
        amount_rub REAL NOT NULL,
        created_at INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        used_by_user_id INTEGER,
        used_at INTEGER,
        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS trainer_auth (
        trainer_id TEXT PRIMARY KEY,
        login TEXT NOT NULL UNIQUE,
        password_salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        password_plain TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS trainer_sessions (
        token TEXT PRIMARY KEY,
        trainer_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        username TEXT,
        trainer_id TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_paid_events_trainer_time ON paid_events(trainer_id, paid_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_promo_codes_trainer ON promo_codes(trainer_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_price_promos_trainer ON trainer_price_promos(trainer_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_trainer_auth_login ON trainer_auth(login)")
    _ensure_column(con, "trainer_auth", "password_plain", "TEXT")
    con.commit()
    return con


def _ensure_column(con: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    cols = [row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()]
    if column in cols:
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _ensure_trainer_auth(con: sqlite3.Connection, trainer_id: str) -> tuple[str, str]:
    row = con.execute(
        "SELECT login, password_plain FROM trainer_auth WHERE trainer_id=?",
        (trainer_id,)
    ).fetchone()
    if row:
        login_value = row[0] or ""
        password_plain = row[1] or ""
        if not login_value:
            login_value = _generate_login(con)
            con.execute(
                "UPDATE trainer_auth SET login=?, updated_at=? WHERE trainer_id=?",
                (login_value, _now(), trainer_id)
            )
        if not password_plain:
            password_plain = _generate_password()
            salt_b64, hash_b64 = _hash_password(password_plain)
            con.execute(
                "UPDATE trainer_auth SET password_salt=?, password_hash=?, password_plain=?, updated_at=? "
                "WHERE trainer_id=?",
                (salt_b64, hash_b64, password_plain, _now(), trainer_id)
            )
        return login_value, password_plain

    login_value = _generate_login(con)
    password_plain = _generate_password()
    salt_b64, hash_b64 = _hash_password(password_plain)
    con.execute(
        "INSERT INTO trainer_auth(trainer_id, login, password_salt, password_hash, password_plain, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (trainer_id, login_value, salt_b64, hash_b64, password_plain, _now(), _now())
    )
    return login_value, password_plain


def _now() -> int:
    return int(time.time())


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _normalize_numeric_code(code: str) -> str:
    return "".join(ch for ch in (code or "") if ch.isdigit())


MAX_PROMO_LEN = 64


def _normalize_promo(code: str) -> str:
    return _normalize_code(code)


def _validate_promo(code: str) -> str:
    normalized = _normalize_promo(code)
    if not normalized:
        raise ValueError("promo code is required")
    if len(normalized) > MAX_PROMO_LEN:
        raise ValueError("promo code is too long")
    return normalized


def _normalize_login(login: str) -> str:
    return (login or "").strip().lower()


def _hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(dk).decode("ascii")


def _verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(actual, expected)


def _generate_login(con: sqlite3.Connection) -> str:
    for _ in range(100):
        suffix = "".join(secrets.choice(string.digits) for _ in range(4))
        login = f"coach{suffix}"
        row = con.execute("SELECT 1 FROM trainer_auth WHERE login=?", (login,)).fetchone()
        if not row:
            return login
    raise RuntimeError("failed to generate unique login")


def _generate_password(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_promo_code(prefix: str = "", length: int = 4) -> str:
    alphabet = string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        full_code = f"{prefix}{code}" if prefix else code
        con = _connect()
        try:
            row = con.execute("SELECT code FROM promo_codes WHERE code=?", (full_code,)).fetchone()
            if not row:
                return full_code
        finally:
            con.close()

def _generate_price_promo_code(amount_rub: int, con: sqlite3.Connection, length: int = 4) -> str:
    alphabet = string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        row = con.execute("SELECT code FROM trainer_price_promos WHERE code=?", (code,)).fetchone()
        row2 = con.execute("SELECT code FROM promo_codes WHERE code=?", (code,)).fetchone()
        if not row and not row2:
            return code


def _insert_price_promos(con: sqlite3.Connection, trainer_id: str, price_promos: Optional[Dict[int, str]] = None) -> List[Dict]:
    created = []
    provided = price_promos or {}
    for amount, raw in provided.items():
        if amount not in PRICE_PROMO_AMOUNTS:
            continue
        code = _validate_promo(raw)
        exists = con.execute(
            "SELECT code FROM trainer_price_promos WHERE code=?",
            (code,)
        ).fetchone()
        exists2 = con.execute(
            "SELECT code FROM promo_codes WHERE code=?",
            (code,)
        ).fetchone()
        if exists or exists2:
            raise ValueError(f"promo code {code} already exists")
        con.execute(
            "INSERT INTO trainer_price_promos(code, trainer_id, amount_rub, created_at, is_active) VALUES(?,?,?,?,1)",
            (code, trainer_id, float(amount), _now())
        )
        con.execute(
            "INSERT OR IGNORE INTO promo_codes(code, trainer_id, created_at, is_active) VALUES(?,?,?,1)",
            (code, trainer_id, _now())
        )
        created.append({"code": code, "amount_rub": float(amount)})
    return created


def create_trainer(name: str, login: Optional[str] = None, password: Optional[str] = None,
                   price_promos: Optional[Dict[int, str]] = None) -> Dict:
    trainer_id = f"TRN{_now()}"
    con = _connect()
    try:
        name_value = (name or "").strip()
        login_value = _normalize_login(login)
        if login_value:
            existing = con.execute(
                "SELECT 1 FROM trainer_auth WHERE login=?",
                (login_value,)
            ).fetchone()
            if existing:
                raise ValueError("login already exists")
        else:
            login_value = _generate_login(con)
        password_value = password or _generate_password()
        salt_b64, hash_b64 = _hash_password(password_value)
        con.execute(
            "INSERT INTO trainers(trainer_id, name, created_at, is_active) VALUES(?,?,?,1)",
            (trainer_id, name_value, _now())
        )
        con.execute(
            "INSERT INTO trainer_auth(trainer_id, login, password_salt, password_hash, password_plain, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (trainer_id, login_value, salt_b64, hash_b64, password_value, _now(), _now())
        )
        price_list = _insert_price_promos(con, trainer_id, price_promos)
        con.commit()
        return {
            "trainer_id": trainer_id,
            "login": login_value,
            "password": password_value,
            "price_promos": price_list,
        }
    finally:
        con.close()


def list_trainers() -> List[Dict]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT t.trainer_id, t.name, t.created_at, t.is_active, a.login, a.password_plain "
            "FROM trainers t LEFT JOIN trainer_auth a ON t.trainer_id=a.trainer_id "
            "ORDER BY t.created_at DESC"
        ).fetchall()
        trainers: List[Dict] = []
        for r in rows:
            trainer_id = r[0]
            login_value = r[4] or ""
            password_plain = r[5] or ""
            if not login_value or not password_plain:
                login_value, password_plain = _ensure_trainer_auth(con, trainer_id)
                con.commit()
            trainers.append(
                {
                    "trainer_id": trainer_id,
                    "name": r[1],
                    "created_at": r[2],
                    "is_active": bool(r[3]),
                    "login": login_value,
                    "password_plain": password_plain,
                }
            )
        return trainers
    finally:
        con.close()


def create_promo_code(trainer_id: str, code: Optional[str] = None) -> str:
    code = _validate_promo(code or "")
    con = _connect()
    try:
        existing = con.execute(
            "SELECT 1 FROM promo_codes WHERE code=?",
            (code,)
        ).fetchone()
        if existing:
            raise ValueError(f"promo code {code} already exists")
        con.execute(
            "INSERT INTO promo_codes(code, trainer_id, created_at, is_active) VALUES(?,?,?,1)",
            (code, trainer_id, _now())
        )
        con.commit()
    return code


def add_price_promo(trainer_id: str, amount_rub: float, code: Optional[str] = None) -> Dict:
    trainer_id = (trainer_id or "").strip()
    if not trainer_id:
        raise ValueError("trainer_id required")
    try:
        amount_value = float(amount_rub)
    except Exception:
        raise ValueError("invalid amount")
    if amount_value <= 0:
        raise ValueError("amount must be positive")

    con = _connect()
    try:
        if code:
            code = _validate_promo(code)
        else:
            code = _generate_price_promo_code(int(round(amount_value)), con)

        row = con.execute("SELECT code FROM trainer_price_promos WHERE code=?", (code,)).fetchone()
        row2 = con.execute("SELECT code FROM promo_codes WHERE code=?", (code,)).fetchone()
        if row or row2:
            raise ValueError(f"promo code {code} already exists")

        con.execute(
            "INSERT INTO trainer_price_promos(code, trainer_id, amount_rub, created_at, is_active) VALUES(?,?,?,?,1)",
            (code, trainer_id, float(amount_value), _now())
        )
        con.execute(
            "INSERT OR IGNORE INTO promo_codes(code, trainer_id, created_at, is_active) VALUES(?,?,?,1)",
            (code, trainer_id, _now())
        )
        con.commit()
        return {"code": code, "amount_rub": amount_value}
    finally:
        con.close()
    finally:
        con.close()


def list_trainer_price_promos(trainer_id: str) -> List[Dict]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT code, amount_rub, is_active, used_by_user_id, used_at FROM trainer_price_promos "
            "WHERE trainer_id=? ORDER BY amount_rub ASC",
            (trainer_id,)
        ).fetchall()
        if not rows:
            promo_rows = con.execute(
                "SELECT code, created_at FROM promo_codes WHERE trainer_id=? ORDER BY created_at DESC",
                (trainer_id,)
            ).fetchall()
            existing = {}
            for code, _created_at in promo_rows:
                for amount in PRICE_PROMO_AMOUNTS:
                    prefix = f"D{amount}"
                    if code.startswith(prefix) and len(code) == len(prefix) + 4 and code[len(prefix):].isdigit():
                        if amount not in existing:
                            existing[amount] = code
                        break
            if existing:
                for amount, code in existing.items():
                    con.execute(
                        "INSERT OR IGNORE INTO trainer_price_promos(code, trainer_id, amount_rub, created_at, is_active) "
                        "VALUES(?,?,?,?,1)",
                        (code, trainer_id, float(amount), _now())
                    )
                con.commit()
                rows = con.execute(
                    "SELECT code, amount_rub, is_active, used_by_user_id, used_at FROM trainer_price_promos "
                    "WHERE trainer_id=? ORDER BY amount_rub ASC",
                    (trainer_id,)
                ).fetchall()
        return [
            {
                "code": r[0],
                "amount_rub": float(r[1]),
                "is_active": bool(r[2]),
                "used_by_user_id": (int(r[3]) if r[3] is not None else None),
                "used_at": (int(r[4]) if r[4] is not None else None),
            }
            for r in rows
        ]
    finally:
        con.close()


def get_price_promo(code: str) -> Optional[Dict]:
    code = _normalize_code(code)
    if not code:
        return None
    con = _connect()
    try:
        row = con.execute(
            "SELECT code, trainer_id, amount_rub, is_active, used_by_user_id, used_at "
            "FROM trainer_price_promos WHERE code=?",
            (code,)
        ).fetchone()
        if not row:
            return None
        return {
            "code": row[0],
            "trainer_id": row[1],
            "amount_rub": float(row[2]),
            "is_active": bool(row[3]),
            "used_by_user_id": (int(row[4]) if row[4] is not None else None),
            "used_at": (int(row[5]) if row[5] is not None else None),
        }
    finally:
        con.close()


def mark_price_promo_used(code: str, user_id: int, paid_at: Optional[int] = None) -> bool:
    paid_at = paid_at or _now()
    con = _connect()
    try:
        row = con.execute(
            "SELECT used_by_user_id FROM trainer_price_promos WHERE code=? AND is_active=1",
            (_normalize_code(code),)
        ).fetchone()
        if not row:
            return False
        if row[0] is not None and int(row[0]) != int(user_id):
            return False
        con.execute(
            "UPDATE trainer_price_promos SET used_by_user_id=?, used_at=? WHERE code=?",
            (int(user_id), paid_at, _normalize_code(code))
        )
        con.commit()
        return True
    finally:
        con.close()


def bind_user_to_trainer_id(user_id: int, trainer_id: str, code: str) -> tuple[bool, str, Optional[str]]:
    con = _connect()
    try:
        existing = con.execute(
            "SELECT trainer_id FROM user_referrals WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if existing:
            return False, "Ты уже привязан к тренеру", existing[0]
        con.execute(
            "INSERT INTO user_referrals(user_id, trainer_id, promo_code, bound_at) VALUES(?,?,?,?)",
            (user_id, trainer_id, _normalize_code(code), _now())
        )
        con.commit()
        return True, "Ты привязан к тренеру", trainer_id
    finally:
        con.close()


def list_trainer_promos(trainer_id: str) -> List[str]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT code FROM promo_codes WHERE trainer_id=? AND is_active=1 ORDER BY created_at DESC",
            (trainer_id,)
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def get_trainer_by_code(code: str) -> Optional[Dict]:
    code = _normalize_code(code)
    if not code:
        return None
    con = _connect()
    try:
        row = con.execute(
            "SELECT p.trainer_id, t.name FROM promo_codes p JOIN trainers t ON p.trainer_id=t.trainer_id WHERE p.code=? AND p.is_active=1",
            (code,)
        ).fetchone()
        if not row:
            return None
        return {"trainer_id": row[0], "name": row[1], "code": code}
    finally:
        con.close()


def bind_user_to_trainer(user_id: int, code: str) -> tuple[bool, str, Optional[str]]:
    info = get_trainer_by_code(code)
    if not info:
        return False, "Промокод не найден", None
    trainer_id = info["trainer_id"]
    con = _connect()
    try:
        existing = con.execute(
            "SELECT trainer_id FROM user_referrals WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if existing:
            return False, "Ты уже привязан к тренеру", trainer_id
        con.execute(
            "INSERT INTO user_referrals(user_id, trainer_id, promo_code, bound_at) VALUES(?,?,?,?)",
            (user_id, trainer_id, _normalize_code(code), _now())
        )
        con.commit()
        return True, f"Промокод принят. Ты привязан к тренеру «{info['name']}»", trainer_id
    finally:
        con.close()


def get_user_trainer(user_id: int) -> Optional[Dict]:
    con = _connect()
    try:
        row = con.execute(
            "SELECT trainer_id, promo_code, bound_at FROM user_referrals WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "trainer_id": row[0],
            "promo_code": row[1],
            "bound_at": row[2]
        }
    finally:
        con.close()


def get_user_profile(user_id: int) -> Optional[Dict]:
    con = _connect()
    try:
        row = con.execute(
            "SELECT full_name, username, trainer_id, created_at, updated_at FROM user_profiles WHERE user_id=?",
            (int(user_id),)
        ).fetchone()
        if not row:
            return None
        return {
            "user_id": int(user_id),
            "full_name": row[0],
            "username": row[1] or "",
            "trainer_id": row[2],
            "created_at": int(row[3]),
            "updated_at": int(row[4]),
        }
    finally:
        con.close()


def upsert_user_profile(user_id: int, full_name: str, username: Optional[str] = None,
                        trainer_id: Optional[str] = None) -> None:
    name_value = (full_name or "").strip()
    if not name_value:
        raise ValueError("full_name required")
    uname_value = (username or "").strip()
    now = _now()
    con = _connect()
    try:
        con.execute(
            "INSERT INTO user_profiles(user_id, full_name, username, trainer_id, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, username=excluded.username, "
            "trainer_id=excluded.trainer_id, updated_at=excluded.updated_at",
            (int(user_id), name_value, uname_value, trainer_id, now, now)
        )
        con.commit()
    finally:
        con.close()


def record_paid_event(user_id: int, amount_rub: float, paid_at: Optional[int] = None) -> bool:
    paid_at = paid_at or _now()
    ref = get_user_trainer(user_id)
    if not ref:
        return False
    con = _connect()
    try:
        con.execute(
            "INSERT INTO paid_events(user_id, trainer_id, amount_rub, paid_at) VALUES(?,?,?,?)",
            (user_id, ref["trainer_id"], float(amount_rub), paid_at)
        )
        con.commit()
        return True
    finally:
        con.close()


def get_user_paid_stats(user_id: int) -> Dict:
    con = _connect()
    try:
        total_row = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_rub), 0) FROM paid_events WHERE user_id=?",
            (int(user_id),)
        ).fetchone()
        last_row = con.execute(
            "SELECT amount_rub, paid_at FROM paid_events WHERE user_id=? ORDER BY paid_at DESC LIMIT 1",
            (int(user_id),)
        ).fetchone()
        return {
            "paid_count": int(total_row[0]) if total_row else 0,
            "paid_total_rub": float(total_row[1]) if total_row else 0.0,
            "last_amount_rub": float(last_row[0]) if last_row else 0.0,
            "last_paid_at": int(last_row[1]) if last_row else None,
        }
    finally:
        con.close()


def get_trainer_paid_count(trainer_id: str, days: int) -> int:
    since = _now() - days * 86400
    con = _connect()
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM paid_events WHERE trainer_id=? AND paid_at>=?",
            (trainer_id, since)
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        con.close()


def list_trainers_with_stats(days: int) -> List[Dict]:
    trainers = list_trainers()
    for t in trainers:
        t["paid_clients"] = get_trainer_paid_count(t["trainer_id"], days)
        t["promos"] = list_trainer_promos(t["trainer_id"])
        t["price_promos"] = list_trainer_price_promos(t["trainer_id"])
    return trainers


def delete_trainer(trainer_id: str) -> None:
    con = _connect()
    try:
        con.execute("DELETE FROM paid_events WHERE trainer_id=?", (trainer_id,))
        con.execute("DELETE FROM user_referrals WHERE trainer_id=?", (trainer_id,))
        con.execute("DELETE FROM promo_codes WHERE trainer_id=?", (trainer_id,))
        con.execute("DELETE FROM trainer_price_promos WHERE trainer_id=?", (trainer_id,))
        con.execute("DELETE FROM trainer_sessions WHERE trainer_id=?", (trainer_id,))
        con.execute("DELETE FROM trainer_auth WHERE trainer_id=?", (trainer_id,))
        con.execute("DELETE FROM trainers WHERE trainer_id=?", (trainer_id,))
        con.commit()
    finally:
        con.close()


def verify_trainer_login(login: str, password: str) -> Optional[Dict]:
    login_value = _normalize_login(login)
    if not login_value or not password:
        return None
    con = _connect()
    try:
        row = con.execute(
            "SELECT trainer_id, password_salt, password_hash FROM trainer_auth WHERE login=?",
            (login_value,)
        ).fetchone()
        if not row:
            return None
        if not _verify_password(password, row[1], row[2]):
            return None
        name_row = con.execute(
            "SELECT name FROM trainers WHERE trainer_id=?",
            (row[0],)
        ).fetchone()
        return {"trainer_id": row[0], "name": name_row[0] if name_row else ""}
    finally:
        con.close()


def reset_trainer_password(trainer_id: str) -> Optional[Dict]:
    trainer_id = (trainer_id or "").strip()
    if not trainer_id:
        return None
    new_password = _generate_password()
    salt_b64, hash_b64 = _hash_password(new_password)
    con = _connect()
    try:
        row = con.execute(
            "SELECT login FROM trainer_auth WHERE trainer_id=?",
            (trainer_id,)
        ).fetchone()
        if not row:
            return None
        con.execute(
            "UPDATE trainer_auth SET password_salt=?, password_hash=?, password_plain=?, updated_at=? "
            "WHERE trainer_id=?",
            (salt_b64, hash_b64, password_value, _now(), trainer_id)
        )
        con.commit()
        return {"trainer_id": trainer_id, "login": row[0], "password": new_password}
    finally:
        con.close()


def create_trainer_session(trainer_id: str, ttl_days: int = SESSION_TTL_DAYS) -> Dict:
    token = secrets.token_urlsafe(32)
    created_at = _now()
    expires_at = created_at + ttl_days * 86400
    con = _connect()
    try:
        con.execute(
            "INSERT INTO trainer_sessions(token, trainer_id, created_at, expires_at) VALUES(?,?,?,?)",
            (token, trainer_id, created_at, expires_at)
        )
        con.commit()
        return {"token": token, "trainer_id": trainer_id, "expires_at": expires_at}
    finally:
        con.close()


def verify_trainer_token(token: str) -> Optional[Dict]:
    token_value = (token or "").strip()
    if not token_value:
        return None
    con = _connect()
    try:
        row = con.execute(
            "SELECT trainer_id, expires_at FROM trainer_sessions WHERE token=?",
            (token_value,)
        ).fetchone()
        if not row:
            return None
        if int(row[1]) < _now():
            return None
        return {"trainer_id": row[0]}
    finally:
        con.close()


def get_trainer_by_id(trainer_id: str) -> Optional[Dict]:
    con = _connect()
    try:
        row = con.execute(
            "SELECT trainer_id, name FROM trainers WHERE trainer_id=?",
            (trainer_id,)
        ).fetchone()
        if not row:
            return None
        return {"trainer_id": row[0], "name": row[1]}
    finally:
        con.close()


def get_trainer_clients(trainer_id: str, days: int) -> List[Dict]:
    since = _now() - days * 86400
    con = _connect()
    try:
        rows = con.execute(
            "SELECT user_id, promo_code, bound_at FROM user_referrals WHERE trainer_id=? AND bound_at>=? ORDER BY bound_at DESC",
            (trainer_id, since)
        ).fetchall()
        user_ids = [int(r[0]) for r in rows]
        profiles = {}
        if user_ids:
            placeholders = ",".join("?" for _ in user_ids)
            p_rows = con.execute(
                f"SELECT user_id, full_name, username FROM user_profiles WHERE user_id IN ({placeholders})",
                user_ids
            ).fetchall()
            for uid, full_name, username in p_rows:
                profiles[int(uid)] = {
                    "full_name": full_name,
                    "username": username or ""
                }
        result = []
        for r in rows:
            uid = int(r[0])
            prof = profiles.get(uid, {})
            result.append(
                {
                    "user_id": uid,
                    "promo_code": r[1],
                    "bound_at": r[2],
                    "full_name": prof.get("full_name"),
                    "username": prof.get("username"),
                }
            )
        return result
    finally:
        con.close()
