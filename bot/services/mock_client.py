"""Заглушка APIClient с захардкоженными данными.

Используется, когда бэкенд недоступен — позволяет тестировать бота локально
без поднятия инфраструктуры. Имеет такой же интерфейс, как и реальный APIClient
в api_client.py, поэтому подменяется бесшовно.

Активируется флагом USE_MOCK=true в окружении (см. config.py).

Дополнительно запускает фоновую задачу, которая раз в N секунд рассылает
случайное предупреждение всем "зарегистрированным" (вызвавшим /start)
пользователям. Частота настраивается переменной окружения:

    MOCK_ALERT_INTERVAL_SECONDS=10     # раз в 10 сек
    MOCK_ALERT_INTERVAL_SECONDS=0      # рассылка отключена

По умолчанию — 30 секунд.

Реализация специально не требует правок handlers.py / main*.py: фоновая
задача подвешивается через monkey-patch методов Bot.set_webhook /
Bot.delete_webhook, которые точки входа вызывают на старте в async-контексте.
Без USE_MOCK=true этот модуль вообще не импортируется (см. services/__init__.py),
поэтому реальный режим не затрагивается.
"""
import asyncio
import os
import random

from aiogram import Bot


# ===== "Хранилище" в памяти процесса =====
# Переживает между вызовами в рамках одной сессии бота, обнуляется при рестарте.
_registered_drivers: set[int] = set()
_refuels: list[dict] = []


# ===== Пул сообщений и настройки авто-рассылки =====
_ALERTS_POOL = [
    "🔥 Температура двигателя выше нормы",
    "⛽ Низкий уровень топлива (<20%)",
    "🛢 Пора заменить масло",
    "🛞 Давление в шинах ниже нормы",
    "🔋 Низкий заряд АКБ",
    "📍 Отклонение от маршрута",
    "💨 Превышение скорости",
    "🚨 Резкое торможение",
    "❄️ Низкая температура охлаждающей жидкости",
    "🛠 Требуется плановое ТО (пробег)",
]

# Интервал авто-рассылки в секундах. 0 или отрицательное — рассылка выключена.
try:
    _ALERT_INTERVAL_SECONDS = int(os.getenv("MOCK_ALERT_INTERVAL_SECONDS", "30"))
except ValueError:
    print("[mock] ⚠️  MOCK_ALERT_INTERVAL_SECONDS не число, использую 30")
    _ALERT_INTERVAL_SECONDS = 30


class MockAPIClient:
    """Возвращает захардкоженные / случайно-варьирующиеся данные вместо HTTP-запросов."""

    @staticmethod
    async def register_driver(telegram_id: int):
        await asyncio.sleep(0.05)  # имитация сетевой задержки
        _registered_drivers.add(telegram_id)
        print(f"[mock] register_driver({telegram_id}) -> ok")
        return {"ok": True, "driverId": telegram_id}

    @staticmethod
    async def send_refuel(telegram_id: int, liters: float, price: float):
        await asyncio.sleep(0.05)
        _refuels.append({"telegramId": telegram_id, "liters": liters, "price": price})
        print(f"[mock] send_refuel({telegram_id}, {liters}л, {price}) -> ok")
        return {"ok": True, "id": len(_refuels)}

    @staticmethod
    async def get_status(telegram_id: int):
        await asyncio.sleep(0.05)
        data = {
            "temp": round(random.uniform(75, 95), 1),
            "rpm": random.randint(1200, 2400),
            "fuel": random.randint(15, 95),
        }
        print(f"[mock] get_status({telegram_id}) -> {data}")
        return data

    @staticmethod
    async def get_alerts(telegram_id: int):
        await asyncio.sleep(0.05)
        alerts = random.sample(_ALERTS_POOL, k=random.randint(0, 3))
        print(f"[mock] get_alerts({telegram_id}) -> {alerts}")
        return alerts


# ===== Фоновая рассылка =====

_broadcast_task: asyncio.Task | None = None


async def _broadcast_loop(bot: Bot) -> None:
    """Периодически шлёт случайный алерт каждому зарегистрированному пользователю."""
    print(
        f"[mock] 📢 авто-рассылка запущена: интервал {_ALERT_INTERVAL_SECONDS}с, "
        f"пул из {len(_ALERTS_POOL)} сообщений"
    )
    while True:
        try:
            await asyncio.sleep(_ALERT_INTERVAL_SECONDS)
            if not _registered_drivers:
                # Никто не сделал /start — пропускаем итерацию (не спамим в пустоту).
                continue
            alert = random.choice(_ALERTS_POOL)
            text = f"⚠️ Авто-уведомление\n{alert}"
            # list(...) — копия, чтобы не падать, если множество меняется во время итерации
            for driver_id in list(_registered_drivers):
                try:
                    await bot.send_message(driver_id, text)
                except Exception as e:
                    # Самое частое: пользователь не нажимал /start у этого бота,
                    # или заблокировал его. Удалять не будем — для mock-сценария ок.
                    print(f"[mock] не удалось отправить алерт {driver_id}: {e}")
        except asyncio.CancelledError:
            print("[mock] 📢 авто-рассылка остановлена")
            raise
        except Exception as e:
            # Не даём циклу умереть из-за единичной ошибки — пишем и идём дальше.
            print(f"[mock] ошибка в цикле рассылки: {e}")


def _ensure_broadcaster_running(bot: Bot) -> None:
    """Запускает фоновую задачу один раз. Идемпотентно."""
    global _broadcast_task
    if _ALERT_INTERVAL_SECONDS <= 0:
        return  # рассылка выключена настройкой
    if _broadcast_task is not None and not _broadcast_task.done():
        return  # уже запущена
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Event loop ещё не запущен — попробуем при следующем вызове.
        return
    _broadcast_task = loop.create_task(_broadcast_loop(bot))


# ----- Подцепляемся к жизненному циклу Bot без правок внешних файлов -----
# set_webhook вызывается из main.py во время FastAPI lifespan,
# delete_webhook — из main_polling.py перед стартом long-polling.
# Обе точки гарантированно исполняются в async-контексте, и каждая из них —
# первая awaitable-операция на bot в своей точке входа. Это идеальный момент,
# чтобы один раз поднять broadcaster, получив реальный экземпляр Bot.
_original_set_webhook = Bot.set_webhook
_original_delete_webhook = Bot.delete_webhook


async def _patched_set_webhook(self, *args, **kwargs):
    _ensure_broadcaster_running(self)
    return await _original_set_webhook(self, *args, **kwargs)


async def _patched_delete_webhook(self, *args, **kwargs):
    _ensure_broadcaster_running(self)
    return await _original_delete_webhook(self, *args, **kwargs)


Bot.set_webhook = _patched_set_webhook
Bot.delete_webhook = _patched_delete_webhook
