"""
API endpoint для статистики - используется в Web App
"""
import os, sqlite3
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, HTTPException, Query
from typing import Dict, List, Optional

DB_PATH = (os.getenv("TRACKER_DB_PATH") or "/data/tracker.db").strip()
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

def _need_user(x_user_id: str | None):
    uid = (x_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="Missing X-User-Id header")
    return uid

def calculate_streak(workout_dates: List[str]) -> Dict[str, int]:
    """Вычисляет текущую и максимальную серию дней В ударе"""
    if not workout_dates:
        return {"current": 0, "max": 0, "total": 0}
    
    sorted_dates = sorted(set(workout_dates))
    today = datetime.now().date()
    current_streak = 0
    check_date = today
    
    # Проверяем сегодня
    if today.isoformat() in sorted_dates:
        current_streak = 1
        check_date = today - timedelta(days=1)
    
    # Продолжаем идти назад
    while check_date.isoformat() in sorted_dates:
        current_streak += 1
        check_date -= timedelta(days=1)
    
    # Максимальная серия
    max_streak = 1
    current_sequence = 1
    
    for i in range(1, len(sorted_dates)):
        prev_date = datetime.strptime(sorted_dates[i-1], "%Y-%m-%d").date()
        curr_date = datetime.strptime(sorted_dates[i], "%Y-%m-%d").date()
        
        if (curr_date - prev_date).days == 1:
            current_sequence += 1
            max_streak = max(max_streak, current_sequence)
        else:
            current_sequence = 1
    
    return {
        "current": current_streak,
        "max": max_streak,
        "total": len(sorted_dates)
    }

@router.get("/api/stats")
def get_stats(
    days: int = Query(90, description="Количество дней для анализа"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """Получает статистику пользователя"""
    uid = _need_user(x_user_id)
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    conn = _db()
    try:
        # Получаем все тренировки за период
        workout_dates = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            row = conn.execute(
                "SELECT text FROM notes WHERE user_id=? AND d=? AND kind='workouts'",
                (uid, date_str)
            ).fetchone()
            
            if row and row[0] and row[0].strip():
                workout_dates.append(date_str)
            
            current_date += timedelta(days=1)
        
        # Вычисляем серии
        streak = calculate_streak(workout_dates)
        
        # Дополнительные метрики
        total_days = (end_date - start_date).days + 1
        workout_percentage = (streak["total"] / total_days * 100) if total_days > 0 else 0
        avg_per_week = (streak["total"] / (total_days / 7)) if total_days > 0 else 0
        
        # Распределение по дням недели
        weekday_counts = [0] * 7  # 0=понедельник, 6=воскресенье
        for date_str in workout_dates:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            weekday = date_obj.weekday()
            weekday_counts[weekday] += 1
        
        # Данные для графика активности (последние 60 дней для детализации)
        chart_days = min(days, 60)
        chart_start = end_date - timedelta(days=chart_days)
        chart_data = []
        chart_date = chart_start
        
        while chart_date <= end_date:
            chart_data.append({
                "date": chart_date.isoformat(),
                "has_workout": chart_date.isoformat() in workout_dates
            })
            chart_date += timedelta(days=1)
        
        # Вычисляем средние значения для сравнения
        # Средний процент активности за предыдущие периоды
        prev_periods = []
        for i in range(1, 4):  # Последние 3 периода
            prev_start = start_date - timedelta(days=days * i)
            prev_end = start_date - timedelta(days=1)
            prev_workouts = 0
            check_date = prev_start
            while check_date <= prev_end:
                date_str = check_date.isoformat()
                row = conn.execute(
                    "SELECT text FROM notes WHERE user_id=? AND d=? AND kind='workouts'",
                    (uid, date_str)
                ).fetchone()
                if row and row[0] and row[0].strip():
                    prev_workouts += 1
                check_date += timedelta(days=1)
            prev_periods.append(prev_workouts)
        
        avg_percentage = (sum(prev_periods) / (len(prev_periods) * days * 100)) if prev_periods else workout_percentage
        
        # Среднее количество тренировок в неделю за предыдущие периоды
        avg_prev_per_week = (sum(prev_periods) / (len(prev_periods) * (days / 7))) if prev_periods else avg_per_week
        
        # Данные для объединенного графика (кумулятивный процент активности за весь период)
        # Группируем по неделям для более плавного графика
        percentage_chart_data = []
        avg_chart_data = []
        current_week_start = start_date
        
        while current_week_start <= end_date:
            week_end = min(current_week_start + timedelta(days=6), end_date)
            week_workouts = 0
            week_days = 0
            
            check_date = current_week_start
            while check_date <= week_end:
                date_str = check_date.isoformat()
                row = conn.execute(
                    "SELECT text FROM notes WHERE user_id=? AND d=? AND kind='workouts'",
                    (uid, date_str)
                ).fetchone()
                if row and row[0] and row[0].strip():
                    week_workouts += 1
                week_days += 1
                check_date += timedelta(days=1)
            
            # Текущий процент за неделю
            current_week_percentage = (week_workouts / week_days * 100) if week_days > 0 else 0
            
            # Средний процент активности за весь период
            avg_week_percentage = workout_percentage
            
            # Текущее среднее в неделю за эту неделю
            current_week_avg = week_workouts
            
            # Среднее в неделю за весь период
            avg_week_avg = avg_per_week
            
            percentage_chart_data.append({
                "date": current_week_start.isoformat(),
                "current": round(current_week_percentage, 1),
                "average": round(avg_week_percentage, 1)
            })
            
            avg_chart_data.append({
                "date": current_week_start.isoformat(),
                "current": round(current_week_avg, 1),
                "average": round(avg_week_avg, 1)
            })
            
            current_week_start += timedelta(days=7)
        
        # Убеждаемся, что массивы всегда есть
        if not percentage_chart_data:
            percentage_chart_data = []
        if not avg_chart_data:
            avg_chart_data = []
        
        result = {
            "streak": streak,
            "workout_percentage": round(workout_percentage, 1),
            "avg_percentage": round(avg_percentage, 1),
            "avg_per_week": round(avg_per_week, 1),
            "avg_prev_per_week": round(avg_prev_per_week, 1),
            "total_period_days": total_days,
            "weekday_distribution": weekday_counts,
            "chart_data": chart_data,
            "percentage_chart_data": percentage_chart_data,
            "avg_chart_data": avg_chart_data,
            "period_days": days
        }
        
        return result
    finally:
        conn.close()
