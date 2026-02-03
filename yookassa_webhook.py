"""
Webhook endpoint для YooKassa
Обрабатывает уведомления о платежах и автоматически активирует подписки
"""
import os
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

PAY_SUB_DAYS = int(os.getenv("PAY_SUB_DAYS", "30").strip())
PAYWALL_DB = os.getenv("PAYWALL_DB", "/root/ai_trainer_cursor/paywall.db")

def activate_paid(user_id: int, days: int = PAY_SUB_DAYS) -> int:
    """Активирует подписку для пользователя"""
    conn = sqlite3.connect(PAYWALL_DB, check_same_thread=False)
    try:
        # Создаем таблицу, если её нет
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            msg_count INTEGER NOT NULL DEFAULT 0,
            paid_until INTEGER NOT NULL DEFAULT 0,
            pending_payment_id TEXT DEFAULT NULL,
            pending_created INTEGER NOT NULL DEFAULT 0
        )
        """)
        conn.commit()
        
        paid_until = int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())
        conn.execute(
            "INSERT INTO users(user_id, msg_count, paid_until, pending_payment_id, pending_created) VALUES(?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET paid_until=excluded.paid_until, msg_count=0, pending_payment_id=NULL, pending_created=0",
            (user_id, 0, paid_until, None, 0)
        )
        conn.commit()
        return paid_until
    finally:
        conn.close()

@router.post("/yookassa/webhook")
async def yookassa_webhook(request: Request):
    """
    Webhook endpoint для обработки уведомлений от YooKassa
    
    YooKassa будет отправлять POST запросы на этот endpoint
    при изменении статуса платежа
    
    URL: https://sport-helper-robot.online/yookassa/webhook
    """
    try:
        # Получаем тело запроса
        body = await request.json()
        
        event_type = body.get("event")
        payment_data = body.get("object", {})
        
        # Обрабатываем только события успешных платежей
        if event_type != "payment.succeeded":
            return {"ok": True, "message": f"Ignored event: {event_type}"}
        
        # Получаем информацию о платеже
        payment_id = payment_data.get("id")
        status = payment_data.get("status", "").lower()
        metadata = payment_data.get("metadata", {})
        user_id_str = metadata.get("user_id")
        
        if not user_id_str:
            return {"ok": False, "error": "No user_id in metadata"}
        
        user_id = int(user_id_str)
        
        # Если платеж успешен, активируем подписку
        if status == "succeeded":
            paid_until = activate_paid(user_id, PAY_SUB_DAYS)
            try:
                from referrals import record_paid_event, mark_price_promo_used
                amount = float((payment_data.get("amount") or {}).get("value") or 0)
                if amount:
                    record_paid_event(user_id, amount)
                promo_code = (metadata.get("promo_code") or "").strip()
                if promo_code:
                    mark_price_promo_used(promo_code, user_id, int(time.time()))
            except Exception:
                pass
            return {
                "ok": True,
                "message": f"Subscription activated for user {user_id}",
                "paid_until": paid_until
            }
        
        return {"ok": True, "message": f"Payment {payment_id} status: {status}"}
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except Exception as e:
        # Логируем ошибку, но возвращаем 200, чтобы YooKassa не повторял запрос
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}
