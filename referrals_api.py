import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sqlite3
from datetime import datetime, timezone

from referrals import (
    PRICE_PROMO_AMOUNTS,
    list_trainers_with_stats,
    create_trainer,
    create_promo_code,
    list_trainer_promos,
    list_trainer_price_promos,
    delete_trainer,
    get_trainer_clients,
    get_user_trainer,
    get_user_profile,
    get_user_paid_stats,
    verify_trainer_login,
    create_trainer_session,
    verify_trainer_token,
    get_trainer_by_id,
    reset_trainer_password,
)

app = FastAPI(title="Referral Dashboard API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrainerCreate(BaseModel):
    name: str
    login: str | None = None
    password: str | None = None
    price_promos: dict[str, str] | None = None


class TrainerLogin(BaseModel):
    login: str
    password: str


class PromoCreate(BaseModel):
    trainer_id: str
    code: str | None = None


def _price_value() -> float:
    raw = os.getenv("PAY_PRICE_RUB", "1490.00").strip()
    try:
        return float(raw.replace(",", "."))
    except Exception:
        return 1490.0


def _tracker_db_path() -> str:
    return (os.getenv("TRACKER_DB_PATH") or "/data/tracker.db").strip()


def _paywall_db_path() -> str:
    return (os.getenv("PAYWALL_DB") or "paywall.db").strip()


def _read_note(user_id: int, day: str, kind: str) -> str:
    conn = sqlite3.connect(_tracker_db_path(), check_same_thread=False)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                user_id TEXT NOT NULL,
                d TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT '',
                updated_at TEXT,
                PRIMARY KEY (user_id, d, kind)
            )
        """)
        conn.commit()
        row = conn.execute(
            "SELECT text FROM notes WHERE user_id=? AND d=? AND kind=?",
            (str(user_id), day, kind)
        ).fetchone()
        return (row[0] or "") if row else ""
    finally:
        conn.close()


def _write_note(user_id: int, day: str, kind: str, text: str) -> None:
    conn = sqlite3.connect(_tracker_db_path(), check_same_thread=False)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                user_id TEXT NOT NULL,
                d TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT '',
                updated_at TEXT,
                PRIMARY KEY (user_id, d, kind)
            )
        """)
        conn.commit()
        conn.execute("""
            INSERT OR REPLACE INTO notes (user_id, d, kind, text, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (str(user_id), day, kind, text or ""))
        conn.commit()
    finally:
        conn.close()


def _workout_days(user_id: int, days: int = 90) -> list[str]:
    conn = sqlite3.connect(_tracker_db_path(), check_same_thread=False)
    try:
        rows = conn.execute(
            "SELECT d, text FROM notes WHERE user_id=? AND kind='workouts' ORDER BY d DESC",
            (str(user_id),)
        ).fetchall()
        result = []
        for d, text in rows:
            if text and text.strip():
                result.append(d)
            if len(result) >= days:
                break
        return result
    finally:
        conn.close()


def _paid_until(user_id: int) -> int:
    conn = sqlite3.connect(_paywall_db_path(), check_same_thread=False)
    try:
        row = conn.execute(
            "SELECT paid_until FROM users WHERE user_id=?",
            (int(user_id),)
        ).fetchone()
        return int(row[0]) if row and row[0] else 0
    finally:
        conn.close()


def _days_left(paid_until: int) -> int:
    if not paid_until:
        return 0
    now = int(datetime.now(timezone.utc).timestamp())
    return max(int((paid_until - now) // 86400), 0)


def _payout_percent() -> float:
    raw = os.getenv("REFERRAL_PAYOUT_PERCENT", "0.5").strip()
    try:
        return float(raw)
    except Exception:
        return 0.5


@app.get("/admin/referrals/trainers")
def trainers(days: int = 7):
    days = 7 if days not in (7, 30, 60) else days
    price = _price_value()
    percent = _payout_percent()
    trainers = list_trainers_with_stats(days)
    for t in trainers:
        t["payout_rub"] = round(t["paid_clients"] * price * percent, 2)
        t["bound_clients"] = len(get_trainer_clients(t["trainer_id"], days))
    return {"trainers": trainers}


@app.post("/admin/referrals/trainers")
def add_trainer(payload: TrainerCreate):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    price_promos = {}
    if payload.price_promos:
        for key, value in payload.price_promos.items():
            try:
                amount = int(str(key).strip())
            except Exception:
                continue
            if amount not in PRICE_PROMO_AMOUNTS:
                raise HTTPException(status_code=400, detail=f"unsupported amount {amount}")
            code = (value or "").strip()
            if code:
                price_promos[amount] = code
    try:
        created = create_trainer(
            name,
            login=payload.login,
            password=payload.password,
            price_promos=price_promos or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "trainer": {
            "trainer_id": created["trainer_id"],
            "name": name,
            "login": created["login"],
            "promo_code": created.get("promo_code"),
        },
        "credentials": {
            "login": created["login"],
            "password": created["password"],
        },
        "promos": list_trainer_promos(created["trainer_id"]),
        "price_promos": list_trainer_price_promos(created["trainer_id"]),
    }


@app.post("/admin/referrals/trainers/{trainer_id}/reset-password")
def trainer_reset_password(trainer_id: str):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    info = reset_trainer_password(trainer_id)
    if not info:
        raise HTTPException(status_code=404, detail="trainer not found")
    return {"trainer_id": info["trainer_id"], "credentials": {"login": info["login"], "password": info["password"]}}


@app.get("/admin/referrals/promos")
def promos(trainer_id: str):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    return {"codes": list_trainer_promos(trainer_id)}


@app.get("/admin/referrals/trainers/{trainer_id}/price-promos")
def trainer_price_promos(trainer_id: str, request: Request):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    _authorize_trainer(request, trainer_id)
    return {"codes": list_trainer_price_promos(trainer_id)}


@app.post("/admin/referrals/promos")
def add_promo(payload: PromoCreate):
    if not payload.trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    if not payload.code or not payload.code.strip():
        raise HTTPException(status_code=400, detail="promo code required")
    code = create_promo_code(payload.trainer_id, payload.code)
    return {"code": code}


@app.delete("/admin/referrals/trainers/{trainer_id}")
def remove_trainer(trainer_id: str):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    delete_trainer(trainer_id)
    return {"success": True}


@app.get("/admin/referrals/trainers/{trainer_id}/clients")
def trainer_clients(trainer_id: str, request: Request, days: int = 7):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    days = 7 if days not in (7, 30, 60) else days
    _authorize_trainer(request, trainer_id)
    return {"clients": get_trainer_clients(trainer_id, days)}


@app.get("/admin/referrals/user/{user_id}/trainer")
def user_trainer(user_id: int):
    info = get_user_trainer(int(user_id))
    return {"trainer": info}


@app.get("/admin/referrals/trainers/{trainer_id}/clients/{user_id}/summary")
def trainer_client_summary(trainer_id: str, user_id: int, request: Request, days: int = 90):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    _authorize_trainer(request, trainer_id)
    client = get_user_trainer(int(user_id))
    if not client or client["trainer_id"] != trainer_id:
        raise HTTPException(status_code=404, detail="client not found")
    paid = get_user_paid_stats(int(user_id))
    paid_until = _paid_until(int(user_id))
    workout_days = _workout_days(int(user_id), days=days)
    profile = get_user_profile(int(user_id)) or {}
    return {
        "user_id": int(user_id),
        "trainer_id": trainer_id,
        "promo_code": client.get("promo_code"),
        "bound_at": client.get("bound_at"),
        "full_name": profile.get("full_name"),
        "username": profile.get("username"),
        "paid": paid,
        "paid_until": paid_until,
        "days_left": _days_left(paid_until),
        "workout_days": workout_days,
        "workout_count": len(workout_days),
    }


@app.get("/admin/referrals/trainers/{trainer_id}/clients/{user_id}/plan")
def trainer_client_plan(trainer_id: str, user_id: int, request: Request, date: str, kind: str = "plan"):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    if kind not in {"plan", "meals"}:
        raise HTTPException(status_code=400, detail="kind must be 'plan' or 'meals'")
    _authorize_trainer(request, trainer_id)
    client = get_user_trainer(int(user_id))
    if not client or client["trainer_id"] != trainer_id:
        raise HTTPException(status_code=404, detail="client not found")
    return {"text": _read_note(int(user_id), date, kind)}


@app.post("/admin/referrals/trainers/{trainer_id}/clients/{user_id}/plan")
def trainer_client_plan_update(trainer_id: str, user_id: int, payload: dict, request: Request):
    if not trainer_id:
        raise HTTPException(status_code=400, detail="trainer_id required")
    _authorize_trainer(request, trainer_id)
    date = (payload.get("date") or "").strip()
    kind = (payload.get("kind") or "plan").strip()
    text = payload.get("text") or ""
    if not date:
        raise HTTPException(status_code=400, detail="date required")
    if kind not in {"plan", "meals"}:
        raise HTTPException(status_code=400, detail="kind must be 'plan' or 'meals'")
    client = get_user_trainer(int(user_id))
    if not client or client["trainer_id"] != trainer_id:
        raise HTTPException(status_code=404, detail="client not found")
    _write_note(int(user_id), date, kind, text)
    return {"success": True}


def should_start_api() -> bool:
    return os.getenv("REFERRAL_API_ENABLE", "true").lower() in {"1", "true", "yes"}


def _authorize_trainer(request: Request | None, trainer_id: str) -> None:
    if not request:
        return
    token = (request.headers.get("X-Trainer-Token") or "").strip()
    if not token:
        return
    info = verify_trainer_token(token)
    if not info:
        raise HTTPException(status_code=401, detail="invalid trainer token")
    if info["trainer_id"] != trainer_id:
        raise HTTPException(status_code=403, detail="trainer mismatch")


@app.post("/admin/referrals/trainer/login")
def trainer_login(payload: TrainerLogin):
    info = verify_trainer_login(payload.login, payload.password)
    if not info:
        raise HTTPException(status_code=401, detail="invalid credentials")
    session = create_trainer_session(info["trainer_id"])
    return {
        "trainer_id": info["trainer_id"],
        "name": info.get("name") or "",
        "token": session["token"],
        "expires_at": session["expires_at"],
    }


@app.get("/admin/referrals/trainer/session")
def trainer_session(request: Request):
    token = (request.headers.get("X-Trainer-Token") or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing token")
    info = verify_trainer_token(token)
    if not info:
        raise HTTPException(status_code=401, detail="invalid token")
    trainer = get_trainer_by_id(info["trainer_id"])
    if not trainer:
        raise HTTPException(status_code=404, detail="trainer not found")
    return {"trainer_id": trainer["trainer_id"], "name": trainer["name"]}
