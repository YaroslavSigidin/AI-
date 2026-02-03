import os, json, re, datetime, urllib.request, urllib.error, asyncio
from typing import Any, Dict, List, Optional

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()          # DeepSeek key (Bearer)
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com").strip().rstrip("/")
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "deepseek-chat").strip()

API_BASE_URL = (os.getenv("API_BASE_URL") or "http://api:8000").strip().rstrip("/")

# MSK fixed offset (UTC+3)
MSK = datetime.timezone(datetime.timedelta(hours=3))

ALLOWED_KINDS = {"workouts", "meals", "plan"}

def _now_msk():
    return datetime.datetime.now(MSK)

def _strip_markdown(s: str) -> str:
    if not s:
        return ""
    # remove typical markdown/control chars that DeepSeek can output
    s = s.replace("*", "")
    s = s.replace("_", "")
    s = s.replace("`", "")
    s = s.replace("#", "")
    s = s.replace("~", "")
    s = s.replace(">", "")
    s = s.replace("[", "").replace("]", "")
    s = s.replace("{", "").replace("}", "")
    # kill weird multiple spaces and trailing
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _api_req(method: str, path: str, user_id: int, body: Optional[dict] = None, timeout: int = 10) -> dict:
    url = f"{API_BASE_URL}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-User-Id", str(user_id))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def _get_note(user_id: int, d: str, kind: str) -> str:
    try:
        j = _api_req("GET", f"/api/notes?d={d}&kind={kind}", user_id=user_id)
        return (j.get("text") or "").strip()
    except Exception:
        return ""

def _put_note(user_id: int, d: str, kind: str, text: str) -> None:
    _api_req("PUT", f"/api/notes?d={d}&kind={kind}", user_id=user_id, body={"text": text})

def _append_note(user_id: int, d: str, kind: str, chunk: str) -> None:
    cur = _get_note(user_id, d, kind)
    if not cur:
        _put_note(user_id, d, kind, chunk.strip())
        return
    merged = (cur.rstrip() + "\n\n" + chunk.strip()).strip()
    _put_note(user_id, d, kind, merged)

def _openai_chat(messages: list, temperature: float = 0.2, max_tokens: int = 600) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

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

    # Уменьшаем timeout до 12 секунд для ускорения ответа
    with urllib.request.urlopen(req, timeout=12) as r:
        j = json.loads(r.read().decode("utf-8"))
    content = (((j.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
    return content.strip()

def _extract_json(text: str) -> dict:
    text = text.strip()
    # First try strict json
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try find first {...} block
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("No JSON found")
    return json.loads(m.group(0))

def _generate_plan_fallback(user_id: int, user_text: str, today: str, context: Optional[str] = None) -> str:
    """Генерирует план тренировок через дополнительный запрос к ИИ, если основной запрос не вернул план"""
    try:
        # Получаем профиль пользователя для контекста
        profile_context = ""
        if context:
            profile_context = f"\nКонтекст пользователя:\n{context}\n"
        
        # Формируем специальный промпт для генерации плана
        plan_prompt = (
            "Ты — фитнес-тренер. Пользователь просит составить план тренировок.\n"
            "ОБЯЗАТЕЛЬНО создай полноценный план тренировок с:\n"
            "- Конкретными упражнениями (например: жим лёжа, приседания, тяга штанги)\n"
            "- Количеством подходов и повторений (например: 4 подхода по 8-12 повторений)\n"
            "- Весом в килограммах для каждого упражнения (например: 80 кг)\n"
            "- Структурированным форматом с эмодзи\n\n"
            f"{profile_context}"
            "ВАЖНО: НЕ копируй запрос пользователя. Сразу создавай готовый план.\n"
            "Формат ответа: просто текст плана, без JSON, без форматирования markdown.\n"
            "Пример формата:\n"
            "🏋️ План тренировок на сегодня:\n\n"
            "1. Жим лёжа: 4 подхода по 8-12 повторений, 80 кг\n"
            "2. Приседания: 4 подхода по 10-12 повторений, 100 кг\n"
            "3. Тяга штанги в наклоне: 4 подхода по 8-10 повторений, 70 кг\n"
            "4. Жим гантелей сидя: 3 подхода по 10-12 повторений, 20 кг\n"
            "5. Подъём на бицепс: 3 подхода по 10-12 повторений, 15 кг\n\n"
            f"Запрос пользователя: {user_text}\n\n"
            "Создай план тренировок прямо сейчас:"
        )
        
        # Вызываем ИИ для генерации плана
        messages = [
            {"role": "system", "content": "Ты профессиональный фитнес-тренер. Создавай конкретные, практичные планы тренировок с указанием весов и подходов."},
            {"role": "user", "content": plan_prompt}
        ]
        
        generated_plan = _openai_chat(messages, temperature=0.3, max_tokens=800)
        
        # Очищаем от markdown и форматирования
        plan_text = _strip_markdown(generated_plan).strip()
        
        # Если план слишком короткий или похож на запрос пользователя, создаем базовый план
        if len(plan_text) < 50 or user_text.lower() in plan_text.lower():
            # Создаем базовый план как fallback
            plan_text = (
                "🏋️ План тренировок на сегодня:\n\n"
                "1. Жим лёжа: 4 подхода по 8-12 повторений, 80 кг\n"
                "2. Приседания со штангой: 4 подхода по 10-12 повторений, 100 кг\n"
                "3. Тяга штанги в наклоне: 4 подхода по 8-10 повторений, 70 кг\n"
                "4. Жим гантелей сидя: 3 подхода по 10-12 повторений, 20 кг\n"
                "5. Подъём штанги на бицепс: 3 подхода по 10-12 повторений, 15 кг\n"
                "6. Разгибания на трицепс: 3 подхода по 12-15 повторений, 10 кг\n\n"
                "💪 Отдых между подходами: 60-90 секунд\n"
                "🔥 Разминка перед тренировкой обязательна!"
            )
        
        return plan_text
    except Exception as e:
        # В случае ошибки возвращаем базовый план
        import logging
        logging.warning(f"Failed to generate plan via fallback: {e}")
        return (
            "🏋️ План тренировок на сегодня:\n\n"
            "1. Жим лёжа: 4 подхода по 8-12 повторений, 80 кг\n"
            "2. Приседания со штангой: 4 подхода по 10-12 повторений, 100 кг\n"
            "3. Тяга штанги в наклоне: 4 подхода по 8-10 повторений, 70 кг\n"
            "4. Жим гантелей сидя: 3 подхода по 10-12 повторений, 20 кг\n"
            "5. Подъём штанги на бицепс: 3 подхода по 10-12 повторений, 15 кг\n\n"
            "💪 Отдых между подходами: 60-90 секунд"
        )

def _kind_from_mode(mode_hint: Optional[str]) -> Optional[str]:
    if mode_hint == "sets":
        return "workouts"
    if mode_hint == "meals":
        return "meals"
    if mode_hint == "plan":
        return "plan"
    return None

def _truncate(s: str, limit: int = 1800) -> str:
    s = (s or "").strip()
    if len(s) <= limit:
        return s
    return s[-limit:]

def _detect_kind_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    if not t:
        return None
    plan_keywords = ("план", "состав", "создай", "созда", "распиши", "распис")
    meal_keywords = ("завтрак", "обед", "ужин", "перекус", "ел", "съел", "поел",
                     "калори", "белк", "жир", "углев", "еда", "питани", "рацион", "меню")
    workout_keywords = ("тренир", "упражнен", "подход", "повтор", "кг", "штанг", "гантел",
                        "жим", "присед", "тяга", "бицепс", "трицепс", "плеч", "спин", "ног")
    if any(k in t for k in plan_keywords):
        return "plan"
    if any(k in t for k in meal_keywords):
        return "meals"
    if any(k in t for k in workout_keywords):
        return "workouts"
    return None

def _is_plan_request(text: str) -> bool:
    return _detect_kind_from_text(text) == "plan"

def _build_system_prompt() -> str:
    return (
        "Ты — ИИ-ассистент для дневника тренировок/питания/плана.\n"
        "ВАЖНО: ты пишешь в Telegram.\n"
        "Запрещено использовать Markdown/разметку и спецсимволы форматирования.\n"
        "НЕ используй: звездочки, подчеркивания, решетки, обратные кавычки, списки со звездочками, заголовки с ###.\n"
        "Пиши простым текстом, короткими абзацами, с уместными смайликами.\n"
        "\n"
        "КРИТИЧЕСКИ ВАЖНО: НИКОГДА не копируй запрос пользователя в ответ. "
        "Если пользователь просит 'составь план' — сразу формируй готовый план, НЕ повторяй слова 'составь план'.\n"
        "\n"
        "ОБЯЗАТЕЛЬНО для планов тренировок:\n"
        "- ВСЕГДА указывай вес в килограммах (кг) для каждого упражнения с весом\n"
        "- Формат: 'Название упражнения: 4 подхода по 8-12 повторений, 80 кг'\n"
        "- Или короткий: 'Название упражнения: 4х8-12 80кг'\n"
        "- Или с прогрессией: 'Название: 1 подход 60кг, 2 подход 80кг, 3 подход 100кг'\n"
        "- КРИТИЧЕСКИ ВАЖНО: БЕЗ веса план бесполезен - всегда указывай конкретный вес в кг!\n"
        "- Для упражнений с весом тела (подтягивания, планка, пресс) - можно не указывать вес\n"
        "\n"
        "Ты ВСЕГДА отвечаешь ТОЛЬКО одним JSON-объектом.\n"
        "Формат JSON:\n"
        "{\n"
        '  "reply": "строка ответа пользователю",\n'
        '  "writes": [\n'
        '     {"d":"YYYY-MM-DD","kind":"workouts|meals|plan","mode":"append|replace","text":"что записать"}\n'
        "  ]\n"
        "}\n"
        "\n"
        "КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА КЛАССИФИКАЦИИ:\n"
        "\n"
        "1. ОПРЕДЕЛЕНИЕ ТИПА ЗАПРОСА:\n"
        "   — ТРЕНИРОВКА (kind='workouts'): если упоминаются упражнения, подходы, повторения, вес (кг), "
        "названия упражнений (жим, присед, тяга, бицепс, трицепс и т.д.), или частичные записи типа '3х10 60кг'.\n"
        "   — ПИТАНИЕ (kind='meals'): если упоминаются приемы пищи (завтрак, обед, ужин, перекус), "
        "продукты, калории, или действия 'ел', 'съел', 'поел'.\n"
        "   — ПЛАН (kind='plan'): если пользователь ПРОСИТ составить/создать/расписать план тренировок или питания.\n"
        "\n"
        "2. ПРАВИЛА ЗАПИСИ:\n"
        "   — Если mode_hint='sets' (тренировки): ОБЯЗАТЕЛЬНО записывай в kind='workouts', используй mode='append'.\n"
        "   — Если mode_hint='meals' (питание): ОБЯЗАТЕЛЬНО записывай в kind='meals', используй mode='append'.\n"
        "   — Если mode_hint='plan' (план): ОБЯЗАТЕЛЬНО записывай в kind='plan', используй mode='replace'.\n"
        "   — Если mode_hint НЕ задан, но пользователь ЯВНО просит записать/добавить/обновить — определи тип по контексту и запиши.\n"
        "\n"
        "3. ЧАСТИЧНЫЕ ЗАПИСИ ТРЕНИРОВОК:\n"
        "   — Если пользователь пишет короткие записи типа '3х10 60кг', 'жим 80кг', 'бицепс 4 подхода' — "
        "это ВСЕГДА тренировка (kind='workouts'), даже если запись неполная.\n"
        "   — Всегда используй mode='append' для тренировок, чтобы не потерять предыдущие записи.\n"
        "\n"
        "4. ЗАПРОСЫ НА ПЛАН:\n"
        "   — Если пользователь просит 'составь план', 'создай план тренировок', 'распиши питание на сегодня' — "
        "это ВСЕГДА kind='plan', используй mode='replace'.\n"
        "   — В ответе на запрос плана создавай структурированный, понятный план с эмодзи.\n"
        "   — КРИТИЧЕСКИ ВАЖНО: при запросе плана тренировок ОБЯЗАТЕЛЬНО создавай полноценный план с конкретными "
        "упражнениями, подходами, повторениями и весом. НЕ копируй запрос пользователя, НЕ пиши просто 'План создан'.\n"
        "   — Если пользователь просит 'составь план тренировок' — создай план с 5-7 упражнениями, "
        "каждое с указанием подходов, повторений и веса в кг.\n"
        "   — КРИТИЧЕСКИ ВАЖНО: при запросе плана тренировок ОБЯЗАТЕЛЬНО создавай полноценный план с конкретными "
        "упражнениями, подходами, повторениями и весом. НЕ копируй запрос пользователя, НЕ пиши просто 'План создан'.\n"
        "   — Если пользователь просит 'составь план тренировок' — создай план с 5-7 упражнениями, "
        "каждое с указанием подходов, повторений и веса в кг.\n"
        "\n"
        "5. КОНФЛИКТЫ И ПРИОРИТЕТЫ:\n"
        "   — Если mode_hint задан, но пользователь явно просит другой тип (например, mode_hint='meals', "
        "но пишет 'жим 80кг') — ПРИОРИТЕТ у явного запроса пользователя, используй правильный kind.\n"
        "   — Если пользователь просит 'составить план тренировок' — это kind='plan', НЕ 'workouts'.\n"
        "\n"
        "Стиль записей в дневник:\n"
        "— Только понятный текст.\n"
        "— Строки вида: '🍽️ Завтрак: ...', '🏋️ Жим лёжа: 4х8 80кг', '🗓️ План тренировок на сегодня: ...'\n"
        "— Аккуратные переносы строк, без таблиц и без форматирования.\n"
        "— Для тренировок: формат '🏋️ Название упражнения: подходы х повторения вес'\n"
    )

def _build_user_prompt(user_text: str, mode_hint: Optional[str], today: str, now_str: str,
                       workouts: str, meals: str, plan: str, context: Optional[str] = None,
                       intent_classification: Optional[str] = None) -> str:
    context_part = f"\nКонтекст пользователя:\n{context}\n\n" if context else ""
    
    # Добавляем информацию о классификации намерения
    intent_info = ""
    if intent_classification:
        intent_info = f"\n⚠️ КЛАССИФИКАЦИЯ НАМЕРЕНИЯ: {intent_classification}\n"
        intent_info += "Используй эту информацию для правильного определения kind в writes.\n"
    
    mode_hint_info = f"mode_hint: {mode_hint or 'none'}"
    if mode_hint:
        mode_hint_info += f" ({'тренировки' if mode_hint == 'sets' else 'питание' if mode_hint == 'meals' else 'план'})"
    
    return (
        f"Текущее время (МСК): {now_str}\n"
        f"Сегодня: {today}\n"
        f"{mode_hint_info}\n"
        f"{intent_info}"
        f"{context_part}"
        "Текущие заметки за выбранный день:\n"
        f"Тренировки:\n{workouts or '(пусто)'}\n\n"
        f"Питание:\n{meals or '(пусто)'}\n\n"
        f"План:\n{plan or '(пусто)'}\n\n"
        "Сообщение пользователя:\n"
        f"{user_text}\n\n"
        "ИНСТРУКЦИИ:\n"
        "1. Проанализируй сообщение пользователя и определи тип запроса:\n"
        "   — ТРЕНИРОВКА: если есть упражнения, подходы, повторения, вес\n"
        "   — ПИТАНИЕ: если есть приемы пищи, продукты, еда\n"
        "   — ПЛАН: если пользователь ПРОСИТ составить/создать план\n"
        "\n"
        "2. Если mode_hint задан, но он противоречит явному запросу пользователя — "
        "используй тип из запроса пользователя (приоритет у пользователя).\n"
        "\n"
        "3. Запиши в правильный kind:\n"
        "   — kind='workouts' для тренировок (mode='append')\n"
        "   — kind='meals' для питания (mode='append')\n"
        "   — kind='plan' для планов (mode='replace')\n"
        "\n"
        "4. КРИТИЧЕСКИ ВАЖНО для планов:\n"
        "   — Если пользователь просит план тренировок, ОБЯЗАТЕЛЬНО создавай полноценный план в writes.\n"
        "   — План должен содержать конкретные упражнения с подходами, повторениями и весом.\n"
        "   — НЕ сохраняй запрос пользователя как план. НЕ пиши просто 'План создан' без самого плана.\n"
        "   — Если writes пустой при запросе плана — это ОШИБКА. Всегда создавай план в writes.\n"
        "\n"
        "5. Если это обычный разговор без запроса на запись — просто ответь, writes оставь пустым.\n"
        "\n"
        "Верни JSON строго по формату."
    )

async def handle(user_id: int, text: str, mode_hint: Optional[str] = None, force_mode_hint: bool = False) -> Dict[str, Any]:
    user_text = (text or "").strip()
    now = _now_msk()
    today = now.date().isoformat()
    now_str = now.strftime("%Y-%m-%d %H:%M")

    # Pull current notes (context)
    workouts = _truncate(_get_note(user_id, today, "workouts"))
    meals = _truncate(_get_note(user_id, today, "meals"))
    plan = _truncate(_get_note(user_id, today, "plan"))
    
    # Получаем контекст пользователя (предпочтения, цели)
    try:
        from user_settings import get_context_summary, track_activity
        context = get_context_summary(user_id)
        track_activity(user_id, "message")
    except ImportError:
        context = None

    # КЛАССИФИКАЦИЯ НАМЕРЕНИЯ - ключевое улучшение!
    # ВАЖНО: для системных вызовов (например, генерация плана) можно принудительно зафиксировать mode_hint.
    if not force_mode_hint:
        try:
            from intent_classifier import classify_intent, get_mode_hint, should_append_to_existing
            intent, confidence = classify_intent(user_text, mode_hint)
            
            # Если классификатор уверен, используем его результат вместо mode_hint
            if confidence >= 0.5:
                suggested_mode = get_mode_hint(user_text, mode_hint)
                if suggested_mode and suggested_mode != mode_hint:
                    # Логируем изменение для отладки
                    import logging
                    logging.info(f"🔄 Intent classifier: '{user_text[:50]}' -> intent={intent}, confidence={confidence:.2f}, "
                               f"mode_hint changed: {mode_hint} -> {suggested_mode}")
                    mode_hint = suggested_mode
        except ImportError:
            intent = None
            confidence = 0.0
    else:
        intent = None
        confidence = 0.0

    sys_prompt = _build_system_prompt()
    intent_classification = f"{intent} (confidence: {confidence:.2f})" if intent else None
    user_prompt = _build_user_prompt(user_text, mode_hint, today, now_str, workouts, meals, plan, context, intent_classification)

    # Call DeepSeek in a thread to not block polling
    def _call():
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return _openai_chat(messages, temperature=0.15, max_tokens=450)

    raw = ""
    try:
        raw = await asyncio.to_thread(_call)
        data = _extract_json(raw)
        
        # Проверяем, что data содержит корректный JSON
        if not isinstance(data, dict):
            raise ValueError("Invalid response format")
        if "reply" not in data and "writes" not in data:
            raise ValueError("Missing required fields in response")
            
    except Exception as e1:
        # second strict retry
        try:
            def _call2():
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt + "\n\nСТРОГО: верни только JSON без любого другого текста. Формат: {\"reply\": \"текст\", \"writes\": []}"},
                ]
                return _openai_chat(messages, temperature=0.0, max_tokens=400)
            raw = await asyncio.to_thread(_call2)
            data = _extract_json(raw)
            
            # Проверяем повторно после retry
            if not isinstance(data, dict):
                raise ValueError("Invalid response format after retry")
            if "reply" not in data and "writes" not in data:
                raise ValueError("Missing required fields after retry")
                
        except Exception as e2:
            # Если оба запроса провалились, создаем минимальный ответ
            import logging
            logging.error(f"Failed to get valid response from AI: {e1}, {e2}")
            
            # Пытаемся извлечь хотя бы reply из raw, если он есть
            if raw:
                try:
                    # Пробуем найти JSON в тексте
                    import re
                    json_match = re.search(r'\{[^{}]*"reply"[^{}]*\}', raw, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(0))
                    else:
                        # Если JSON не найден, создаем ответ из текста
                        data = {"reply": _strip_markdown(raw)[:200], "writes": []}
                except:
                    data = {"reply": "✅ План создан", "writes": []}
            else:
                data = {"reply": "✅ План создан", "writes": []}

    reply = _strip_markdown(str(data.get("reply") or "")).strip()
    writes = data.get("writes") or []
    if not isinstance(writes, list):
        writes = []

    detected_kind = _detect_kind_from_text(user_text)
    is_plan_request = _is_plan_request(user_text)

    # If mode_hint is set but model forgot to write — force one write (avoid misclassifying to plan)
    forced_kind = _kind_from_mode(mode_hint)
    if len(writes) == 0:
        if detected_kind and detected_kind != "plan":
            forced_kind = detected_kind
        elif forced_kind == "plan" and not is_plan_request:
            forced_kind = None
        if forced_kind:
            if forced_kind == "meals":
                chunk = f"🍽️ Запись: {_strip_markdown(user_text)}"
                mode = "append"
            elif forced_kind == "workouts":
                chunk = f"🏋️ Подходы/вес: {_strip_markdown(user_text)}"
                mode = "append"
            else:
                # plan only when user действительно просит план
                chunk = f"🗓️ План: {_strip_markdown(user_text)}"
                mode = "replace"
            writes = [{"d": today, "kind": forced_kind, "mode": mode, "text": chunk}]

    # If user requested a plan, ensure we have a real plan and reply with it
    if is_plan_request:
        plan_write = next((w for w in writes if str(w.get("kind")) == "plan"), None)
        plan_text = _strip_markdown(str(plan_write.get("text") if plan_write else "")).strip()
        if not plan_text or len(plan_text) < 50:
            plan_text = _generate_plan_fallback(user_id, user_text, today)
        writes = [{"d": today, "kind": "plan", "mode": "replace", "text": plan_text}]
        if not reply or "план создан" in reply.lower() or len(reply) < 30:
            reply = plan_text

    # Apply writes
    for w in writes:
        try:
            d = str(w.get("d") or today).strip()
            kind = str(w.get("kind") or "").strip()
            mode = str(w.get("mode") or "append").strip()
            txt = _strip_markdown(str(w.get("text") or "")).strip()

            if kind not in ALLOWED_KINDS or not txt:
                continue

            if mode == "replace":
                _put_note(user_id, d, kind, txt)
            else:
                _append_note(user_id, d, kind, txt)
            
        except Exception:
            # do not crash bot
            continue

    if not reply:
        reply = "Ок."

    return {"reply": reply, "writes": writes}
