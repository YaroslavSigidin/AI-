# AI Trainer Cursor

## Что это
Проект Telegram‑бота и веб‑мини‑приложения с личными кабинетами, планами тренировок/питания и реферальной системой.

## Быстрый старт (локально)
1) Клонировать репозиторий
2) Установить зависимости
3) Запустить локальный сервер/бота

Подробности см. в `LOCAL_SETUP.md` и `DOCKER_SETUP.md`.

## Структура проекта (основные файлы)
- `bot.py` — логика Telegram‑бота
- `tracker.html` / `tracker.js` / `tracker.css` — фронт мини‑приложения
- `trainer_dashboard.*` — кабинет тренера
- `referrals_dashboard.*` — админ‑панель рефералов
- `referrals.py` / `referrals_api.py` — реферальный backend
- `paywall.py`, `yookassa_webhook.py` — оплата и вебхуки

## Деплой
Деплой делается через GitHub Actions (workflow `Deploy to TimeWeb`).

## Правила коммитов
Используем Conventional Commits:
- `feat:` новая функциональность
- `fix:` исправление багов
- `ui:` изменения интерфейса
- `refactor:` рефакторинг без изменения поведения
- `docs:` документация
- `chore:` тех. изменения/обновления

Примеры:
- `feat: add trainer login flow`
- `fix: handle missing user id`
- `ui: compact referral dashboard`

## Ветки
- `main` — стабильная версия
- `feature/<name>` — новая функциональность
- `fix/<name>` — исправление багов

