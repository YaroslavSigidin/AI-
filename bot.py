import os
import asyncio
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.filters import Command, CommandObject
from aiogram.filters.command import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, Message, CallbackQuery

# === PROMO_UNLIMITED v1 ===
import json
from pathlib import Path

# промокоды через .env (можно несколько через запятую)
PAY_PROMO_CODES = set(
    c.strip().lower() for c in os.getenv("PAY_PROMO_CODES", "sigidingo").split(",") if c.strip()
)

# хранение активированных юзеров (переживает перезапуск)
_PROMO_DB = Path(__file__).resolve().parent / "promo_users.json"

def _promo_load():
    try:
        data = json.loads(_PROMO_DB.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(int(x) for x in data)
        return set()
    except Exception:
        return set()

def _promo_save(uids):
    _PROMO_DB.write_text(json.dumps(sorted(uids)), encoding="utf-8")

def is_promo_user(user_id: int) -> bool:
    return int(user_id) in _promo_load()

def grant_promo_user(user_id: int) -> None:
    uids = _promo_load()
    uids.add(int(user_id))
    _promo_save(uids)
# === PROMO_UNLIMITED v1 === END

# PROMO_ACCESS_V1
from access import apply_promo, check_and_hit, status_text

from paywall import (
    is_paid, inc_free_count, get_state, status_text, yk_create_payment, 
    yk_check_and_activate, yk_create_payment_amount, PAY_FREE_LIMIT, PAY_PRICE_RUB, activate_paid,
    get_expiring_subscriptions, get_expired_subscriptions, mark_auto_renewal_attempted
)

from tracker_agent import handle as agent_handle
from menu_button import set_menu_button
from partners import use_partner_promo
from user_settings import get_preferences, update_preferences, get_goals, update_goals, track_activity
from reminders import create_reminder, get_user_reminders, delete_reminder, toggle_reminder, format_reminder_time, get_due_reminders
from notifications import get_users_for_notification, can_send_notification, mark_notification_sent
from motivation_messages import generate_motivation_message
from referrals import bind_user_to_trainer, bind_user_to_trainer_id, get_user_trainer, get_price_promo
from stats_enhanced import (
    generate_streak_stats, generate_streak_summary_chart, 
    generate_streak_chart, generate_timeline_chart,
    generate_weekly_distribution_chart, generate_stats_summary_text
)
import traceback


from io import BytesIO


# YC_STT_INLINE_V1
import os
import aiohttp

YC_IAM_TOKEN = os.getenv("YC_IAM_TOKEN", "").strip()
YC_API_KEY = os.getenv("YC_API_KEY", "").strip()
YC_STT_LANG = os.getenv("YC_STT_LANG", "ru-RU").strip()
STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"

class YandexSTTError(RuntimeError):
    pass

async def stt_oggopus(ogg_bytes: bytes, lang: str | None = None) -> str:
    # Поддерживаем два способа авторизации: IAM-токен (предпочтительно) или API-ключ
    if not YC_IAM_TOKEN and not YC_API_KEY:
        raise YandexSTTError("YC_IAM_TOKEN или YC_API_KEY не установлены (проверьте .env и перезапустите бота)")
    
    params = {"lang": (lang or YC_STT_LANG or "ru-RU"), "format": "oggopus"}
    
    # Используем IAM-токен, если он есть, иначе API-ключ
    if YC_IAM_TOKEN:
        headers = {"Authorization": f"Bearer {YC_IAM_TOKEN}"}
    else:
        headers = {"Authorization": f"Api-Key {YC_API_KEY}"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(STT_URL, params=params, data=ogg_bytes, headers=headers) as r:
            if r.status != 200:
                # Обработка ошибок
                try:
                    error_data = await r.json(content_type=None)
                    error_msg = error_data.get("error_message", str(error_data))
                    error_code = error_data.get("error_code", "UNKNOWN")
                    raise YandexSTTError(f"HTTP {r.status} ({error_code}): {error_msg}")
                except Exception:
                    body = await r.text()
                raise YandexSTTError(f"HTTP {r.status}: {body}")
            
            # Успешный ответ
            try:
                data = await r.json(content_type=None)
            except Exception as e:
                body = await r.text()
                raise YandexSTTError(f"Bad JSON: {body} ({e})")

    text = (data.get("result") or "").strip()
    if not text:
        raise YandexSTTError(f"Empty result: {data}")
    return text

# menu_kb удалена - кнопки под строкой ввода отключены


BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = (os.environ.get("WEBAPP_URL") or "").strip() or "https://sport-helper-robot.online/tracker.html"

dp = Dispatcher()





@dp.message(Command("promo"))
async def cmd_promo(message: types.Message):
    """Улучшенная система промокодов с партнерской программой"""
    parts = (message.text or "").split(maxsplit=1)
    code = (parts[1].strip().upper() if len(parts) > 1 else "").strip()
    
    if not code:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Ввести промокод", switch_inline_query_current_chat="/promo ")
        ]])
        await message.answer(
            "🎟 **Промокод**\n\n"
            "Введи промокод командой:\n"
            "`/promo КОД`\n\n"
            "Или просто отправь мне сообщение с промокодом.",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return
    
    uid = message.from_user.id
    
    # 1. Проверяем партнерские промокоды (7 дней)
    success, msg, days = use_partner_promo(code, uid)
    if success:
        # Активируем подписку на 7 дней
        activate_paid(uid, days)
        await message.answer(
            f"✅ {msg}\n\n"
            f"Теперь у тебя полный доступ к боту на {days} дней! 🎉"
        )
        return
    
    if msg and "уже использовали" not in msg:
        # Промокод не найден в партнерских, пробуем старые
        code_lower = code.lower()
        if code_lower in PAY_PROMO_CODES:
            grant_promo_user(uid)
            await message.answer(
                "✅ Промокод принят!\n\n"
                "Доступ без ограничений активирован. 🎉"
            )
            return

    # Тренерские промокоды с оплатой по сумме
    price_promo = get_price_promo(code)
    if price_promo and price_promo.get("is_active"):
        if price_promo.get("used_by_user_id"):
            await message.answer("❌ Этот промокод уже использован.")
            return
        trainer_id = price_promo.get("trainer_id")
        if trainer_id:
            ok, msg, _ = bind_user_to_trainer_id(uid, trainer_id, code)
            if not ok and "уже привязан" not in msg:
                await message.answer(f"⚠️ {msg}")
                return
        amount = price_promo.get("amount_rub") or 0
        try:
            url, pid = await yk_create_payment_amount(
                uid,
                amount_rub=amount,
                description=f"Оплата по промокоду {code}",
                metadata={"promo_code": code, "amount_rub": str(amount)}
            )
        except Exception as e:
            await message.answer(f"⚠️ Не удалось создать платеж: {e}")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {int(amount)}₽", url=url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"checkpay:{pid}")]
        ])
        await message.answer(
            "Оплата по промокоду:\n"
            "1) Нажми «Оплатить»\n"
            "2) После оплаты вернись сюда и нажми «Проверить оплату»",
            reply_markup=kb
        )
        return
    
    # Промокод не найден
    await message.answer(
        f"❌ {msg if msg else 'Промокод не найден'}\n\n"
        "Проверь правильность написания промокода."
    )

@dp.message(Command("privacy"))
async def cmd_privacy(message: types.Message):
    await message.answer(
        "Политика конфиденциальности:\n"
        "https://sport-helper-robot.online/privacy_policy.html"
    )

@dp.message(Command("terms"))
async def cmd_terms(message: types.Message):
    await message.answer(
        "Пользовательское соглашение:\n"
        "https://sport-helper-robot.online/terms.html\n\n"
        "Публичная оферта:\n"
        "https://sport-helper-robot.online/offer.html\n\n"
        "Согласие на обработку данных:\n"
        "https://sport-helper-robot.online/consent.html"
    )

# WEBAPP_MODE_SWITCH_V1
def _set_mode(uid: int, mode: str):
    try:
        USER_MODE[uid] = mode
    except Exception:
        pass

def _mode_text(mode: str) -> str:
    if mode == "workouts":
        return ("🏋️ Запись подходов включена\n\n"
                "Напиши упражнение и цифры: жим 3х8 60кг, присед 5х5 80кг")
    if mode == "meals":
        return ("🍽️ Запись питания включена\n\n"
                "Напиши приемы пищи: завтрак — …, обед — …, ужин — …")
    if mode == "plan":
        return ("🗓️ План включен\n\n"
                "Напиши: составь план на завтра / на неделю")
    return "✅ Режим обновлён"

# REPLY_NORMALIZE_V1
def _reply_text(out) -> str:
    # aiogram message.answer ждёт строку
    if out is None:
        return ""
    if isinstance(out, str):
        return out
    if isinstance(out, dict):
        v = out.get('reply') or out.get('text') or out.get('message') or ""
        return v if isinstance(v, str) else str(v)
    return str(out)


# Команды /1, /2, /3 удалены

# Обработка web_app_data cmd:/1, /2, /3 удалена



# MODE_KB_V2
USER_MODE: dict[int, str] = {}  # 'sets' | 'meals' | 'plan'

# main_kb удалена - кнопки под строкой ввода отключены



# MODE_MAP_V1
# USER_MODE используется для хранения режима пользователя (если нужно)
USER_MODE: dict[int, str] = {}
REFERRAL_PENDING: set[int] = set()

def _welcome_text() -> str:
    return (
        "Привет! 😊 Я твой личный фитнес-тренер в Telegram.\n\n"
        "Я могу:\n"
        "🏋️‍♂️ фиксировать результаты и прогресс\n"
        "🍽️ помогать с рационом и диетой\n"
        "📅 составлять планы тренировок\n"
        "🎤 принимать и разбирать голосовые сообщения\n\n"
        "С чего начнём? Могу составить план тренировок на сегодня и завтра 💪\n"
        "Или просто пришли мне голосовое — разберёмся по ходу 😉"
    )

def webapp_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])

@dp.message(Command("start", "open"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id if message.from_user else 0
    if uid and not get_user_trainer(uid):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎟️ Ввести промокод", callback_data="referral_enter"),
            InlineKeyboardButton(text="Продолжить", callback_data="referral_skip")
        ]])
        await message.answer(
            "У тебя есть промокод от тренера? Введи его, чтобы закрепиться за ним.",
            reply_markup=kb
        )
        return
    await message.answer(_welcome_text(), reply_markup=webapp_kb())

@dp.callback_query(F.data == "referral_enter")
async def referral_enter(cb: CallbackQuery):
    uid = cb.from_user.id if cb.from_user else 0
    if uid:
        REFERRAL_PENDING.add(uid)
    await cb.message.answer("Введи промокод от тренера (пример: TRAINER1).")
    await cb.answer()

@dp.callback_query(F.data == "referral_skip")
async def referral_skip(cb: CallbackQuery):
    await cb.message.answer(_welcome_text(), reply_markup=webapp_kb())
    await cb.answer()

# Команды /1, /2, /3, /0 удалены


# VOICE_STT_V1
@dp.message(F.voice)
async def on_voice(message: Message):
    import re
    import logging
    from io import BytesIO

    uid = message.from_user.id if message.from_user else 0
    v = message.voice

    # лимиты синхронного STT
    if getattr(v, "duration", 0) and v.duration > 30:
        await message.answer("⏱️ Голосовое слишком длинное (до 30 сек). Запиши короче 🙏")
        return
    if getattr(v, "file_size", 0) and v.file_size > 1024 * 1024:
        await message.answer("📦 Голосовое слишком тяжёлое (до 1 MB). Запиши короче 🙏")
        return

    try:
        buf = BytesIO()
        await message.bot.download(v, destination=buf)
        ogg_bytes = buf.getvalue()

        text = await stt_oggopus(ogg_bytes)
        text = (text or "").strip()
        if not text:
            await message.answer("⚠️ Ничего не распознал.")
            return

        await message.answer(f"🎙️ Я услышал: {text}")
        
        # Сразу показываем typing indicator
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Улучшенная система определения режима для голосовых сообщений
        from intent_classifier import get_mode_hint, classify_intent
        
        mode = USER_MODE.get(uid, "") if "USER_MODE" in globals() else ""
        
        # Используем классификатор намерений
        intent, confidence = classify_intent(text, mode)
        suggested_mode = get_mode_hint(text, mode)
        
        if suggested_mode:
            mode = suggested_mode
            if "USER_MODE" in globals():
                USER_MODE[uid] = mode

        if get_user_trainer(uid) and mode == "plan":
            await message.answer("📌 План тебе назначает тренер. Ты не можешь создавать новый план.")
            return

        # чистим "воду"
        cleaned = re.sub(r"\b(пожалуйста|запиши|записать|в дневник|в мой дневник|сегодня)\b", "", text, flags=re.I)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        text_to_save = cleaned if cleaned else text

        out = await agent_handle(user_id=uid, text=text_to_save, mode_hint=mode)
        await message.answer(_reply_text(out) or "✅ Готово.")
    except YandexSTTError as e:
        await message.answer(f"⚠️ Не смог распознать: {e}")
    except Exception as e:
        logging.exception("VOICE_SAVE_FAILED")
        await message.answer(f"⚠️ Распознал, но не смог записать: {type(e).__name__}: {e}")

# ВАЖНО: Обработчики команд должны быть ПЕРЕД on_text!
# Переместим их сюда, чтобы они обрабатывались первыми

@dp.message(Command("status"))
async def _paywall_status(message: Message):
    uid = message.from_user.id if message.from_user else 0
    await message.answer(status_text(uid))

@dp.message(Command("pay"))
async def _paywall_pay(message: Message):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    uid = message.from_user.id if message.from_user else 0
    logger.info(f"🔵🔵🔵 Command /pay received from user {uid} - ОБРАБОТЧИК ВЫЗВАН!")
    
    try:
        logger.info(f"🔵 Creating payment for user {uid}")
        try:
            url, pid = await yk_create_payment(uid, description=f"Подписка {PAY_PRICE_RUB}₽ на 30 дней")
            logger.info(f"🔵 Payment created successfully: {pid}, URL: {url[:50]}...")
        except Exception as payment_error:
            logger.error(f"🔴 ERROR in yk_create_payment: {payment_error}", exc_info=True)
            raise
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {PAY_PRICE_RUB}₽", url=url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"checkpay:{pid}")]
        ])
        await message.answer(
            "Оплата подписки:\n"
            "1) Нажми «Оплатить»\n"
            "2) После оплаты вернись сюда и нажми «Проверить оплату»",
            reply_markup=kb
        )
        logger.info(f"🔵 Payment message sent to user {uid}")
    except Exception as e:
        logger.error(f"🔴 Error in /pay handler: {e}", exc_info=True)
        error_msg = str(e)
        if "YK_SHOP_ID" in error_msg or "YK_SECRET_KEY" in error_msg or "Не заданы" in error_msg:
            await message.answer(
                "⚠️ Оплата пока не настроена.\n\n"
                "Проверьте настройки YooKassa в .env файле:\n"
                "- YK_SHOP_ID\n"
                "- YK_SECRET_KEY\n\n"
                "После настройки перезапустите бота."
            )
        else:
            await message.answer(
                f"⚠️ Ошибка при создании платежа: {error_msg}\n\n"
                "Попробуйте позже или обратитесь в поддержку."
            )

@dp.message(F.text)
async def on_text(message: types.Message):
    # Пропускаем команды - они обрабатываются отдельными обработчиками
    # ВАЖНО: Этот обработчик должен быть ПОСЛЕ всех обработчиков команд!
    txt = (message.text or "").strip()
    if txt.startswith("/"):
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ on_text получил команду {txt}, но должен был обработаться другим обработчиком!")
        return  # Команды обрабатываются отдельными обработчиками
    
    uid = message.from_user.id if message.from_user else 0
    if uid in REFERRAL_PENDING:
        if txt.lower() in {"пропустить", "skip"}:
            REFERRAL_PENDING.discard(uid)
            await message.answer("Ок, продолжаем без промокода.")
            await message.answer(_welcome_text(), reply_markup=webapp_kb())
            return
        ok, msg, _trainer_id = bind_user_to_trainer(uid, txt)
        if ok:
            REFERRAL_PENDING.discard(uid)
            await message.answer(f"✅ {msg}")
            await message.answer(_welcome_text(), reply_markup=webapp_kb())
        else:
            await message.answer(f"⚠️ {msg}. Попробуй ещё раз или напиши «пропустить».")
        return

    # PROMO_ACCESS_GUARD_V1
    username = message.from_user.username if message.from_user else None
    
    # Безлимитный доступ для @sigidingo
    if username and username.lower() == "sigidingo":
        # Пропускаем проверку лимита для @sigidingo
        pass
    else:
        allowed, remaining = check_and_hit(uid)
        if not allowed:
            await message.answer(
                "🔒 Бесплатный лимит (15 сообщений) закончился.\n\n"
                f"💳 Подписка: {PAY_PRICE_RUB}₽/мес\n"
                "Нажми /pay чтобы оплатить подписку и продолжить использование."
            )
            return
    # (remaining можно показывать при желании)
    # MODE_GUARD_V2
    # Команды уже обработаны выше, здесь только обычный текст
    user_text = (getattr(message, 'text', None) or '').strip()
    uid = message.from_user.id
    
    # Сразу показываем typing indicator для мгновенной обратной связи
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Улучшенная система определения режима
        from intent_classifier import get_mode_hint, classify_intent
        
        # Классифицируем намерение пользователя
        intent, confidence = classify_intent(message.text, USER_MODE.get(uid))
        
        # Определяем mode_hint с учетом классификации
        suggested_mode = get_mode_hint(message.text, USER_MODE.get(uid))
        
        # Если классификатор уверен (confidence >= 0.5), обновляем режим
        if confidence >= 0.5 and suggested_mode:
            USER_MODE[uid] = suggested_mode
            mode = suggested_mode
        else:
            mode = USER_MODE.get(uid)

        if get_user_trainer(uid) and mode == "plan":
            await message.answer("📌 План тебе назначает тренер. Ты не можешь создавать новый план.")
            return

        out = await agent_handle(user_id=uid, text=message.text, mode_hint=(mode or ""))
        reply = (out.get("reply") or "").strip()
        if not reply:
            reply = "Ок."
        await message.answer(reply)
    except Exception as e:

        traceback.print_exc()

        await message.answer("⚠️ Ошибка. Попробуй ещё раз.\nЕсли повторится — скажи, я посмотрю логи.")

async def check_and_renew_subscriptions(bot: Bot):
    """Проверяет подписки и отправляет уведомления о необходимости продления"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Получаем пользователей, у которых подписка истекает через 3 дня
        expiring = get_expiring_subscriptions(days_before=3)
        logger.info(f"🔍 Найдено {len(expiring)} подписок, истекающих через 3 дня")
        
        for user_id, paid_until in expiring:
            try:
                # Проверяем, не создан ли уже платеж для этого пользователя
                _, _, pending = get_state(user_id)
                if pending:
                    logger.info(f"⏭️ Для user {user_id} уже есть pending платеж, пропускаем")
                    continue
                
                # Создаем платеж для автоматического продления
                try:
                    url, pid = await yk_create_payment(
                        user_id, 
                        description=f"Автоматическое продление подписки на 30 дней"
                    )
                    mark_auto_renewal_attempted(user_id, pid)
                    
                    # Отправляем уведомление пользователю
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"💳 Оплатить {PAY_PRICE_RUB}₽", url=url)],
                        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"checkpay:{pid}")]
                    ])
                    
                    from datetime import datetime, timezone
                    expire_date = datetime.fromtimestamp(paid_until, tz=timezone.utc).astimezone().strftime("%d.%m.%Y")
                    
                    await bot.send_message(
                        user_id,
                        f"📅 Ваша подписка истекает {expire_date}\n\n"
                        f"💳 Для автоматического продления нажмите кнопку ниже.\n"
                        f"После оплаты подписка будет продлена на 30 дней.",
                        reply_markup=kb
                    )
                    logger.info(f"✅ Отправлено уведомление о продлении для user {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при создании платежа для user {user_id}: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке user {user_id}: {e}")
        
        # Проверяем истекшие подписки (отправляем напоминание)
        expired = get_expired_subscriptions()
        logger.info(f"🔍 Найдено {len(expired)} истекших подписок")
        
        for user_id in expired:
            try:
                # Проверяем, не создан ли уже платеж
                _, _, pending = get_state(user_id)
                if pending:
                    continue
                
                # Создаем платеж для продления
                try:
                    url, pid = await yk_create_payment(
                        user_id,
                        description=f"Продление подписки на 30 дней"
                    )
                    mark_auto_renewal_attempted(user_id, pid)
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"💳 Оплатить {PAY_PRICE_RUB}₽", url=url)],
                        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"checkpay:{pid}")]
                    ])
                    
                    await bot.send_message(
                        user_id,
                        f"⏰ Ваша подписка истекла.\n\n"
                        f"💳 Для продолжения использования оплатите подписку.\n"
                        f"После оплаты подписка будет активирована на 30 дней.",
                        reply_markup=kb
                    )
                    logger.info(f"✅ Отправлено напоминание об истекшей подписке для user {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при создании платежа для user {user_id}: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке истекшей подписки user {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в check_and_renew_subscriptions: {e}", exc_info=True)

async def subscription_renewal_scheduler(bot: Bot):
    """Периодически проверяет подписки и отправляет уведомления"""
    import logging
    import asyncio
    logger = logging.getLogger(__name__)
    
    while True:
        try:
            await asyncio.sleep(3600)  # Проверяем каждый час
            await check_and_renew_subscriptions(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_renewal_scheduler: {e}", exc_info=True)
            await asyncio.sleep(60)  # При ошибке ждем минуту перед повтором

async def send_motivation_notifications(bot: Bot):
    """Отправляет мотивирующие уведомления пользователям"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        users = get_users_for_notification()
        logger.info(f"🔔 Проверяю {len(users)} пользователей для отправки уведомлений")
        
        for user_id in users:
            try:
                can_send, reason = can_send_notification(user_id)
                if not can_send:
                    logger.debug(f"⏭️ Пропускаю user {user_id}: {reason}")
                    continue
                
                # Генерируем мотивирующее сообщение
                message = await generate_motivation_message(user_id)
                if not message:
                    logger.warning(f"⚠️ Не удалось сгенерировать сообщение для user {user_id}")
                    continue
                
                # Отправляем сообщение
                await bot.send_message(user_id, message)
                mark_notification_sent(user_id)
                logger.info(f"✅ Отправлено уведомление user {user_id}")
                
                # Небольшая задержка между отправками
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке уведомления user {user_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в send_motivation_notifications: {e}", exc_info=True)

async def motivation_notifications_scheduler(bot: Bot):
    """Периодически отправляет мотивирующие уведомления"""
    import logging
    import asyncio
    logger = logging.getLogger(__name__)
    
    # Ждем 5 минут после запуска бота перед первой проверкой
    await asyncio.sleep(300)
    
    while True:
        try:
            await send_motivation_notifications(bot)
            # Проверяем каждые 2 часа
            await asyncio.sleep(7200)
        except Exception as e:
            logger.error(f"❌ Ошибка в motivation_notifications_scheduler: {e}", exc_info=True)
            await asyncio.sleep(300)  # При ошибке ждем 5 минут перед повтором

async def main():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Запуск бота...")
    bot = Bot(token=BOT_TOKEN)  # parse_mode не задаём специально
    logger.info("✅ Bot создан")
    set_menu_button()           # меню-кнопка тоже "Дневник"
    logger.info("✅ Меню-кнопка установлена")

    # Запускаем API для дашборда рефералов (если включено)
    try:
        from referrals_api import app as referral_app, should_start_api
        if should_start_api():
            import uvicorn
            import threading
            port = int(os.getenv("REFERRAL_API_PORT", "8010"))
            def _run_referral_api():
                config = uvicorn.Config(referral_app, host="0.0.0.0", port=port, log_level="info")
                server = uvicorn.Server(config)
                server.run()
            threading.Thread(target=_run_referral_api, daemon=True).start()
            logger.info(f"✅ Referral API запущен на порту {port}")
    except Exception as e:
        logger.error(f"❌ Не удалось запустить Referral API: {e}")
    
    # Запускаем scheduler для автоматического продления подписок
    import asyncio
    asyncio.create_task(subscription_renewal_scheduler(bot))
    logger.info("✅ Scheduler автоматического продления подписок запущен")
    
    # Запускаем scheduler для мотивирующих уведомлений
    asyncio.create_task(motivation_notifications_scheduler(bot))
    logger.info("✅ Scheduler мотивирующих уведомлений запущен")
    
    logger.info("🔄 Начинаю polling...")
    await dp.start_polling(bot)


# MODE_MENU_V2 удален - команды /1, /2, /3, /menu и кнопки отключены

# PAYWALL_V1
import re as _re_paywall
from typing import Any, Awaitable, Callable, Dict

class PaywallMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]], event: Any, data: Dict[str, Any]) -> Any:
        if isinstance(event, Message):
            uid = event.from_user.id if event.from_user else 0
            username = event.from_user.username if event.from_user else None

            # команды не считаем и не блокируем
            txt = (event.text or "").strip()
            if txt.startswith("/"):
                import re
                cmd = re.split(r"[\s@]", txt[1:], 1)[0].lower()
                if cmd in {"start","help","pay","status","open","stats","reminders","remind","promo"}:
                    # Логируем для отладки
                    import logging
                    logging.basicConfig(level=logging.INFO)
                    logging.getLogger(__name__).info(f"🟢 PaywallMiddleware: пропускаем команду /{cmd} для user {uid}")
                    return await handler(event, data)

            # Безлимитный доступ для @sigidingo
            if username and username.lower() == "sigidingo":
                    return await handler(event, data)

            if uid and is_paid(uid):
                return await handler(event, data)

            if uid:
                msg_count, _, _ = get_state(uid)
                if msg_count >= PAY_FREE_LIMIT and not is_promo_user(event.from_user.id):
                    await event.answer(
                        f"🚫 Бесплатный лимит ({PAY_FREE_LIMIT} сообщений) исчерпан.\n"
                        f"💳 Подписка: {PAY_PRICE_RUB}₽/мес\n"
                        f"Нажми /pay чтобы продолжить."
                    )
                    return

                inc_free_count(uid)

        return await handler(event, data)

# подключаем middleware
try:
    dp.message.middleware(PaywallMiddleware())
except Exception:
    pass

# Обработчики Command("status") и Command("pay") перемещены выше, перед on_text

@dp.callback_query(F.data.startswith("checkpay:"))
async def _paywall_checkpay(call: CallbackQuery):
    uid = call.from_user.id if call.from_user else 0
    pid = (call.data or "").split(":", 1)[1].strip()
    ok, text = await yk_check_and_activate(uid, pid)
    if ok:
        await call.message.answer(text)
        await call.answer("Готово ✅", show_alert=False)
    else:
        await call.answer(text, show_alert=True)


# === СТАТИСТИКА ===
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показывает статистику В ударе с красивыми графиками"""
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Команда /stats получена от пользователя {message.from_user.id}")
    
    uid = message.from_user.id if message.from_user else 0
    
    try:
        # Сначала отправляем простое сообщение для проверки
        logger.info("Отправляю сообщение 'Генерирую статистику...'")
        await message.answer("📊 Генерирую статистику...")
        logger.info("Сообщение отправлено")
        
        # Генерируем текстовую сводку
        try:
            summary = generate_stats_summary_text(uid, days=90)
            await message.answer(summary)
        except Exception as e:
            await message.answer(f"⚠️ Ошибка получения статистики: {type(e).__name__}: {e}")
            traceback.print_exc()
            return
        
        # График с метриками В ударе (круговая диаграмма + метрики)
        try:
            summary_chart = generate_streak_summary_chart(uid, days=90)
            if summary_chart:
                await message.answer_photo(summary_chart, caption="🔥 Метрики \"В ударе\"")
        except Exception as e:
            await message.answer(f"⚠️ Ошибка создания графика метрик: {e}")
            traceback.print_exc()
        
        # Календарь активности
        try:
            calendar_chart = generate_streak_chart(uid, days=90)
            if calendar_chart:
                await message.answer_photo(calendar_chart, caption="📅 Календарь активности за 90 дней")
        except Exception as e:
            traceback.print_exc()
        
        # График распределения по дням недели
        try:
            weekly_chart = generate_weekly_distribution_chart(uid, days=90)
            if weekly_chart:
                await message.answer_photo(weekly_chart, caption="📈 Распределение тренировок по дням недели")
        except Exception as e:
            traceback.print_exc()
        
        # Timeline график (за 60 дней для детализации)
        try:
            timeline_chart = generate_timeline_chart(uid, days=60)
            if timeline_chart:
                await message.answer_photo(timeline_chart, caption="⏱️ График активности за последние 60 дней")
        except Exception as e:
            traceback.print_exc()
            
    except Exception as e:
        traceback.print_exc()
        await message.answer(f"⚠️ Неожиданная ошибка: {type(e).__name__}: {e}")


# === НАПОМИНАНИЯ ===
@dp.message(Command("reminders"))
async def cmd_reminders(message: types.Message):
    """Показывает список напоминаний пользователя"""
    uid = message.from_user.id if message.from_user else 0
    
    try:
        reminders_list = get_user_reminders(uid, active_only=False)
        
        if not reminders_list:
            await message.answer("📋 У тебя нет напоминаний.\n\nИспользуй /remind чтобы создать новое напоминание.")
            return
        
        lines = ["📋 Твои напоминания:\n"]
        kb_buttons = []
        
        for i, rem in enumerate(reminders_list, 1):
            status = "✅" if rem["is_active"] else "❌"
            time_str = format_reminder_time(rem["time_hour"], rem["time_minute"], rem["days_of_week"])
            lines.append(f"{i}. {status} {time_str}")
            lines.append(f"   {rem['message']}\n")
            
            kb_buttons.append([
                InlineKeyboardButton(
                    text=f"{'🔕' if rem['is_active'] else '🔔'} {i}",
                    callback_data=f"remind_toggle:{rem['reminder_id']}"
                ),
                InlineKeyboardButton(
                    text=f"❌ {i}",
                    callback_data=f"remind_del:{rem['reminder_id']}"
                )
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None
        
        await message.answer("\n".join(lines), reply_markup=kb)
    except Exception as e:
        traceback.print_exc()
        await message.answer(f"⚠️ Ошибка при получении напоминаний: {e}")


@dp.message(Command("remind"))
async def cmd_remind(message: types.Message):
    """Создает новое напоминание"""
    uid = message.from_user.id if message.from_user else 0
    text = (message.text or "").strip()
    
    # Простой парсинг: /remind 18:00 тренировка
    parts = text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            "📝 Создание напоминания:\n\n"
            "Формат: /remind ЧЧ:ММ сообщение\n\n"
            "Примеры:\n"
            "• /remind 18:00 Тренировка\n"
            "• /remind 09:00 Завтрак\n"
            "• /remind 20:00 Вода"
        )
        return
    
    try:
        time_str = parts[2].strip()
        if ":" not in time_str:
            raise ValueError("Неверный формат времени")
        
        hour_str, minute_str = time_str.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str) if minute_str else 0
        
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Неверное время")
        
        rem_message = parts[3].strip()
        if not rem_message:
            raise ValueError("Сообщение не может быть пустым")
        
        # Создаем ежедневное напоминание
        rem_id = create_reminder(uid, "custom", rem_message, hour, minute, days_of_week=None)
        
        await message.answer(
            f"✅ Напоминание создано!\n\n"
            f"⏰ {format_reminder_time(hour, minute, None)}\n"
            f"📝 {rem_message}\n\n"
            f"Используй /reminders чтобы управлять напоминаниями."
        )
    except (ValueError, IndexError) as e:
        await message.answer(f"❌ Неверный формат: {e}\n\nИспользуй: /remind 18:00 сообщение")
    except Exception as e:
        traceback.print_exc()
        await message.answer(f"⚠️ Ошибка при создании напоминания: {e}")


@dp.callback_query(F.data.startswith("remind_toggle:"))
async def _remind_toggle(call: CallbackQuery):
    uid = call.from_user.id if call.from_user else 0
    rem_id = int((call.data or "").split(":", 1)[1].strip())
    
    try:
        success = toggle_reminder(rem_id, uid)
        if success:
            await call.answer("✅ Напоминание обновлено", show_alert=False)
            # Обновляем список
            await cmd_reminders(types.Message(chat=call.message.chat, from_user=call.from_user))
        else:
            await call.answer("❌ Напоминание не найдено", show_alert=True)
    except Exception as e:
        traceback.print_exc()
        await call.answer(f"⚠️ Ошибка: {e}", show_alert=True)


@dp.callback_query(F.data.startswith("remind_del:"))
async def _remind_del(call: CallbackQuery):
    uid = call.from_user.id if call.from_user else 0
    rem_id = int((call.data or "").split(":", 1)[1].strip())
    
    try:
        success = delete_reminder(rem_id, uid)
        if success:
            await call.answer("✅ Напоминание удалено", show_alert=False)
            # Обновляем список
            await cmd_reminders(types.Message(chat=call.message.chat, from_user=call.from_user))
        else:
            await call.answer("❌ Напоминание не найдено", show_alert=True)
    except Exception as e:
        traceback.print_exc()
        await call.answer(f"⚠️ Ошибка: {e}", show_alert=True)


# Админ-команды партнерской программы удалены

if __name__ == "__main__":
    asyncio.run(main())
