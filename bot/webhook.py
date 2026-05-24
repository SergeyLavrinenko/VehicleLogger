from fastapi import APIRouter, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update


def build_webhook_router(dp: Dispatcher, bot: Bot) -> APIRouter:
    """Создаёт APIRouter с замыканием на bot и dp,
    чтобы оба эндпоинта имели к ним доступ."""
    router = APIRouter()

    @router.post("/api/telegram/webhook")
    async def telegram_webhook(req: Request):
        data = await req.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return {"ok": True}

    @router.post("/send-message")
    async def send_message(data: dict):
        telegram_id = data["telegramId"]
        text = data["text"]
        await bot.send_message(telegram_id, text)
        return {"ok": True}

    return router
