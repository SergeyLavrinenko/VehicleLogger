import os

# Токен бота. НИКОГДА не коммить реальный токен в код — только через переменную
# окружения. Если ранее токен был захардкожен — сбрось его через @BotFather (/revoke)
# и получи новый.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# URL бэкенд-API. По умолчанию указан плейсхолдер — реальный адрес передавай через env.
BASE_API_URL = os.getenv("BASE_API_URL", "https://91.188.212.119")

# URL вебхука для prod-режима (используется только в main.py, не в main_polling.py).
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com/api/telegram/webhook")

# Режим mock-данных: если True — APIClient подменяется на заглушку с захардкоженными
# данными, бэкенд не вызывается. Удобно для локальной разработки и тестирования бота
# без поднятия инфраструктуры.
#
# Включить:  USE_MOCK=true python main_polling.py
# Выключить: USE_MOCK=false python main_polling.py   (или просто не задавать)
USE_MOCK = os.getenv("USE_MOCK", "true").lower() in ("1", "true", "yes", "on")

# ── HTTP-сервер уведомлений (бэкенд → бот) ───────────────────────────────
# В polling-режиме бот дополнительно поднимает маленький HTTP-сервер, чтобы
# основной бэкенд мог присылать сообщения водителям (алерты по фуре).
# Это внутренний сервис между контейнерами — наружу порт не публикуется.
NOTIFY_HOST = os.getenv("NOTIFY_HOST", "0.0.0.0")
NOTIFY_PORT = int(os.getenv("NOTIFY_PORT", "8081"))

# Общий секрет между ботом и бэкендом для эндпоинта /send-message.
# Если пусто — проверка ключа отключена.
BOT_NOTIFY_KEY = os.getenv("BOT_NOTIFY_KEY", "")
