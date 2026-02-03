"""
API endpoint для генерации плана тренировок/питания через ИИ
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import os

router = APIRouter()

# Импортируем tracker_agent для генерации плана
try:
    from tracker_agent import handle as agent_handle
except ImportError:
    # Если tracker_agent не доступен напрямую, используем альтернативный путь
    agent_handle = None

try:
    from referrals import get_user_trainer
except Exception:
    get_user_trainer = None


class GeneratePlanRequest(BaseModel):
    d: str  # Дата в формате YYYY-MM-DD
    kind: str  # "workouts" или "meals"

def _safe_import_context():
    """
    Эти модули опциональны. Если их нет/что-то упало — генерация не ломается.
    """
    profile_prompt = ""
    strength_prompt = ""
    try:
        from app.profile_store import get_profile
        prof = get_profile  # type: ignore
    except Exception:
        try:
            from profile_store import get_profile
            prof = get_profile  # type: ignore
        except Exception:
            prof = None  # type: ignore

    try:
        from app.workout_insights import summarize_strength
        strength = summarize_strength  # type: ignore
    except Exception:
        try:
            from workout_insights import summarize_strength
            strength = summarize_strength  # type: ignore
        except Exception:
            strength = None  # type: ignore

    try:
        from app.workout_insights import last_weight_map
        last_w = last_weight_map  # type: ignore
    except Exception:
        try:
            from workout_insights import last_weight_map
            last_w = last_weight_map  # type: ignore
        except Exception:
            last_w = None  # type: ignore

    return prof, strength, last_w


def _build_fallback_workout_plan(day: str, weights: dict) -> str:
    """
    Детерминированный fallback, если ИИ дал кривой JSON/таймаут.
    """
    def w(ex: str, default: int) -> int:
        try:
            val = float(weights.get(ex, default))
            return int(round(val))
        except Exception:
            return default

    bench = w("жим лежа", 40)
    row = w("тяга штанги в наклоне", 40)
    ohp = w("армейский жим", 25)
    dead = w("становая тяга", 60)
    curls = w("подъем штанги на бицепс", 20)

    return (
        f"🗓️ План тренировки на {day}\n\n"
        "Разминка 8–10 мин:\n"
        "- 5 мин легкое кардио\n"
        "- плечи/таз/голеностоп + 2 разминочных подхода перед первым упражнением\n\n"
        "Основная часть:\n"
        f"1) Жим лежа: 4х6–10 @ {bench}кг (RPE 7–8)\n"
        f"2) Тяга штанги в наклоне: 4х8–12 @ {row}кг (RPE 7–8)\n"
        f"3) Армейский жим: 3х8–12 @ {ohp}кг (RPE 7–8)\n"
        f"4) Становая тяга (техника): 3х5 @ {dead}кг (RPE 6–7)\n"
        "5) Тяга верхнего блока/подтягивания: 3х8–12 (RPE 7–8)\n"
        f"6) Бицепс (штанга): 3х10–15 @ {curls}кг\n"
        "7) Трицепс (канат/французский): 3х10–15\n\n"
        "Правило прогрессии (самое важное):\n"
        "- Если в последнем подходе сделал верх диапазона и RPE ≤ 8 → +2.5кг (на больших упражнениях иногда +5кг).\n"
        "- Если не добираешь повторы/ломается техника → оставь вес и добей повторы.\n"
        "- Если сомневаешься в весе: выбери такой, чтобы осталось ~2 повтора в запасе.\n"
    )


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> int:
    """Извлекает user_id из заголовка X-User-Id"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    try:
        return int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id")


@router.post("/api/generate-plan")
async def generate_plan(
    request: GeneratePlanRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Генерирует план тренировок или питания на указанный день через ИИ
    """
    if not agent_handle:
        raise HTTPException(status_code=500, detail="Agent handler not available")
    
    user_id = _get_user_id(x_user_id)
    kind = request.kind

    if get_user_trainer and get_user_trainer(user_id):
        raise HTTPException(status_code=403, detail="Plan editing is disabled for users bound to a trainer")
    
    if kind not in ["workouts", "meals"]:
        raise HTTPException(status_code=400, detail="kind must be 'workouts' or 'meals'")
    
    get_profile, summarize_strength, last_weight_map = _safe_import_context()
    profile_block = ""
    if get_profile:
        try:
            try:
                from app.profile_store import profile_to_prompt
            except Exception:
                from profile_store import profile_to_prompt
            profile_block = profile_to_prompt(get_profile(user_id))  # type: ignore
        except Exception:
            profile_block = ""

    strength_block = ""
    if summarize_strength:
        try:
            strength_block = summarize_strength(user_id, days=60)  # type: ignore
        except Exception:
            strength_block = ""

    weights_map = {}
    if last_weight_map:
        try:
            weights_map = last_weight_map(user_id, days=90)  # type: ignore
        except Exception:
            weights_map = {}

    # Формируем запрос для ИИ - как будто пользователь написал в чат
    # ВАЖНО: для генерации плана используем mode_hint="plan", чтобы ИИ создал план в разделе "plan"
    if kind == "workouts":
        # Максимально компактный промпт, чтобы ИИ не копировал его
        context_parts = []
        if profile_block and profile_block.strip() and profile_block != "(нет данных)":
            context_parts.append(f"Профиль: {profile_block[:150]}")
        if strength_block and strength_block.strip() and strength_block != "(нет данных)":
            context_parts.append(f"Веса: {strength_block[:200]}")
        
        context_str = "\n".join(context_parts) if context_parts else ""
        
        # Убираем фразу "Составь план" - она провоцирует копирование
        prompt = f"План тренировок на {request.d}:\n"
        if context_str:
            prompt += f"{context_str}\n"
        prompt += "КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО укажи вес в кг для КАЖДОГО упражнения!\n"
        prompt += "Формат каждого упражнения: 'Название: 4 подхода по 8-12 повторений, 80 кг'\n"
        prompt += "Или короткий формат: 'Название: 4х8-12 80кг'\n"
        prompt += "БЕЗ веса план бесполезен - пользователь не знает, с каким весом работать.\n"
        prompt += "Структура: Разминка → Основные упражнения (с весом в кг!) → Добивка → Заминка.\n"
        
        mode_hint = "plan"  # Используем "plan" чтобы ИИ создал план
    else:  # meals
        prompt = f"Составь подробный план питания на {request.d}. Включи завтрак, обед, ужин и перекусы с указанием продуктов и примерных порций. Сделай план сбалансированным и полезным."
        mode_hint = "plan"  # Используем "plan" чтобы ИИ создал план
    
    try:
        # Вызываем tracker_agent для генерации плана
        result = await agent_handle(
            user_id=user_id,
            text=prompt,
            mode_hint=mode_hint,
            force_mode_hint=True,
        )
        
        # Извлекаем сгенерированный текст
        writes = result.get("writes", [])
        generated_text = ""
        
        # ИИ сохраняет план в kind="plan" при mode_hint="plan"
        # Ищем план в kind="plan" для нужной даты
        for write in writes:
            if write.get("kind") == "plan" and write.get("d") == request.d:
                generated_text = write.get("text", "")
                break
        
        # Если не нашли "plan", ищем в нужном kind (workouts/meals) - на случай если ИИ сохранил туда
        if not generated_text:
            for write in writes:
                if write.get("kind") == kind and write.get("d") == request.d:
                    generated_text = write.get("text", "")
                    break
        
        # Если текст не найден в writes, используем reply (но игнорируем служебные сообщения)
        if not generated_text:
            reply_text = result.get("reply", "")
            if reply_text and not reply_text.startswith("⚠️") and reply_text != "✅ План создан":
                generated_text = reply_text
        
        # РАННЯЯ ПРОВЕРКА на промпт - ДО сохранения в БД
        if generated_text:
            bad_echo_indicators = [
                "Составь план",
                "План тренировок на",
                "КРИТИЧЕСКИ ВАЖНО",
                "Контекст профиля",
                "Контекст рабочих весов",
                "Сформируй план так",
                "Требования:",
                "Формат: Разминка",
            ]
            # Проверяем первые 200 символов - если там есть промпт, это эхо
            text_start = generated_text[:200].lower()
            bad_echo = any(indicator.lower() in text_start for indicator in bad_echo_indicators)
            
            # Если это промпт - сразу используем fallback
            if bad_echo:
                generated_text = _build_fallback_workout_plan(request.d, weights_map)
        
        # Если все еще нет текста, проверяем БД напрямую
        if not generated_text or generated_text.strip() == "":
            try:
                import sqlite3
                db_path = os.getenv("TRACKER_DB_PATH", "/data/tracker.db")
                conn = sqlite3.connect(db_path, check_same_thread=False)
                cursor = conn.cursor()
                # Проверяем сначала "plan" (куда ИИ сохраняет), потом нужный kind
                for check_kind in ["plan", kind]:
                    cursor.execute(
                        "SELECT text FROM notes WHERE user_id=? AND d=? AND kind=?",
                        (str(user_id), request.d, check_kind)
                    )
                    row = cursor.fetchone()
                    if row and row[0] and row[0].strip():
                        generated_text = row[0]
                        break
                conn.close()
            except Exception as db_e:
                import logging
                logging.error(f"DB check error: {db_e}")
        
        # Если план найден, но он в kind="plan", копируем его в нужный kind для отображения
        if generated_text and generated_text.strip():
            try:
                import sqlite3
                db_path = os.getenv("TRACKER_DB_PATH", "/data/tracker.db")
                conn = sqlite3.connect(db_path, check_same_thread=False)
                cursor = conn.cursor()
                # Сохраняем план в нужный kind (workouts/meals) для отображения в правильном разделе
                cursor.execute(
                    "INSERT OR REPLACE INTO notes (user_id, d, kind, text, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
                    (str(user_id), request.d, kind, generated_text)
                )
                conn.commit()
                conn.close()
            except Exception as db_e:
                import logging
                logging.error(f"Failed to copy plan to {kind}: {db_e}")
        
        if not generated_text or generated_text.strip() == "":
            raise HTTPException(
                status_code=500, 
                detail="Не удалось сгенерировать план. Попробуйте еще раз или напишите боту в чат."
            )

        # Финальная проверка на промпт (на случай если ранняя проверка пропустила)
        if kind == "workouts" and generated_text:
            # Проверяем, что ответ не слишком короткий (меньше 100 символов) - это тоже признак ошибки
            if len(generated_text.strip()) < 100:
                generated_text = _build_fallback_workout_plan(request.d, weights_map)
        
        return {
            "text": generated_text,
            "plan": generated_text,  # Для обратной совместимости
            "kind": kind,
            "d": request.d
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")
