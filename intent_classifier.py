"""
Гениальная система классификации намерений пользователя
Определяет тип запроса с высокой точностью
"""

import re
from typing import Optional, Dict, Tuple
from datetime import datetime

# Ключевые слова и паттерны для классификации
WORKOUT_KEYWORDS = {
    # Упражнения
    "жим", "присед", "тяга", "подтягивание", "отжимание", "планка", "бурпи",
    "гантел", "штанга", "гиря", "тренажер", "кроссовер", "блок", "скамья",
    # Действия тренировки
    "подход", "повтор", "повторение", "раз", "кг", "килограмм", "вес",
    "сделал", "выполнил", "закончил", "завершил", "тренировка", "тренировался",
    "занятие", "зал", "спортзал", "фитнес", "качалка",
    # Части тренировки
    "разминка", "заминка", "кардио", "силовая", "растяжка",
    # Конкретные упражнения
    "бицепс", "трицепс", "грудь", "спина", "ноги", "плечи", "пресс",
    "квадрицепс", "икры", "ягодицы", "дельты", "трапеция",
}

NUTRITION_KEYWORDS = {
    # Приемы пищи
    "завтрак", "обед", "ужин", "перекус", "полдник", "ланч",
    # Действия
    "ел", "съел", "поел", "попил", "выпил", "съела", "поела",
    "питание", "еда", "кушал", "покушала",
    # Еда
    "калори", "белок", "углевод", "жир", "протеин", "ккал",
    "грамм", "гр", "мл", "литр", "порция", "тарелка", "чашка",
    # Продукты (основные)
    "курица", "рыба", "мясо", "овощ", "фрукт", "каша", "рис", "гречка",
    "овсянка", "творог", "йогурт", "молоко", "яйцо", "хлеб",
}

PLAN_KEYWORDS = {
    # Планирование
    "план", "планируй", "составь", "распиши", "расписание", "программа",
    "на сегодня", "на завтра", "на неделю", "на месяц",
    "тренировочный план", "план тренировок", "план питания",
    "меню", "рацион", "диета",
    # Запросы на создание
    "создай", "придумай", "подбери", "рекомендуй", "предложи",
}

# Паттерны для частичных записей тренировок
PARTIAL_WORKOUT_PATTERNS = [
    r"\d+\s*(кг|kg|килограмм)",  # "20 кг", "60kg"
    r"\d+\s*(раз|повтор|повторение)",  # "10 раз", "12 повторений"
    r"\d+\s*х\s*\d+",  # "3х10", "4х8"
    r"\d+\s*подход",  # "3 подхода"
    r"подход\s*\d+",  # "подход 1"
]

# Паттерны для запросов на создание плана
PLAN_REQUEST_PATTERNS = [
    r"составь.*план",
    r"создай.*план",
    r"распиши.*план",
    r"план.*на\s+(сегодня|завтра|неделю)",
    r"тренировк[ау].*на\s+(сегодня|завтра)",
    r"питани[ея].*на\s+(сегодня|завтра)",
]


def normalize_text(text: str) -> str:
    """Нормализует текст для анализа"""
    text = text.lower().strip()
    # Убираем лишние пробелы
    text = re.sub(r'\s+', ' ', text)
    return text


def count_keywords(text: str, keywords: set) -> int:
    """Подсчитывает количество совпадений ключевых слов"""
    text = normalize_text(text)
    count = 0
    for keyword in keywords:
        if keyword in text:
            count += 1
    return count


def check_patterns(text: str, patterns: list) -> bool:
    """Проверяет наличие паттернов в тексте"""
    text = normalize_text(text)
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def classify_intent(text: str, current_mode: Optional[str] = None) -> Tuple[str, float]:
    """
    Классифицирует намерение пользователя
    
    Returns:
        (intent, confidence): intent может быть 'workout', 'nutrition', 'plan', 'unknown'
        confidence от 0.0 до 1.0
    """
    if not text or not text.strip():
        return ("unknown", 0.0)
    
    normalized = normalize_text(text)
    
    # Подсчитываем совпадения для каждого типа
    workout_score = count_keywords(normalized, WORKOUT_KEYWORDS)
    nutrition_score = count_keywords(normalized, NUTRITION_KEYWORDS)
    plan_score = count_keywords(normalized, PLAN_KEYWORDS)
    
    # Проверяем паттерны для частичных записей тренировок
    if check_patterns(normalized, PARTIAL_WORKOUT_PATTERNS):
        workout_score += 3  # Высокий приоритет
    
    # Проверяем паттерны для запросов на план
    if check_patterns(normalized, PLAN_REQUEST_PATTERNS):
        plan_score += 3  # Высокий приоритет
    
    # Специальные правила для явных запросов
    if any(phrase in normalized for phrase in ["составь план", "создай план", "распиши план"]):
        plan_score += 5
    
    if any(phrase in normalized for phrase in ["тренировк", "упражнен", "подход", "повтор"]):
        workout_score += 2
    
    if any(phrase in normalized for phrase in ["ел", "съел", "поел", "питание", "завтрак", "обед", "ужин"]):
        nutrition_score += 2
    
    # Если есть явное указание на режим в тексте
    if "тренировк" in normalized or "упражнен" in normalized:
        workout_score += 3
    if "питани" in normalized or "еда" in normalized:
        nutrition_score += 3
    if "план" in normalized and ("составь" in normalized or "создай" in normalized):
        plan_score += 5
    
    # Вычисляем уверенность
    total_score = workout_score + nutrition_score + plan_score
    if total_score == 0:
        return ("unknown", 0.0)
    
    # Определяем победителя
    max_score = max(workout_score, nutrition_score, plan_score)
    
    if workout_score == max_score and workout_score > 0:
        confidence = workout_score / max(total_score, 1)
        return ("workout", min(confidence, 1.0))
    elif nutrition_score == max_score and nutrition_score > 0:
        confidence = nutrition_score / max(total_score, 1)
        return ("nutrition", min(confidence, 1.0))
    elif plan_score == max_score and plan_score > 0:
        confidence = plan_score / max(total_score, 1)
        return ("plan", min(confidence, 1.0))
    
    return ("unknown", 0.0)


def get_mode_hint(text: str, current_mode: Optional[str] = None) -> Optional[str]:
    """
    Определяет mode_hint для передачи в tracker_agent
    
    Returns:
        'sets' для тренировок, 'meals' для питания, 'plan' для планов, None если неопределенно
    """
    intent, confidence = classify_intent(text, current_mode)
    
    # Если уверенность низкая, используем текущий режим
    if confidence < 0.3 and current_mode:
        return current_mode
    
    # Преобразуем intent в mode_hint
    if intent == "workout":
        return "sets"
    elif intent == "nutrition":
        return "meals"
    elif intent == "plan":
        return "plan"
    
    # Если неопределенно, но есть текущий режим - используем его
    if current_mode:
        return current_mode
    
    return None


def is_partial_workout_record(text: str) -> bool:
    """Проверяет, является ли текст частичной записью тренировки"""
    normalized = normalize_text(text)
    
    # Проверяем паттерны частичных записей
    if check_patterns(normalized, PARTIAL_WORKOUT_PATTERNS):
        return True
    
    # Проверяем наличие чисел и единиц измерения
    if re.search(r"\d+\s*(кг|kg|раз|повтор|подход)", normalized):
        return True
    
    # Проверяем короткие записи типа "3х10 60кг"
    if re.search(r"\d+\s*х\s*\d+", normalized):
        return True
    
    return False


def should_append_to_existing(text: str, intent: str) -> bool:
    """
    Определяет, нужно ли добавлять к существующей записи или создавать новую
    
    Для тренировок: частичные записи всегда добавляются
    Для планов: обычно заменяются
    """
    if intent == "workout":
        return is_partial_workout_record(text)
    elif intent == "plan":
        return False  # Планы обычно заменяются
    elif intent == "nutrition":
        return True  # Питание обычно добавляется
    
    return True  # По умолчанию добавляем
