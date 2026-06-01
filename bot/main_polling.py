"""Запуск бота в режиме long polling — для локальной разработки и Docker.

Бот сам опрашивает Telegram (getUpdates) и параллельно поднимает лёгкий
HTTP-сервер уведомлений, через который основной бэкенд присылает алерты
водителям (см. notify_server.py).

Запуск:
    # с mock-данными (без бэкенда) — по умолчанию:
    BOT_TOKEN=xxx python main_polling.py

    # с реальным бэкендом:
    BOT_TOKEN=xxx USE_MOCK=false BASE_API_URL=http://localhost:5000 python main_polling.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, USE_MOCK, NOTIFY_HOST, NOTIFY_PORT
from handlers import router as handlers_router
from notify_server import build_notify_server

logging.basicConfig(level=logging.INFO)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не задан. Запускай так: BOT_TOKEN=<токен_от_BotFather> python main_polling.py"
        )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers_router)

    # Если ранее был установлен webhook — снимаем его,
    # иначе getUpdates (polling) ругнётся, что webhook активен.
    await bot.delete_webhook(drop_pending_updates=True)

    # HTTP-сервер уведомлений (бэкенд → бот) — работает рядом с поллингом.
    notify_server = build_notify_server(bot)

    mode = "MOCK (захардкоженные данные)" if USE_MOCK else "REAL (HTTP к бэкенду)"
    print(f"🚀 Бот запущен в режиме polling. Источник данных: {mode}. Ctrl+C для остановки.")
    print(f"📡 Сервер уведомлений слушает http://{NOTIFY_HOST}:{NOTIFY_PORT}/send-message")

    try:
        # Поллинг и HTTP-сервер крутятся в одном event loop.
        # Если любая из задач упадёт — поднимется исключение и оба остановятся.
        await asyncio.gather(
            dp.start_polling(bot),
            notify_server.serve(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
