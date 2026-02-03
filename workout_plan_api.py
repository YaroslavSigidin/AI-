"""
API endpoint для работы с планом тренировок на сегодня
Извлекает упражнения из плана и управляет состоянием выполнения
"""
import os
import sqlite3
import re
import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel

# Импорт tracker_agent для генерации плана
agent_handle = None
try:
    from tracker_agent import handle as agent_handle
except ImportError:
    try:
        import sys
        sys.path.insert(0, "/app")
        from tracker_agent import handle as agent_handle
    except ImportError:
        try:
            from app.tracker_agent import handle as agent_handle
        except ImportError:
            agent_handle = None

DB_PATH = (os.getenv("TRACKER_DB_PATH") or "/data/tracker.db").strip()
WORKOUT_STATE_DB = (os.getenv("WORKOUT_STATE_DB") or "/data/workout_state.db").strip()

router = APIRouter()

def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
    return conn

def _workout_state_db():
    """База данных для хранения состояния выполнения упражнений"""
    conn = sqlite3.connect(WORKOUT_STATE_DB, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workout_state (
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            exercise_name TEXT NOT NULL,
            set_number INTEGER NOT NULL,
            weight TEXT,
            reps TEXT,
            completed INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            updated_at TEXT,
            PRIMARY KEY (user_id, date, exercise_name, set_number)
        )
    """)
    # Мягкая миграция для старых БД без столбца reps
    cols = [row[1] for row in conn.execute("PRAGMA table_info(workout_state)").fetchall()]
    if "reps" not in cols:
        conn.execute("ALTER TABLE workout_state ADD COLUMN reps TEXT")
    conn.commit()
    return conn

def _need_user(x_user_id: str | None):
    uid = (x_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="Missing X-User-Id header")
    return uid

def _parse_plan(plan_text: str) -> List[Dict]:
    """
    Парсит план тренировок.
    Сначала пытается использовать ИИ-парсер, но при таймауте сразу переходит на fallback.
    """
    if not plan_text:
        return []
    
    # ИИ-парсер отключен по умолчанию из-за таймаутов
    # Используем быстрый fallback парсер для мгновенной загрузки
    # Включить можно через USE_AI_PARSER=true в .env (для сложных случаев)
    use_ai_parser = os.getenv("USE_AI_PARSER", "false").lower() == "true"
    
    if use_ai_parser:
        # Используем ИИ-парсер только если явно включен
        try:
            try:
                from app.workout_parser import parse_workout_plan_with_ai
            except ImportError:
                from workout_parser import parse_workout_plan_with_ai
            
            exercises = parse_workout_plan_with_ai(plan_text)
            
            # Конвертируем формат для совместимости со старым кодом
            result = []
            for ex in exercises:
                sets = []
                for set_data in ex.get("sets", []):
                    # Формируем info для обратной совместимости
                    info_parts = []
                    if set_data.get("reps"):
                        info_parts.append(set_data["reps"])
                    if set_data.get("weight_kg"):
                        info_parts.append(f"{set_data['weight_kg']}кг")
                    if set_data.get("rpe"):
                        info_parts.append(f"RPE {set_data['rpe']}")
                    
                    info = " ".join(info_parts) if info_parts else ""
                    
                    sets.append({
                        "number": set_data.get("number", 1),
                        "info": info,
                        "reps": set_data.get("reps", ""),
                        "weight_kg": set_data.get("weight_kg")
                    })
                
                result.append({
                    "name": ex["name"],
                    "sets": sets
                })
            
            return result
        except Exception as e:
            import logging
            logging.warning(f"AI parser error: {e}, using fallback")
            # Продолжаем на fallback
    
    # Используем быстрый fallback парсер (по умолчанию)
    if not plan_text:
        return []
    
    exercises = []
    current_exercise = None
    lines = plan_text.split('\n')
    skip_sections = ['разминка', 'разогрев', 'заминка', 'основная часть', 'основная', 'warm-up', 'cool-down']
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Убираем эмодзи и маркеры списка
        line_clean = re.sub(r'^[🗓️📝•\-\*🏋️🍽️]\s*', '', line)
        line_clean = re.sub(r'^\d+[\.\)]\s*', '', line_clean)
        line_clean = line_clean.strip()
        
        # Пропускаем заголовки разделов
        line_lower = line_clean.lower()
        if any(section in line_lower for section in skip_sections):
            # Если есть текущее упражнение без подходов, сохраняем его
            if current_exercise and current_exercise['sets']:
                exercises.append(current_exercise)
                current_exercise = None
            continue
        
        # Проверяем формат: "Упражнение: 4х8-10" или "Упражнение: 4 подхода по 10-12"
        # Улучшенный паттерн для поддержки названий в скобках: "Бабочка (сведение рук): 4х8-10"
        colon_match = re.match(r'^(.+?):\s*(.+)', line_clean)
        if colon_match:
            exercise_name = colon_match.group(1).strip()
            sets_info = colon_match.group(2).strip()
            
            # Парсим информацию о подходах
            # Формат: "4х8-10" или "4 подхода по 10-12 повторений" или "3хдо отказа"
            sets = []
            
            # Формат "4х8-10" или "4x8-10" или "4х8-10 60кг" или "4х8-10, 60кг"
            x_match = re.search(r'(\d+)\s*[хx]\s*([\d\-до\s]+(?:[\s,]+)?\d+\s*кг)?', sets_info, re.IGNORECASE)
            if not x_match:
                # Попробуем найти вес отдельно: "4х8-10, 60 кг"
                x_match = re.search(r'(\d+)\s*[хx]\s*([\d\-до\s]+)', sets_info, re.IGNORECASE)
            
            if x_match:
                num_sets = int(x_match.group(1))
                reps_info = x_match.group(2).strip() if x_match.group(2) else sets_info
                
                # Ищем вес в разных форматах: "60кг", "60 кг", ", 60кг", "с весом 70 кг", "весом 70 кг"
                weight_kg = None
                # Сначала ищем "с весом X кг" или "весом X кг"
                weight_match = re.search(r'(?:с\s+)?весом\s+(\d+(?:[.,]\d+)?)\s*кг', sets_info, re.IGNORECASE)
                if weight_match:
                    weight_kg = weight_match.group(1).replace(',', '.')
                    try:
                        weight_kg = str(int(float(weight_kg)))  # Конвертируем в целое число
                    except:
                        weight_kg = weight_match.group(1)
                
                # Если не нашли, ищем стандартные форматы: "60кг", "60 кг", ", 60кг", ", 60 кг"
                if not weight_kg:
                    weight_match = re.search(r'[,\s]+(\d+(?:[.,]\d+)?)\s*кг|^(\d+(?:[.,]\d+)?)\s*кг|(\d+(?:[.,]\d+)?)\s*кг', sets_info, re.IGNORECASE)
                    if weight_match:
                        weight_str = weight_match.group(1) or weight_match.group(2) or weight_match.group(3)
                        weight_str = weight_str.replace(',', '.')
                        try:
                            weight_kg = str(int(float(weight_str)))  # Конвертируем в целое число
                        except:
                            weight_kg = weight_str
                
                # Если вес не найден в строке с подходами, ищем в конце всей строки
                if not weight_kg:
                    weight_match = re.search(r'(\d+(?:[.,]\d+)?)\s*кг', sets_info, re.IGNORECASE)
                    if weight_match:
                        weight_str = weight_match.group(1).replace(',', '.')
                        try:
                            weight_kg = str(int(float(weight_str)))
                        except:
                            weight_kg = weight_match.group(1)
                
                # Убираем вес из строки с повторениями (включая "с весом X кг")
                reps = re.sub(r'(?:с\s+)?весом\s+\d+(?:[.,]\d+)?\s*кг|,\s*\d+(?:[.,]\d+)?\s*кг|\d+(?:[.,]\d+)?\s*кг', '', reps_info, flags=re.IGNORECASE).strip()
                reps = re.sub(r'^,\s*|,\s*$', '', reps).strip()  # Убираем запятые по краям
                
                # Исправляем обрезанные фразы типа "до о" -> "до отказа"
                if reps == "до о":
                    reps = "до отказа"
                
                for i in range(1, num_sets + 1):
                    sets.append({
                        'number': i,
                        'info': sets_info,  # Сохраняем оригинальную строку
                        'reps': reps,
                        'weight_kg': weight_kg
                    })
            else:
                # Формат "4 подхода по 10-12 повторений" или "4 подхода по 10-12 60кг"
                approach_match = re.search(r'(\d+)\s*подход[а-я]*\s*(?:по\s*)?([\d\-до\s]+)', sets_info, re.IGNORECASE)
                if approach_match:
                    num_sets = int(approach_match.group(1))
                    reps_info = approach_match.group(2).strip()
                    
                    # Ищем вес в разных форматах
                    weight_kg = None
                    # Сначала ищем "с весом X кг" или "весом X кг"
                    weight_match = re.search(r'(?:с\s+)?весом\s+(\d+(?:[.,]\d+)?)\s*кг', sets_info, re.IGNORECASE)
                    if weight_match:
                        weight_str = weight_match.group(1).replace(',', '.')
                        try:
                            weight_kg = str(int(float(weight_str)))
                        except:
                            weight_kg = weight_match.group(1)
                    
                    # Если не нашли, ищем стандартные форматы
                    if not weight_kg:
                        weight_match = re.search(r'[,\s]+(\d+(?:[.,]\d+)?)\s*кг|^(\d+(?:[.,]\d+)?)\s*кг|(\d+(?:[.,]\d+)?)\s*кг', sets_info, re.IGNORECASE)
                        if weight_match:
                            weight_str = weight_match.group(1) or weight_match.group(2) or weight_match.group(3)
                            weight_str = weight_str.replace(',', '.')
                            try:
                                weight_kg = str(int(float(weight_str)))
                            except:
                                weight_kg = weight_str
                    
                    # Убираем вес из строки с повторениями (включая "с весом X кг")
                    reps = re.sub(r'(?:с\s+)?весом\s+\d+(?:[.,]\d+)?\s*кг|,\s*\d+(?:[.,]\d+)?\s*кг|\d+(?:[.,]\d+)?\s*кг', '', reps_info, flags=re.IGNORECASE).strip()
                    reps = re.sub(r'^,\s*|,\s*$', '', reps).strip()
                    
                    # Исправляем обрезанные фразы типа "до о" -> "до отказа"
                    if reps == "до о":
                        reps = "до отказа"
                    
                    for i in range(1, num_sets + 1):
                        sets.append({
                            'number': i,
                            'info': sets_info,  # Сохраняем оригинальную строку
                            'reps': reps,
                            'weight_kg': weight_kg
                        })
                else:
                    # Если не удалось распарсить, создаем один подход с полной информацией
                    weight_kg = None
                    # Ищем вес в разных форматах
                    weight_match = re.search(r'(?:с\s+)?весом\s+(\d+(?:[.,]\d+)?)\s*кг|(\d+(?:[.,]\d+)?)\s*кг', sets_info, re.IGNORECASE)
                    if weight_match:
                        weight_str = (weight_match.group(1) or weight_match.group(2)).replace(',', '.')
                        try:
                            weight_kg = str(int(float(weight_str)))
                        except:
                            weight_kg = weight_str
                    
                    # Убираем вес из строки с повторениями
                    reps = re.sub(r'(?:с\s+)?весом\s+\d+(?:[.,]\d+)?\s*кг|\d+(?:[.,]\d+)?\s*кг', '', sets_info, flags=re.IGNORECASE).strip()
                    reps = re.sub(r'\s*повторени[яй]?\s*', '', reps, flags=re.IGNORECASE).strip()
                    
                    sets.append({
                        'number': 1,
                        'info': sets_info,
                        'reps': reps,
                        'weight_kg': weight_kg
                    })
            
            # Сохраняем предыдущее упражнение
            if current_exercise and current_exercise['sets']:
                exercises.append(current_exercise)
            
            # Создаем новое упражнение
            current_exercise = {
                'name': exercise_name,
                'sets': sets
            }
            continue
        
        # Проверяем, является ли строка упражнением (начинается с дефиса или содержит только название)
        if line_clean.startswith('-') or (not ':' in line_clean and not 'подход' in line_lower):
            # Убираем дефис в начале
            line_clean = re.sub(r'^-\s*', '', line_clean)
            
            # Если это не подход, то это новое упражнение
            if 'подход' not in line_lower and 'set' not in line_lower:
                # Сохраняем предыдущее упражнение
                if current_exercise and current_exercise['sets']:
                    exercises.append(current_exercise)
                
                # Создаем новое упражнение
                current_exercise = {
                    'name': line_clean,
                    'sets': []
                }
            else:
                # Это подход в формате "1 подход - 20 кг"
                if current_exercise is None:
                    current_exercise = {
                        'name': 'Упражнение',
                        'sets': []
                    }
                
                # Парсим подход: "1 подход - 20 кг" или "1 подход - 8-10 повторений 60кг"
                set_match = re.search(r'(\d+)\s*подход[а-я]*\s*[:\-]\s*(.+)', line_clean, re.IGNORECASE)
                if set_match:
                    set_num = int(set_match.group(1))
                    set_info = set_match.group(2).strip()
                    
                    # Парсим вес и повторения отдельно
                    weight_match = re.search(r'(\d+)\s*кг', set_info, re.IGNORECASE)
                    weight_kg = weight_match.group(1) if weight_match else None
                    reps = re.sub(r'\s*\d+\s*кг', '', set_info, flags=re.IGNORECASE).strip()
                    # Убираем слова "повторений", "повторения" и т.д.
                    reps = re.sub(r'\s*повторени[яй]?\s*', '', reps, flags=re.IGNORECASE).strip()
                    
                    current_exercise['sets'].append({
                        'number': set_num,
                        'info': set_info,
                        'reps': reps,
                        'weight_kg': weight_kg
                    })
        else:
            # Это подход в другом формате
            if current_exercise is None:
                current_exercise = {
                    'name': 'Упражнение',
                    'sets': []
                }
            
            # Парсим подход: "1 подход - 20 кг" или "1 подход: 20 кг"
            set_match = re.search(r'(\d+)\s*подход[а-я]*\s*[:\-]\s*(.+)', line_clean, re.IGNORECASE)
            if set_match:
                set_num = int(set_match.group(1))
                set_info = set_match.group(2).strip()
                
                # Парсим вес и повторения отдельно
                weight_kg = None
                # Ищем вес в разных форматах
                weight_match = re.search(r'(?:с\s+)?весом\s+(\d+(?:[.,]\d+)?)\s*кг|(\d+(?:[.,]\d+)?)\s*кг', set_info, re.IGNORECASE)
                if weight_match:
                    weight_str = (weight_match.group(1) or weight_match.group(2)).replace(',', '.')
                    try:
                        weight_kg = str(int(float(weight_str)))
                    except:
                        weight_kg = weight_str
                
                # Убираем вес из строки с повторениями
                reps = re.sub(r'(?:с\s+)?весом\s+\d+(?:[.,]\d+)?\s*кг|\d+(?:[.,]\d+)?\s*кг', '', set_info, flags=re.IGNORECASE).strip()
                # Убираем слова "повторений", "повторения" и т.д.
                reps = re.sub(r'\s*повторени[яй]?\s*', '', reps, flags=re.IGNORECASE).strip()
                
                current_exercise['sets'].append({
                    'number': set_num,
                    'info': set_info,
                    'reps': reps,
                    'weight_kg': weight_kg
                })
    
    # Добавляем последнее упражнение
    if current_exercise:
        # Если у упражнения нет подходов, но есть название - создаем один подход
        if not current_exercise['sets']:
            current_exercise['sets'] = [{
                'number': 1,
                'info': 'Выполнить',
                'reps': '',
                'weight_kg': None
            }]
        exercises.append(current_exercise)
    
    return exercises

def _get_workout_state(user_id: str, date: str) -> Dict:
    """Получает состояние выполнения упражнений на дату"""
    conn = _workout_state_db()
    try:
        rows = conn.execute("""
            SELECT exercise_name, set_number, weight, reps, completed, skipped
            FROM workout_state
            WHERE user_id = ? AND date = ?
            ORDER BY exercise_name, set_number
        """, (user_id, date)).fetchall()
        
        state = {}
        for row in rows:
            ex_name, set_num, weight, reps, completed, skipped = row
            if ex_name not in state:
                state[ex_name] = {}
            state[ex_name][set_num] = {
                'completed': bool(completed),
                'skipped': bool(skipped),
                'weight': weight,
                'reps': reps
            }
        return state
    finally:
        conn.close()

def _update_set_state(user_id: str, date: str, exercise_name: str, set_number: int, 
                     completed: Optional[bool] = None, skipped: Optional[bool] = None, weight: Optional[str] = None, reps: Optional[str] = None):
    """Обновляет состояние подхода"""
    conn = _workout_state_db()
    try:
        now = datetime.now().isoformat()
        
        # Получаем текущее состояние
        row = conn.execute("""
            SELECT completed, skipped, weight, reps
            FROM workout_state
            WHERE user_id = ? AND date = ? AND exercise_name = ? AND set_number = ?
        """, (user_id, date, exercise_name, set_number)).fetchone()
        
        if row:
            current_completed, current_skipped, current_weight, current_reps = row
            new_completed = completed if completed is not None else current_completed
            new_skipped = skipped if skipped is not None else current_skipped
            new_weight = weight if weight is not None else current_weight
            new_reps = reps if reps is not None else current_reps
            
            # Если отмечаем как выполненный, снимаем пропуск и наоборот
            if completed is True:
                new_skipped = False
            elif skipped is True:
                new_completed = False
            
            conn.execute("""
                UPDATE workout_state
                SET completed = ?, skipped = ?, weight = ?, reps = ?, updated_at = ?
                WHERE user_id = ? AND date = ? AND exercise_name = ? AND set_number = ?
            """, (new_completed, new_skipped, new_weight, new_reps, now, user_id, date, exercise_name, set_number))
        else:
            # Создаем новую запись
            new_completed = 1 if completed else 0
            new_skipped = 1 if skipped else 0
            conn.execute("""
                INSERT INTO workout_state (user_id, date, exercise_name, set_number, weight, reps, completed, skipped, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, date, exercise_name, set_number, weight or '', reps or '', new_completed, new_skipped, now))
        
        conn.commit()
    finally:
        conn.close()

@router.get("/api/workout-plan/today")
async def get_today_workout_plan(x_user_id: str = Header(None, alias="X-User-Id")):
    """Получает план тренировок на сегодня с состоянием выполнения"""
    user_id = _need_user(x_user_id)
    
    # Получаем сегодняшнюю дату (по московскому времени)
    moscow_tz = timezone(timedelta(hours=3))
    today = datetime.now(moscow_tz).strftime("%Y-%m-%d")
    
    # Получаем план на сегодня (только из kind='plan')
    conn = _db()
    try:
        row = conn.execute("""
            SELECT text FROM notes
            WHERE user_id = ? AND d = ? AND kind = 'plan'
        """, (user_id, today)).fetchone()
        plan_text = row[0] if row else ""
    finally:
        conn.close()
    
    # Парсим план
    exercises = _parse_plan(plan_text)
    
    # Получаем состояние выполнения
    state = _get_workout_state(user_id, today)
    
    # Объединяем упражнения с состоянием
    result = []
    for exercise in exercises:
        exercise_name = exercise['name']
        sets = []
        all_completed = True
        all_skipped = True
        has_sets = len(exercise['sets']) > 0
        
        for set_info in exercise['sets']:
            set_num = set_info['number']
            set_state = state.get(exercise_name, {}).get(set_num, {})
            
            completed = set_state.get('completed', False)
            skipped = set_state.get('skipped', False)
            performed_reps = set_state.get('reps', '')
            
            sets.append({
                'number': set_num,
                'info': set_info.get('info', ''),
                'reps': set_info.get('reps', ''),
                'weight_kg': set_info.get('weight_kg'),
                'completed': completed,
                'skipped': skipped,
                'performed_reps': performed_reps
            })
            
            if not completed:
                all_completed = False
            if not skipped:
                all_skipped = False
        
        # Вычисляем рабочий и максимальный вес
        working_weight = 0
        max_weight = 0
        
        weights = []
        for set_info in exercise['sets']:
            weight_kg = set_info.get('weight_kg')
            if weight_kg:
                try:
                    # Поддерживаем разные форматы: "80", "80кг", "80 кг"
                    weight_str = str(weight_kg).replace('кг', '').replace('kg', '').strip()
                    weight_val = int(float(weight_str))  # Поддерживаем "80.5" -> 80
                    weights.append(weight_val)
                    if weight_val > max_weight:
                        max_weight = weight_val
                except (ValueError, TypeError):
                    pass
        
        # Рабочий вес - средний из всех подходов (или минимальный, если все одинаковые)
        if weights:
            if len(set(weights)) == 1:
                # Все подходы с одинаковым весом - берем минимальный
                working_weight = min(weights)
            else:
                # Разные веса - берем среднее значение
                working_weight = int(sum(weights) / len(weights))
        
        result.append({
            'name': exercise_name,
            'sets': sets,
            'completed': all_completed and has_sets,
            'all_skipped': all_skipped and has_sets,
            'working_weight': working_weight,
            'max_weight': max_weight
        })
    
    # has_plan = True если есть план И есть хотя бы одно упражнение
    has_plan = bool(plan_text) and len(result) > 0
    
    return {
        'date': today,
        'exercises': result,
        'has_plan': has_plan
    }


# Endpoint /api/generate-plan перенесен в generate_plan_api.py
# Этот файл теперь отвечает только за загрузку и управление состоянием плана тренировок

class SetStateUpdate(BaseModel):
    exercise_name: str
    set_number: int
    completed: Optional[bool] = None
    skipped: Optional[bool] = None
    reps: Optional[str] = None

@router.post("/api/workout-plan/set-state")
async def update_set_state(
    update: SetStateUpdate,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    """Обновляет состояние подхода (выполнен/пропущен)"""
    user_id = _need_user(x_user_id)
    moscow_tz = timezone(timedelta(hours=3))
    today = datetime.now(moscow_tz).strftime("%Y-%m-%d")
    
    _update_set_state(
        user_id, today,
        update.exercise_name,
        update.set_number,
        update.completed,
        update.skipped,
        reps=update.reps
    )
    
    return {"success": True}
