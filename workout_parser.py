"""
Умный парсер планов тренировок с использованием ИИ
Анализирует текст плана и извлекает структурированные данные: упражнения, подходы, веса, повторения, RPE, отдых
"""
import os
import json
import re
from typing import Dict, List, Optional

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com").strip().rstrip("/")
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "deepseek-chat").strip()


def _openai_chat(messages: list, temperature: float = 0.1, max_tokens: int = 800) -> str:
    """Вызов DeepSeek API для парсинга плана"""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    import urllib.request
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
        with urllib.request.urlopen(req, timeout=8) as r:  # Короткий таймаут с fallback
            j = json.loads(r.read().decode("utf-8"))
        content = (((j.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
        return content.strip()
    except Exception as e:
        # Если таймаут или другая ошибка - возвращаем пустую строку для fallback
        import logging
        logging.warning(f"AI parser timeout/error: {e}")
        raise  # Пробрасываем исключение для fallback


def parse_workout_plan_with_ai(plan_text: str) -> List[Dict]:
    """
    Парсит план тренировок с помощью ИИ и возвращает структурированные данные.
    
    ВАЖНО: Эта функция отключена по умолчанию из-за таймаутов.
    Используйте только если USE_AI_PARSER=true в .env
    
    Возвращает список упражнений, каждое с:
    - name: название упражнения
    - sets: список подходов, каждый с:
        - number: номер подхода (1, 2, 3...)
        - reps: повторения (например, "8-10", "12", "до отказа")
        - weight_kg: вес в кг (число или None)
        - rpe: RPE (Rate of Perceived Exertion, например, "7-8", "≤8")
        - rest_sec: отдых в секундах (число или None)
    """
    if not plan_text or not plan_text.strip():
        return []
    
    # ИИ-парсер включен по умолчанию для умной классификации
    use_ai = os.getenv("USE_AI_PARSER", "true").lower() == "true"
    if not use_ai:
        # Если отключен - сразу используем fallback
        return _fallback_parse(plan_text)
    
    # Если план очень короткий или простой - используем fallback сразу
    if len(plan_text.strip()) < 50:
        return _fallback_parse(plan_text)
    
    # Промпт для ИИ
    system_prompt = """Ты — эксперт по парсингу планов тренировок. Твоя задача — извлечь из текста плана все упражнения с их параметрами.

Ты должен вернуть ТОЛЬКО валидный JSON без дополнительного текста, комментариев или объяснений.

Формат ответа:
{
  "exercises": [
    {
      "name": "Название упражнения",
      "sets": [
        {
          "number": 1,
          "reps": "8-10",
          "weight_kg": 80,
          "rpe": "7-8",
          "rest_sec": 90
        },
        {
          "number": 2,
          "reps": "8-10",
          "weight_kg": 80,
          "rpe": "7-8",
          "rest_sec": 90
        }
      ]
    }
  ]
}

ПРАВИЛА:
1. Извлекай ТОЛЬКО упражнения из основной части (игнорируй разминку, заминку, общие советы).
2. КРИТИЧЕСКИ ВАЖНО: Всегда пытайся извлечь вес, даже если он записан некорректно.
3. Форматы веса: "60кг", "60 кг", "60kg", "60", "рабочий вес 60", "с весом 60кг" — все извлекай.
4. Если вес указан для всех подходов одинаково "4х8-10 80кг" — создай 4 подхода с weight_kg=80.
5. Если вес указан отдельно для каждого подхода "1 подход 60кг, 2 подход 80кг" — создай разные подходы.
6. Если вес не указан явно, но есть упоминание в тексте — попробуй извлечь его из контекста.
7. Для упражнений без веса (подтягивания, планка, пресс) — используй weight_kg=null.
8. Если повторения указаны как диапазон "8-10" или "10-12" — сохраняй как строку "8-10".
9. Если RPE указан как "RPE 7-8" или "≤8" — извлекай.
10. Если отдых указан как "90 сек", "2 мин" — конвертируй в секунды (90, 120).
11. Названия упражнений могут быть в скобках: "Бабочка (сведение рук)" — извлекай полностью.
12. НЕ придумывай данные, которых нет в тексте, но МАКСИМАЛЬНО старайся найти вес.

ВАЖНО: Верни ТОЛЬКО JSON, без markdown, без объяснений, без дополнительного текста."""

    user_prompt = f"""Проанализируй этот план тренировок и извлеки все упражнения с подходами, весами, повторениями, RPE и отдыхом:

{plan_text}

Верни структурированный JSON с упражнениями."""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Уменьшаем таймаут и токены для ускорения
        response = _openai_chat(messages, temperature=0.1, max_tokens=600)
        
        # Извлекаем JSON из ответа (на случай если ИИ добавил markdown)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group(0)
        
        data = json.loads(response)
        
        # Валидация и нормализация данных
        exercises = data.get("exercises", [])
        result = []
        
        for ex in exercises:
            if not ex.get("name"):
                continue
            
            sets = []
            for set_data in ex.get("sets", []):
                # Нормализуем данные подхода
                set_num = set_data.get("number", 1)
                reps = str(set_data.get("reps", "")).strip()
                weight_kg = set_data.get("weight_kg")
                rpe = str(set_data.get("rpe", "")).strip()
                rest_sec = set_data.get("rest_sec")
                
                # Конвертируем weight_kg в строку если это число
                if weight_kg is not None:
                    try:
                        weight_kg = str(int(float(weight_kg)))
                    except (ValueError, TypeError):
                        weight_kg = None
                
                # Конвертируем rest_sec в число если это строка
                if rest_sec is not None and isinstance(rest_sec, str):
                    # Пытаемся извлечь число из строки типа "90 сек", "2 мин"
                    rest_match = re.search(r'(\d+)', rest_sec)
                    if rest_match:
                        rest_sec = int(rest_match.group(1))
                    else:
                        rest_sec = None
                
                sets.append({
                    "number": int(set_num),
                    "reps": reps,
                    "weight_kg": weight_kg,
                    "rpe": rpe,
                    "rest_sec": rest_sec
                })
            
            # Если нет подходов, создаем один пустой
            if not sets:
                sets = [{
                    "number": 1,
                    "reps": "",
                    "weight_kg": None,
                    "rpe": "",
                    "rest_sec": None
                }]
            
            result.append({
                "name": ex["name"].strip(),
                "sets": sets
            })
        
        return result
        
    except json.JSONDecodeError as e:
        # Если ИИ вернул невалидный JSON, используем fallback парсер
        return _fallback_parse(plan_text)
    except Exception as e:
        # В случае любой ошибки используем fallback
        import logging
        logging.error(f"AI parsing error: {e}")
        return _fallback_parse(plan_text)


def _fallback_parse(plan_text: str) -> List[Dict]:
    """
    Простой fallback парсер на случай если ИИ не сработал.
    Использует базовые регулярные выражения.
    """
    if not plan_text:
        return []
    
    exercises = []
    lines = plan_text.split('\n')
    current_exercise = None
    skip_sections = ['разминка', 'разогрев', 'заминка', 'основная часть', 'warm-up', 'cool-down', 'правило прогрессии']
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Убираем эмодзи и маркеры
        line_clean = re.sub(r'^[🗓️📝•\-\*🏋️🍽️🔥💪]\s*', '', line)
        line_clean = re.sub(r'^\d+[\.\)]\s*', '', line_clean).strip()
        
        line_lower = line_clean.lower()
        if any(section in line_lower for section in skip_sections):
            if current_exercise and current_exercise['sets']:
                exercises.append(current_exercise)
                current_exercise = None
            continue
        
        # Формат "Упражнение: 4х8-10 80кг"
        colon_match = re.match(r'^(.+?):\s*(.+)', line_clean)
        if colon_match:
            ex_name = colon_match.group(1).strip()
            sets_info = colon_match.group(2).strip()
            
            # Парсим "4х8-10 80кг"
            x_match = re.search(r'(\d+)\s*[хx]\s*([\d\-до\s]+)', sets_info, re.IGNORECASE)
            weight_match = re.search(r'(\d+)\s*кг', sets_info, re.IGNORECASE)
            
            if x_match:
                num_sets = int(x_match.group(1))
                reps = x_match.group(2).strip()
                weight_kg = weight_match.group(1) if weight_match else None
                
                sets = []
                for i in range(1, num_sets + 1):
                    sets.append({
                        "number": i,
                        "reps": reps,
                        "weight_kg": weight_kg,
                        "rpe": "",
                        "rest_sec": None
                    })
                
                if current_exercise and current_exercise['sets']:
                    exercises.append(current_exercise)
                
                current_exercise = {
                    "name": ex_name,
                    "sets": sets
                }
                continue
        
        # Формат "1 подход - 60кг" или "1 подход: 8-10 повторений 60кг"
        set_match = re.search(r'(\d+)\s*подход[а-я]*\s*[:\-]\s*(.+)', line_clean, re.IGNORECASE)
        if set_match:
            if current_exercise is None:
                current_exercise = {"name": "Упражнение", "sets": []}
            
            set_num = int(set_match.group(1))
            set_info = set_match.group(2).strip()
            
            weight_match = re.search(r'(\d+)\s*кг', set_info, re.IGNORECASE)
            reps_match = re.search(r'([\d\-до]+)\s*повторени[яй]?', set_info, re.IGNORECASE)
            
            weight_kg = weight_match.group(1) if weight_match else None
            reps = reps_match.group(1) if reps_match else ""
            
            current_exercise['sets'].append({
                "number": set_num,
                "reps": reps,
                "weight_kg": weight_kg,
                "rpe": "",
                "rest_sec": None
            })
            continue
        
        # Просто название упражнения
        if not ':' in line_clean and not 'подход' in line_lower:
            if current_exercise and current_exercise['sets']:
                exercises.append(current_exercise)
            
            current_exercise = {
                "name": line_clean,
                "sets": []
            }
    
    if current_exercise:
        if not current_exercise['sets']:
            current_exercise['sets'] = [{
                "number": 1,
                "reps": "",
                "weight_kg": None,
                "rpe": "",
                "rest_sec": None
            }]
        exercises.append(current_exercise)
    
    return exercises
