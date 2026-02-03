"""
Генератор мотивирующих сообщений для уведомлений
Использует AI для создания нешаблонных, контекстных сообщений
"""
import os
import json
import asyncio
import datetime
from typing import Optional, Dict, Any
import urllib.request
import urllib.error

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com").strip().rstrip("/")
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "deepseek-chat").strip()

API_BASE_URL = (os.getenv("API_BASE_URL") or "http://api:8000").strip().rstrip("/")

MSK = datetime.timezone(datetime.timedelta(hours=3))

def _now_msk():
    return datetime.datetime.now(MSK)

def _api_req(method: str, path: str, user_id: int, body: Optional[dict] = None, timeout: int = 20) -> dict:
    """Выполняет запрос к API"""
    url = f"{API_BASE_URL}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-User-Id", str(user_id))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except Exception:
        return {}

def _get_note(user_id: int, d: str, kind: str) -> str:
    """Получает заметку за день"""
    try:
        j = _api_req("GET", f"/api/notes?d={d}&kind={kind}", user_id=user_id)
        return (j.get("text") or "").strip()
    except Exception:
        return ""

def _get_user_context(user_id: int) -> str:
    """Получает контекст пользователя (цели, предпочтения, статистика)"""
    try:
        from user_settings import get_context_summary
        return get_context_summary(user_id) or ""
    except Exception:
        return ""

def _get_recent_activity(user_id: int, days: int = 7) -> Dict[str, Any]:
    """Получает активность пользователя за последние дни"""
    today = _now_msk().date()
    workouts_count = 0
    last_workout_date = None
    
    for i in range(days):
        date = today - datetime.timedelta(days=i)
        date_str = date.isoformat()
        workouts = _get_note(user_id, date_str, "workouts")
        if workouts:
            workouts_count += 1
            if last_workout_date is None:
                last_workout_date = date_str
    
    return {
        "workouts_count": workouts_count,
        "last_workout_date": last_workout_date,
        "days_checked": days
    }

def _openai_chat(messages: list, temperature: float = 0.8, max_tokens: int = 200) -> str:
    """Вызывает OpenAI API для генерации сообщения"""
    if not OPENAI_API_KEY:
        return None
    
    url = f"{OPENAI_BASE_URL}/v1/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8"))
        content = (((j.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
        return content.strip()
    except Exception:
        return None

async def generate_motivation_message(user_id: int) -> Optional[str]:
    """
    Генерирует мотивирующее сообщение для пользователя.
    Использует AI для создания нешаблонного, контекстного сообщения.
    """
    now = _now_msk()
    today = now.date().isoformat()
    hour = now.hour
    
    # Получаем контекст
    context = _get_user_context(user_id)
    activity = _get_recent_activity(user_id, days=7)
    today_workouts = _get_note(user_id, today, "workouts")
    today_meals = _get_note(user_id, today, "meals")
    
    # Определяем время суток и тему сообщения
    if 6 <= hour < 12:
        time_context = "утро"
        suggested_topics = ["планы на тренировку сегодня", "завтрак и питание", "энергия на день"]
    elif 12 <= hour < 18:
        time_context = "день"
        suggested_topics = ["тренировка сегодня", "обед и питание", "прогресс"]
    elif 18 <= hour < 22:
        time_context = "вечер"
        suggested_topics = ["тренировка сегодня", "ужин", "итоги дня"]
    else:
        time_context = "ночь"
        suggested_topics = ["планы на завтра", "отдых и восстановление"]
    
    # Формируем промпт для AI
    system_prompt = """Ты — мотивирующий фитнес-тренер в Telegram-боте.
Твоя задача — мотивировать пользователя продолжать тренироваться и держать "ударный режим".

ВАЖНО:
- НЕ используй шаблонные фразы типа "иди на тренировку", "не сдавайся"
- Будь естественным, дружелюбным, но не навязчивым
- Используй контекст пользователя (его цели, активность)
- Задавай вопросы, которые мотивируют действовать
- Пиши коротко (1-2 предложения максимум)
- Используй эмодзи уместно (не перебор)
- НЕ используй markdown, звездочки, подчеркивания

Примеры ХОРОШИХ сообщений:
- "Вижу, что ты уже 3 дня подряд в ударе! 🔥 Что сегодня планируешь на тренировке?"
- "Утро началось? Как насчет заряда энергии через тренировку?"
- "Заметил, что ты пропустил пару дней. Может, сегодня вернемся в ритм?"

Примеры ПЛОХИХ сообщений (НЕ ДЕЛАЙ ТАК):
- "Иди на тренировку!"
- "Не сдавайся!"
- "Ты можешь это сделать!"
- "Сегодня день тренировки!"

Отвечай ТОЛЬКО текстом сообщения, без дополнительных пояснений."""

    # Формируем контекст для пользователя
    context_text = f"""Время суток: {time_context} ({hour}:00)
Сегодня: {today}

Контекст пользователя:
{context if context else "Новый пользователь"}

Активность за последние 7 дней:
- Тренировок: {activity['workouts_count']}
- Последняя тренировка: {activity['last_workout_date'] or 'нет'}

Сегодня:
- Тренировки: {'есть' if today_workouts else 'нет'}
- Питание: {'есть' if today_meals else 'нет'}

Возможные темы для сообщения: {', '.join(suggested_topics[:2])}"""

    user_prompt = f"""{context_text}

Сгенерируй мотивирующее сообщение для пользователя.
Сообщение должно:
1. Быть естественным и нешаблонным
2. Мотивировать к действию (тренировка, питание, прогресс)
3. Учитывать контекст (если есть активность - похвалить, если нет - мягко мотивировать)
4. Быть коротким (1-2 предложения)
5. Задавать вопрос или предлагать действие

Сообщение:"""

    def _call():
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return _openai_chat(messages, temperature=0.85, max_tokens=150)
    
    try:
        message = await asyncio.to_thread(_call)
        if message and len(message.strip()) > 10:
            # Очищаем от markdown и лишних символов
            message = message.replace("*", "").replace("_", "").replace("`", "")
            message = message.replace("#", "").replace("~", "").replace(">", "")
            message = message.strip()
            if message:
                return message
    except Exception:
        pass
    
    # Fallback - простые сообщения, если AI не сработал
    fallback_messages = [
        "Как дела с тренировками? Что сегодня по плану? 💪",
        "Вижу, что ты держишь ритм! Продолжаем в том же духе? 🔥",
        "Как настроение? Готов к тренировке сегодня?",
        "Что сегодня по питанию и тренировкам? 📝",
    ]
    
    import random
    return random.choice(fallback_messages)
