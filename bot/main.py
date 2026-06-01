from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, WEBHOOK_URL, USE_MOCK
from handlers import router as handlers_router
from webhook import build_webhook_router

# Защита от запуска с плейсхолдером — иначе бот молча "работает",
# но Telegram шлёт апдейты на несуществующий домен.
if "your-domain.com" in WEBHOOK_URL or not WEBHOOK_URL.startswith("https://"):
    raise RuntimeError(
        f"WEBHOOK_URL не настроен (сейчас: {WEBHOOK_URL!r}). "
        "Для локальной разработки запускай main_polling.py — не нужен публичный URL. "
        "Для webhook-режима подними ngrok и пропиши WEBHOOK_URL=https://xxx.ngrok-free.app/api/telegram/webhook"
    )

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Запускай так: BOT_TOKEN=<токен_от_BotFather> python main.py"
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(handlers_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Сообщаем Telegram, куда слать апдейты
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    mode = "MOCK (захардкоженные данные)" if USE_MOCK else "REAL (HTTP к бэкенду)"
    print(f"🚀 Bot started, webhook set to: {WEBHOOK_URL}. Источник данных: {mode}")
    yield
    # Корректное завершение
    await bot.delete_webhook()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)
app.include_router(build_webhook_router(dp, bot))


if __name__ == "__main__":
    # ВАЖНО: передаём объект app, а не строку "main:app",
    # иначе uvicorn повторно импортирует модуль и роутер
    # попытается прицепиться к диспетчеру дважды.
    uvicorn.run(app, host="0.0.0.0", port=8000)
