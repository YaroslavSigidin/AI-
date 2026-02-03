"""
Извлечение "силовых сигналов" из истории тренировок (notes.kind='workouts').
Цель: дать генератору плана опору по весам, прогрессии и слабым местам.

Важно: парсинг эвристический, но безопасный — если ничего не распарсили, вернем пусто.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

DB_PATH = (os.getenv("TRACKER_DB_PATH") or "/data/tracker.db").strip()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
          user_id TEXT NOT NULL,
          d TEXT NOT NULL,
          kind TEXT NOT NULL,
          text TEXT NOT NULL DEFAULT '',
          updated_at TEXT,
          PRIMARY KEY (user_id, d, kind)
        )
        """
    )
    conn.commit()
    return conn


def _normalize_exercise(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[•\-—–]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # легкая нормализация популярных вариантов
    repl = {
        "жим лёжа": "жим лежа",
        "жим штанги лёжа": "жим лежа",
        "приседания": "присед",
        "становая": "становая тяга",
        "тяга становая": "становая тяга",
    }
    return repl.get(s, s)


@dataclass
class SetEntry:
    reps: Optional[int]
    weight_kg: Optional[float]


@dataclass
class ExerciseEntry:
    name: str
    sets: List[SetEntry]


_RE_WEIGHT = re.compile(r"(?P<w>\d{1,3}(?:[.,]\d)?)\s*(?:кг|kg)\b", re.I)
_RE_REPS = re.compile(r"(?P<r>\d{1,2})\s*(?:повт|раз|reps?)\b", re.I)
_RE_X = re.compile(r"(?P<s>\d{1,2})\s*[xх×]\s*(?P<r>\d{1,2})", re.I)


def _parse_line(line: str) -> Tuple[Optional[str], List[SetEntry]]:
    """
    Пытается извлечь упражнение и набор сетов из одной строки.
    Поддерживает форматы:
    - "Жим лежа: 4х8 80кг"
    - "🏋️ Жим лежа: 4x8 80 kg"
    - "Присед 3х5 100кг"
    - "Тяга: 8 повторений 60кг"
    """
    raw = (line or "").strip()
    if not raw:
        return None, []

    # убрать эмодзи в начале
    raw = re.sub(r"^[^\wА-Яа-я]+", "", raw).strip()

    # разделение по двоеточию: "Упражнение: ..."
    if ":" in raw:
        left, right = raw.split(":", 1)
        ex = _normalize_exercise(left)
        payload = right.strip()
    else:
        # попытаться взять первые слова как упражнение до первой цифры
        m = re.search(r"\d", raw)
        if not m:
            return None, []
        ex = _normalize_exercise(raw[: m.start()].strip())
        payload = raw[m.start() :].strip()

    if not ex:
        return None, []
    # Отсекаем строки вида "1 подход", "3 подход" и т.п. — это не упражнение
    if re.match(r"^\d+\s*подход\b", ex, flags=re.I):
        return None, []

    sets: List[SetEntry] = []

    # 4х8 80кг
    mx = _RE_X.search(payload)
    mw = _RE_WEIGHT.search(payload)
    if mx and mw:
        try:
            s_cnt = int(mx.group("s"))
            reps = int(mx.group("r"))
            w = float(mw.group("w").replace(",", "."))
            for _ in range(max(1, s_cnt)):
                sets.append(SetEntry(reps=reps, weight_kg=w))
            return ex, sets
        except Exception:
            pass

    # "8 повторений 60кг"
    mr = _RE_REPS.search(payload)
    if mr and mw:
        try:
            reps = int(mr.group("r"))
            w = float(mw.group("w").replace(",", "."))
            sets.append(SetEntry(reps=reps, weight_kg=w))
            return ex, sets
        except Exception:
            pass

    # только вес (редко)
    if mw:
        try:
            w = float(mw.group("w").replace(",", "."))
            sets.append(SetEntry(reps=None, weight_kg=w))
            return ex, sets
        except Exception:
            pass

    return ex, []


def last_weight_map(user_id: int, days: int = 60) -> Dict[str, float]:
    """
    Возвращает последние распознанные рабочие веса по упражнениям.
    """
    notes = get_recent_workout_notes(user_id, days=days)
    ex_map = extract_exercises(notes)
    out: Dict[str, float] = {}
    for ex, entries in ex_map.items():
        entries_sorted = sorted(entries, key=lambda t: t[0], reverse=True)
        _, last_entry = entries_sorted[0]
        for s in last_entry.sets:
            if s.weight_kg is not None:
                out[ex] = float(s.weight_kg)
                break
    return out


def get_recent_workout_notes(user_id: int, days: int = 60) -> List[Tuple[str, str]]:
    uid = str(user_id)
    end = datetime.now().date()
    start = end - timedelta(days=days)
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT d, text FROM notes WHERE user_id=? AND kind='workouts' AND d>=? AND d<=? ORDER BY d DESC",
            (uid, start.isoformat(), end.isoformat()),
        ).fetchall()
        out: List[Tuple[str, str]] = []
        for d, txt in rows:
            if txt and str(txt).strip():
                out.append((str(d), str(txt)))
        return out
    finally:
        conn.close()


def extract_exercises(notes: List[Tuple[str, str]]) -> Dict[str, List[Tuple[str, ExerciseEntry]]]:
    """
    Возвращает map[exercise_name] -> список (date, entry)
    """
    acc: Dict[str, List[Tuple[str, ExerciseEntry]]] = {}
    for d, txt in notes:
        for line in (txt or "").splitlines():
            ex, sets = _parse_line(line)
            if not ex or not sets:
                continue
            entry = ExerciseEntry(name=ex, sets=sets)
            acc.setdefault(ex, []).append((d, entry))
    return acc


def _epley_1rm(weight: float, reps: int) -> float:
    # 1RM ≈ w * (1 + r/30)
    return float(weight) * (1.0 + float(reps) / 30.0)


def summarize_strength(user_id: int, days: int = 60) -> str:
    """
    Строит краткое резюме по рабочим весам: последние веса, примерный 1RM, что прогрессировать.
    """
    notes = get_recent_workout_notes(user_id, days=days)
    ex_map = extract_exercises(notes)
    if not ex_map:
        return ""

    lines: List[str] = []
    lines.append("История рабочих весов (по заметкам, последние ~60 дней):")

    # берём топ-8 упражнений по частоте
    items = sorted(ex_map.items(), key=lambda kv: len(kv[1]), reverse=True)[:8]
    for ex, entries in items:
        # последние 2 тренировки
        entries_sorted = sorted(entries, key=lambda t: t[0], reverse=True)
        last_date, last_entry = entries_sorted[0]

        # оценка: лучший сет по 1RM
        best_1rm = 0.0
        last_weight = None
        last_reps = None
        for s in last_entry.sets:
            if s.weight_kg and s.reps:
                best_1rm = max(best_1rm, _epley_1rm(s.weight_kg, s.reps))
            if s.weight_kg is not None and last_weight is None:
                last_weight = s.weight_kg
                last_reps = s.reps

        # предлагаемый микро-прогресс (грубо): +2.5кг, если 1RM достаточно
        inc = 2.5
        if last_weight and last_weight >= 100:
            inc = 5.0
        if last_weight and last_weight <= 30:
            inc = 2.0

        hint = ""
        if last_weight:
            hint = f"след. раз попробуй +{inc:g}кг, если техника ок и RPE ≤ 8."

        if last_weight:
            if last_reps:
                lines.append(f"- {ex}: последний раз {last_weight:g}кг x{last_reps} ({last_date}). 1RM~{best_1rm:.0f}кг; {hint}")
            else:
                lines.append(f"- {ex}: последний раз {last_weight:g}кг ({last_date}). 1RM~{best_1rm:.0f}кг; {hint}")
        else:
            lines.append(f"- {ex}: есть записи, но вес/повторы распарсить сложно.")

    lines.append(
        "Правило прогрессии: если в последнем подходе выполнил верх диапазона повторений и RPE ≤ 8 — увеличь вес на 2–5кг; "
        "если не добираешь повторы — оставь вес и добей повторения."
    )
    return "\n".join(lines).strip()

