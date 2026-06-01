FROM python:3.12-slim
WORKDIR /app

# Зависимости отдельным слоем — кэшируется, пока не меняется requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Polling-режим: бот сам опрашивает Telegram, входящий порт не нужен.
CMD ["python", "main_polling.py"]
