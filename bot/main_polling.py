"""Запуск бота в режиме long polling — для локальной разработки.

Не требует публичного URL и webhook. Бот сам опрашивает Telegram
каждую секунду и получает новые сообщения.

Запуск:
    # с mock-данными (без бэкенда) — по умолчанию:
    BOT_TOKEN=xxx python main_polling.py

    # с реальным бэкендом:
    BOT_TOKEN=xxx USE_MOCK=false python main_polling.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, USE_MOCK
from handlers import router as handlers_router

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

    mode = "MOCK (захардкоженные данные)" if USE_MOCK else "REAL (HTTP к бэкенду)"
    print(f"🚀 Бот запущен в режиме polling. Источник данных: {mode}. Ctrl+C для остановки.")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
