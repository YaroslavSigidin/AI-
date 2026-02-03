"""
Улучшенный модуль статистики с визуально привлекательными графиками
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from io import BytesIO
from collections import defaultdict

try:
    from matplotlib import pyplot as plt
    from matplotlib import dates as mdates
    from matplotlib.patches import Rectangle
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
    
    # Настройка стиля для красивых графиков
    plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')
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
    except Exception as e:
        # Логируем ошибку для отладки
        print(f"API request error: {e}")
        return {}

def get_user_workout_dates(user_id: int, days: int = 90) -> Dict[str, List[str]]:
    """Получает даты с тренировками за период"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    workout_dates = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.isoformat()
        workouts_data = _api_req(f"/api/notes?d={date_str}&kind=workouts", user_id)
        workouts_text = workouts_data.get("text", "").strip()
        
        if workouts_text:
            workout_dates.append(date_str)
        
        current_date += timedelta(days=1)
    
    return {
        "dates": workout_dates,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_days": len(workout_dates)
    }

def calculate_streak(workout_dates: List[str]) -> Dict[str, int]:
    """Вычисляет текущую и максимальную серию дней В ударе"""
    if not workout_dates:
        return {"current": 0, "max": 0, "total": 0}
    
    # Сортируем даты
    sorted_dates = sorted(set(workout_dates))
    
    # Вычисляем текущую серию (от сегодня назад)
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
    
    # Вычисляем максимальную серию
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

def generate_streak_stats(user_id: int, days: int = 90) -> Dict:
    """Генерирует статистику по сериям тренировок"""
    workout_data = get_user_workout_dates(user_id, days)
    streak = calculate_streak(workout_data["dates"])
    
    # Дополнительные метрики
    total_days = (datetime.now().date() - datetime.strptime(workout_data["start_date"], "%Y-%m-%d").date()).days + 1
    workout_percentage = (streak["total"] / total_days * 100) if total_days > 0 else 0
    avg_per_week = (streak["total"] / (total_days / 7)) if total_days > 0 else 0
    
    return {
        "streak": streak,
        "workout_percentage": round(workout_percentage, 1),
        "avg_per_week": round(avg_per_week, 1),
        "total_period_days": total_days,
        "dates": workout_data["dates"]
    }

def generate_streak_chart(user_id: int, days: int = 90) -> Optional[BytesIO]:
    """Создает красивый график серии тренировок (календарь активности)"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    stats = generate_streak_stats(user_id, days)
    workout_dates = set(stats["dates"])
    
    if not workout_dates:
        return None
    
    # Создаем календарь активности
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Подсчитываем тренировки по неделям
    weeks_data = defaultdict(lambda: [0] * 7)  # 0 = понедельник, 6 = воскресенье
    
    current_date = start_date
    while current_date <= end_date:
        week_num = (current_date - start_date).days // 7
        weekday = current_date.weekday()
        if current_date.isoformat() in workout_dates:
            weeks_data[week_num][weekday] = 1
        current_date += timedelta(days=1)
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Палитра цветов
    colors = ['#ebedf0', '#c6e48b', '#40c463', '#30a14e', '#216e39']
    
    # Рисуем календарь
    week_count = len(weeks_data)
    for week_idx in range(week_count):
        for day_idx in range(7):
            has_workout = weeks_data[week_idx][day_idx]
            color = colors[1] if has_workout else colors[0]
            
            rect = Rectangle((week_idx, 6-day_idx), 0.8, 0.8, 
                           facecolor=color, edgecolor='white', linewidth=0.5)
            ax.add_patch(rect)
    
    # Настройка осей
    day_labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    ax.set_yticks(range(7))
    ax.set_yticklabels(day_labels, fontsize=10)
    ax.set_xticks(range(0, week_count, max(1, week_count // 12)))
    ax.set_xlabel('Недели', fontsize=12, fontweight='bold')
    ax.set_ylabel('День недели', fontsize=12, fontweight='bold')
    ax.set_title(f'Календарь активности тренировок за {days} дней', 
                fontsize=16, fontweight='bold', pad=20)
    
    # Легенда
    legend_elements = [
        Rectangle((0, 0), 1, 1, facecolor=colors[0], edgecolor='gray', label='Нет тренировки'),
        Rectangle((0, 0), 1, 1, facecolor=colors[1], edgecolor='gray', label='Тренировка')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    ax.set_xlim(-0.5, week_count)
    ax.set_ylim(-0.5, 7)
    ax.set_aspect('equal')
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def generate_streak_summary_chart(user_id: int, days: int = 90) -> Optional[BytesIO]:
    """Создает красивый график с метриками В ударе"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    stats = generate_streak_stats(user_id, days)
    streak = stats["streak"]
    
    # Создаем график с метриками
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('📊 Статистика "В ударе"', fontsize=20, fontweight='bold', y=0.98)
    
    # 1. Текущая серия (большой индикатор)
    ax1.axis('off')
    current_streak = streak["current"]
    max_streak = streak["max"]
    
    # Круговая диаграмма прогресса
    colors_progress = ['#40c463', '#ebedf0']
    sizes = [current_streak, max(1, max_streak - current_streak)]
    if current_streak == 0:
        sizes = [0, 100]
        colors_progress = ['#ebedf0', '#ebedf0']
    
    wedges, texts = ax1.pie(sizes, startangle=90, colors=colors_progress, 
                            counterclock=False, radius=0.8)
    
    # Текст в центре
    ax1.text(0, 0, f'{current_streak}\nдней', ha='center', va='center',
            fontsize=32, fontweight='bold', color='#30a14e')
    ax1.set_title('Текущая серия', fontsize=14, fontweight='bold', pad=20)
    
    # 2. Максимальная серия
    ax2.barh([0], [max_streak], color='#216e39', height=0.5)
    ax2.set_xlim(0, max(max_streak + 5, 20))
    ax2.set_yticks([])
    ax2.set_xlabel('Дни', fontsize=12)
    ax2.set_title(f'Максимальная серия: {max_streak} дней', fontsize=14, fontweight='bold')
    ax2.text(max_streak/2, 0, f'{max_streak}', ha='center', va='center',
            fontsize=24, fontweight='bold', color='white')
    
    # 3. Всего тренировок за период
    total = streak["total"]
    total_days = stats["total_period_days"]
    ax3.bar(['Всего тренировок'], [total], color='#30a14e', width=0.6)
    ax3.set_ylabel('Количество', fontsize=12)
    ax3.set_title(f'Всего тренировок: {total} из {total_days} дней', 
                 fontsize=14, fontweight='bold')
    ax3.text(0, total/2, f'{total}', ha='center', va='center',
            fontsize=24, fontweight='bold', color='white')
    
    # 4. Процент активности
    percentage = stats["workout_percentage"]
    colors_pct = ['#40c463' if percentage >= 50 else '#c6e48b' if percentage >= 30 else '#ebedf0']
    ax4.bar(['Активность'], [percentage], color=colors_pct[0], width=0.6)
    ax4.set_ylim(0, 100)
    ax4.set_ylabel('Процент', fontsize=12)
    ax4.set_title(f'Процент дней с тренировками: {percentage}%', 
                 fontsize=14, fontweight='bold')
    ax4.text(0, percentage/2, f'{percentage}%', ha='center', va='center',
            fontsize=24, fontweight='bold', color='white')
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def generate_timeline_chart(user_id: int, days: int = 60) -> Optional[BytesIO]:
    """Создает график активности по времени (timeline)"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    stats = generate_streak_stats(user_id, days)
    workout_dates = set(stats["dates"])
    
    if not workout_dates:
        return None
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Подсчитываем тренировки по дням
    dates_list = []
    workout_counts = []
    
    current_date = start_date
    while current_date <= end_date:
        dates_list.append(current_date)
        workout_counts.append(1 if current_date.isoformat() in workout_dates else 0)
        current_date += timedelta(days=1)
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # График активности
    ax.plot(dates_list, workout_counts, color='#40c463', linewidth=2, marker='o', 
           markersize=4, alpha=0.7, label='Тренировка')
    ax.fill_between(dates_list, workout_counts, alpha=0.3, color='#40c463')
    
    # Настройка осей
    ax.set_xlabel('Дата', fontsize=12, fontweight='bold')
    ax.set_ylabel('Активность', fontsize=12, fontweight='bold')
    ax.set_title(f'График активности тренировок за {days} дней', 
                fontsize=16, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim(-0.1, 1.1)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Нет', 'Есть'])
    
    # Форматирование дат
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 15)))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def generate_weekly_distribution_chart(user_id: int, days: int = 90) -> Optional[BytesIO]:
    """Создает график распределения тренировок по дням недели"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    stats = generate_streak_stats(user_id, days)
    workout_dates = set(stats["dates"])
    
    if not workout_dates:
        return None
    
    # Подсчитываем тренировки по дням недели (0=понедельник, 6=воскресенье)
    weekday_counts = [0] * 7
    day_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    day_names_short = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    
    for date_str in workout_dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday = date_obj.weekday()
        weekday_counts[weekday] += 1
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(12, 6))
    
    bars = ax.bar(day_names_short, weekday_counts, color='#30a14e', alpha=0.8, 
                  edgecolor='#216e39', linewidth=2)
    
    # Подсветка максимального значения
    max_idx = weekday_counts.index(max(weekday_counts))
    bars[max_idx].set_color('#40c463')
    bars[max_idx].set_alpha(1.0)
    bars[max_idx].set_edgecolor('#216e39')
    bars[max_idx].set_linewidth(3)
    
    # Добавляем значения на столбцы
    for i, (bar, count) in enumerate(zip(bars, weekday_counts)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{count}',
               ha='center', va='bottom', fontsize=14, fontweight='bold')
    
    ax.set_xlabel('День недели', fontsize=12, fontweight='bold')
    ax.set_ylabel('Количество тренировок', fontsize=12, fontweight='bold')
    ax.set_title('Распределение тренировок по дням недели', 
                fontsize=16, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close()
    
    return buf

def generate_stats_summary_text(user_id: int, days: int = 90) -> str:
    """Генерирует текстовую сводку статистики"""
    stats = generate_streak_stats(user_id, days)
    streak = stats["streak"]
    
    lines = []
    lines.append("🔥 СТАТИСТИКА \"В УДАРЕ\"\n")
    
    lines.append(f"⚡ Текущая серия: {streak['current']} дней подряд")
    lines.append(f"🏆 Максимальная серия: {streak['max']} дней")
    lines.append(f"📊 Всего тренировок: {streak['total']} из {stats['total_period_days']} дней")
    lines.append(f"📈 Процент активности: {stats['workout_percentage']}%")
    lines.append(f"📅 Среднее в неделю: {stats['avg_per_week']:.1f} тренировок")
    
    return "\n".join(lines)
