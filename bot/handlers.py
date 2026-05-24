from aiogram import Router, types
from aiogram.filters import Command, CommandObject

# Импортируем APIClient из пакета services — там автоматически выбирается
# либо реальный HTTP-клиент, либо MockAPIClient, в зависимости от USE_MOCK.
from services import APIClient

router = Router()


@router.message(Command("start"))
async def start_handler(message: types.Message):
    telegram_id = message.from_user.id
    try:
        await APIClient.register_driver(telegram_id)
        await message.answer("✅ Вы зарегистрированы в системе")
    except Exception as e:
        print("register_driver error:", e)
        await message.answer("❌ Ошибка регистрации")


@router.message(Command("refuel"))
async def refuel_handler(message: types.Message, command: CommandObject):
    # command.args — это всё, что идёт после самой команды (без префикса /refuel
    # и без возможного @BotName). Это надёжнее, чем message.text.split().
    if not command.args:
        await message.answer("❌ Формат: /refuel <литры> <цена>")
        return

    parts = command.args.split()
    if len(parts) != 2:
        await message.answer("❌ Формат: /refuel <литры> <цена>")
        return

    try:
        liters = float(parts[0])
        price = float(parts[1])
    except ValueError:
        await message.answer("❌ Литры и цена должны быть числами. Пример: /refuel 50 4500")
        return

    try:
        await APIClient.send_refuel(
            telegram_id=message.from_user.id,
            liters=liters,
            price=price,
        )
        await message.answer(f"⛽ Заправка: {liters}л на {price}")
    except Exception as e:
        print("send_refuel error:", e)
        await message.answer("❌ Ошибка при сохранении заправки")


@router.message(Command("status"))
async def status_handler(message: types.Message):
    try:
        data = await APIClient.get_status(message.from_user.id)
        text = (
            "🚛 Статус:\n"
            f"🌡 Температура: {data.get('temp', 'N/A')}°C\n"
            f"🔄 Обороты: {data.get('rpm', 'N/A')}\n"
            f"⛽ Топливо: {data.get('fuel', 'N/A')}%"
        )
        await message.answer(text)
    except Exception as e:
        print("get_status error:", e)
        await message.answer("❌ Ошибка получения статуса")


@router.message(Command("alerts"))
async def alerts_handler(message: types.Message):
    try:
        alerts = await APIClient.get_alerts(message.from_user.id)
        if not alerts:
            await message.answer("✅ Нет предупреждений")
        else:
            # Приводим элементы к строкам на случай, если бэкенд вернёт dict'ы:
            # join по списку нестрок упадёт с TypeError.
            lines = [a if isinstance(a, str) else str(a) for a in alerts]
            text = "⚠️ Предупреждения:\n\n" + "\n".join(lines)
            await message.answer(text)
    except Exception as e:
        print("get_alerts error:", e)
        await message.answer("❌ Ошибка получения алертов")
