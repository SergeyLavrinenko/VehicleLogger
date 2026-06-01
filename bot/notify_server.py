"""HTTP-сервер уведомлений (бэкенд → бот).

В polling-режиме бот не имеет своего веб-сервера: эндпоинт /send-message
из webhook.py поднимается только в webhook-режиме (main.py). Этот модуль
даёт лёгкий HTTP-сервер, который запускается ПАРАЛЛЕЛЬНО с поллингом,
чтобы основной бэкенд мог присылать сообщения водителям (алерты по фуре).

Это внутренний сервис между контейнерами — публичный URL и HTTPS ему
не нужны, в отличие от Telegram-вебхука.
"""
import logging
from typing import Optional

import uvicorn
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import FastAPI, Header, HTTPException

from config import NOTIFY_HOST, NOTIFY_PORT, BOT_NOTIFY_KEY

log = logging.getLogger("notify")


def build_notify_server(bot: Bot) -> uvicorn.Server:
    """Собирает uvicorn.Server с эндпоинтом /send-message.
    Возвращённый объект запускается через `await server.serve()`."""
    app = FastAPI(title="VehicleLogger Bot — Notify API")

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/send-message")
    async def send_message(
        data: dict,
        x_bot_key: Optional[str] = Header(default=None),
    ):
        # Проверка общего секрета. Если BOT_NOTIFY_KEY не задан — проверка
        # отключена (удобно для локального запуска без настройки).
        if BOT_NOTIFY_KEY and x_bot_key != BOT_NOTIFY_KEY:
            raise HTTPException(status_code=401, detail="bad bot key")

        telegram_id = data.get("telegramId")
        text = data.get("text")
        if telegram_id is None or not text:
            raise HTTPException(status_code=400, detail="telegramId and text required")

        try:
            await bot.send_message(telegram_id, text)
        except TelegramAPIError as e:
            # Типовая причина — водитель ещё не нажал /start, и бот
            # не имеет права писать ему первым.
            log.warning("Не удалось отправить сообщение %s: %s", telegram_id, e)
            raise HTTPException(status_code=502, detail=str(e))

        return {"ok": True}

    config = uvicorn.Config(
        app,
        host=NOTIFY_HOST,
        port=NOTIFY_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # Сигналами (Ctrl+C / SIGTERM) пусть управляет общий event loop, а не
    # uvicorn — иначе при остановке uvicorn завершится, а поллинг повиснет.
    server.install_signal_handlers = lambda: None

    return server
