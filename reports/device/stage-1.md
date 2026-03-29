# Устройство (ESP32) — Этап 1: Setup

**Ответственный:** Сергей
**Статус:** Завершён

---

## Задачи этапа

| # | Задача | Статус | Примечание |
|---|--------|--------|------------|
| 1 | Настроить среду разработки (PlatformIO) | Done | ESP-WROOM-32, Arduino framework |
| 2 | Создать проект прошивки в `/firmware` | Done | platformio.ini, config.h, plan.md |
| 3 | Диагностика всех модулей | Done | Wi-Fi, MPU-6050, CAN/TWAI, GPS — всё OK |
| 4 | Тестовый стенд с веб-дашбордом | Done | firmware-test/, веб-интерфейс с графиками |
| 5 | Проектирование провизионинга | Done | firmware/PROVISIONING.md |
| 6 | Документация API | Done | docs/api.html |

Задачи по отправке телеметрии на бэкенд (POST /api/telemetry, heartbeat, X-Device-Key) перенесены на Этап 2 — зависят от готовности бэкенда Тимура.

---

## Что сделано

### 1. Среда разработки
- PlatformIO CLI, framework: Arduino, board: esp32dev
- Два проекта: `firmware/` (основной) и `firmware-test/` (тестовый стенд)
- Библиотеки: ArduinoJson 7.x, TinyGPSPlus 1.1, ESPAsyncWebServer, AsyncTCP

### 2. Аппаратная сборка
- Плата: LIVE MINI KIT ESP32 (ESP-WROOM-32, двухъядерный Xtensa)
- Распиновка подобрана под физическую разводку платы
- Инструкция по сборке: `firmware/ASSEMBLY.md`

| Модуль | Пины | Статус |
|--------|------|--------|
| WCMCU-230 (CAN) | TX=GPIO22, RX=GPIO21 | OK |
| NEO-M8N (GPS) | RX=GPIO16, TX=GPIO17 | OK |
| MPU-6050 (IMU) | SDA=GPIO18, SCL=GPIO19 | OK |

### 3. Диагностика модулей
Диагностический скетч `firmware/src/main.cpp` — тестирует все модули при включении:

| Тест | Результат | Детали |
|------|-----------|--------|
| Wi-Fi | OK | Подключение к роутеру, IP получен, RSSI в норме |
| I2C / MPU-6050 | OK | WHO_AM_I = 0x70 (MPU-6500/клон), данные валидны |
| CAN / TWAI | OK | Драйвер инициализирован, listen-only 500 kbit/s |
| GPS / NEO-M8N | OK | NMEA парсится, фикс получен, спутники видны |

### 4. Тестовый стенд с веб-дашбордом (`firmware-test/`)
Отдельный PlatformIO-проект — ESP32 поднимает веб-сервер в локальной сети.

**Функции:**
- Акселерометр и гироскоп — live-графики Canvas с автоскейлом (5 Hz через WebSocket)
- GPS — координаты, скорость, высота, кол-во спутников
- Спутники — sky plot (полярная диаграмма), SNR bar chart, разделение по созвездиям (GPS/GLONASS/Galileo/BeiDou/SBAS)
- CAN Bus — лог фреймов в реальном времени
- Система — RSSI, heap, uptime, кол-во WS-клиентов
- Дашборд: `firmware-test/data/index.html` (dark theme, zero dependencies)

**Решённые проблемы:**
- I2C bus lock после reset ESP32 → добавлена процедура `i2cRecover()` (16 SCL-импульсов)
- MPU-6050 не отвечал → ретраи + задержка после Wire.begin()
- GSV-парсер: `strtok` пропускал пустые SNR → заменён на `splitCSV`
- `$GNGSV` (multi-GNSS talker) не распознавался → добавлено определение созвездия по PRN
- Отдельные буферы по созвездиям вместо одного общего (созвездия перезатирали друг друга)

**Технический стек стенда:**
- ESPAsyncWebServer + WebSocket (200 мс интервал)
- LittleFS для хранения HTML
- Ручной GSV NMEA-парсер (TinyGPSPlus не парсит GSV)
- ArduinoJson для API-ответов

### 5. Проектирование провизионинга
- Дизайн-документ: `firmware/PROVISIONING.md`
- SoftAP captive portal для настройки WiFi
- Мультитенантность (таблица tenants, изоляция данных)
- Привязка устройства к аккаунту через QR-код
- Реализация запланирована на Этап 5

### 6. Документация API
- Файл: `docs/api.html` (self-contained HTML, dark theme)
- Все эндпоинты: устройство, провизионинг, авторизация, фронтенд, Telegram
- JSON-примеры запросов/ответов
- История версий

---

## Отклонения от спецификации

| Что | Было в спеке | Фактически | Причина |
|-----|-------------|------------|---------|
| Микроконтроллер | ESP32-C3 | ESP-WROOM-32 (ESP32) | Двухъядерный, больше GPIO, встроенный TWAI |
| MPU-6050 WHO_AM_I | 0x68 | 0x70 | Чип MPU-6500/клон, регистры совместимы |

---

## Блокеры для следующего этапа

- Бэкенд Тимура с эндпоинтами `POST /api/telemetry` и `POST /api/device/ping`
- Пока бэкенд не готов — можно тестировать на httpbin.org или локальный mock-сервер

---

## Артефакты

| Файл | Описание |
|------|----------|
| `firmware/platformio.ini` | Конфигурация PlatformIO (основной проект) |
| `firmware/src/main.cpp` | Диагностический скетч |
| `firmware/include/config.h` | Конфигурация пинов, WiFi, бэкенда |
| `firmware/plan.md` | Roadmap прошивки (6 этапов) |
| `firmware/ASSEMBLY.md` | Инструкция по сборке |
| `firmware/PROVISIONING.md` | Дизайн провизионинга |
| `firmware-test/` | Тестовый стенд с веб-дашбордом |
| `firmware-test/src/main.cpp` | Прошивка стенда (сенсоры + WebSocket + GSV) |
| `firmware-test/data/index.html` | Веб-дашборд (графики, sky plot, SNR chart) |
| `docs/api.html` | Документация API |
