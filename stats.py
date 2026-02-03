"""
Модуль для генерации статистики и графиков прогресса
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from io import BytesIO

try:
    from matplotlib import pyplot as plt
    from matplotlib import dates as mdates
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

API_BASE_URL = (os.getenv("API_BASE_URL") or "http://api:8000").strip().rstrip("/")

def _api_req(path: str, user_id: int, timeout: int = 10) -> dict:
    """Запрос к API для получения данных"""
    import urllib.request
    import json as json_lib
    
    url = f"{API_BASE_URL}{path}"
    req = urllib.request.Request(url)
    req.add_header("X-User-Id", str(user_id))
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json_lib.loads(raw) if raw else {}
    except Exception:
        return {}

def get_user_stats(user_id: int, days: int = 30) -> Dict:
    """Получает статистику пользователя за период"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    stats = {
        "workouts": [],
        "meals": [],
        "plans": [],
        "dates": [],
        "total_workouts": 0,
        "total_meals": 0,
        "workout_days": set(),
    }
    
    # Получаем данные за каждый день
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        
        workouts_data = _api_req(f"/api/notes?d={date_str}&kind=workouts", user_id)
        meals_data = _api_req(f"/api/notes?d={date_str}&kind=meals", user_id)
        plans_data = _api_req(f"/api/notes?d={date_str}&kind=plan", user_id)
        
        workouts_text = workouts_data.get("text", "").strip()
        meals_text = meals_data.get("text", "").strip()
        plans_text = plans_data.get("text", "").strip()
        
        if workouts_text:
            stats["workouts"].append({"date": date_str, "text": workouts_text})
            stats["workout_days"].add(date_str)
            stats["total_workouts"] += 1
        
        if meals_text:
            stats["meals"].append({"date": date_str, "text": meals_text})
            stats["total_meals"] += 1
        
        if plans_text:
            stats["plans"].append({"date": date_str, "text": plans_text})
        
        stats["dates"].append(date_str)
        current_date += timedelta(days=1)
    
    stats["workout_days"] = len(stats["workout_days"])
    return stats

def generate_workout_chart(user_id: int, days: int = 30) -> Optional[BytesIO]:
    """Генерирует график тренировок"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    stats = get_user_stats(user_id, days)
    
    if not stats["workouts"]:
        return None
    
    # Подсчитываем тренировки по дням
    workout_count_by_date = {}
    for workout in stats["workouts"]:
        date_str = workout["date"]
        workout_count_by_date[date_str] = workout_count_by_date.get(date_str, 0) + 1
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(10, 6))
    
    dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in stats["dates"]]
    counts = [workout_count_by_date.get(d, 0) for d in stats["dates"]]
    
    ax.plot(dates, counts, marker='o', linestyle='-', linewidth=2, markersize=6, color='#4CAF50')
    ax.fill_between(dates, counts, alpha=0.3, color='#4CAF50')
    
    ax.set_xlabel('Дата', fontsize=12)
    ax.set_ylabel('Количество тренировок', fontsize=12)
    ax.set_title(f'Прогресс тренировок за {days} дней', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Форматирование дат
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Сохраняем в BytesIO
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf

def generate_summary_stats(user_id: int, days: int = 30) -> str:
    """Генерирует текстовую сводку статистики"""
    stats = get_user_stats(user_id, days)
    
    lines = []
    lines.append(f"📊 Статистика за последние {days} дней:\n")
    
    lines.append(f"🏋️ Тренировки:")
    lines.append(f"   Всего дней с тренировками: {stats['workout_days']}")
    lines.append(f"   Всего тренировок: {stats['total_workouts']}")
    lines.append(f"   Среднее в неделю: {stats['total_workouts'] * 7 / days:.1f}\n")
    
    lines.append(f"🍽️ Питание:")
    lines.append(f"   Дней с записями: {stats['total_meals']}")
    lines.append(f"   Среднее в неделю: {stats['total_meals'] * 7 / days:.1f}\n")
    
    if stats["workouts"]:
        lines.append(f"📈 Активность:")
        last_week_days = 7
        recent_workouts = sum(1 for w in stats["workouts"] 
                             if (datetime.now().date() - datetime.strptime(w["date"], "%Y-%m-%d").date()).days <= last_week_days)
        lines.append(f"   Тренировок за последнюю неделю: {recent_workouts}")
    
    return "\n".join(lines)

def generate_weekly_chart(user_id: int) -> Optional[BytesIO]:
    """Генерирует график активности по дням недели"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    stats = get_user_stats(user_id, days=30)
    
    if not stats["workouts"]:
        return None
    
    # Подсчитываем тренировки по дням недели (0=понедельник, 6=воскресенье)
    weekday_counts = [0] * 7
    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    
    for workout in stats["workouts"]:
        date_obj = datetime.strptime(workout["date"], "%Y-%m-%d").date()
        weekday = date_obj.weekday()
        weekday_counts[weekday] += 1
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(8, 6))
    
    bars = ax.bar(day_names, weekday_counts, color='#2196F3', alpha=0.7, edgecolor='#1976D2', linewidth=1.5)
    
    # Подсветка максимального значения
    max_idx = weekday_counts.index(max(weekday_counts))
    bars[max_idx].set_color('#FF5722')
    bars[max_idx].set_alpha(1.0)
    
    ax.set_xlabel('День недели', fontsize=12)
    ax.set_ylabel('Количество тренировок', fontsize=12)
    ax.set_title('Распределение тренировок по дням недели', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    # Сохраняем в BytesIO
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf
