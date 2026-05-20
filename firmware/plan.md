# Firmware Plan — ESP32 устройство для VehicleLogger

## Железо

| Компонент | Модуль | Интерфейс | Назначение |
|-----------|--------|-----------|------------|
| МК | ESP-WROOM-32 (ESP32, двухъядерный Xtensa) | — | Основной контроллер, Wi-Fi |
| CAN-трансивер | WCMCU-230 (SN65HVD230) | CAN TX/RX → GPIO | Приём данных CAN-шины фуры |
| GPS | GY-GPSV3-NEO-M8N (u-blox NEO-M8N) | UART | Координаты, скорость, время |
| IMU | MPU-6050 (акселерометр + гироскоп) | I2C | Детекция резкого торможения, ускорения, вибраций |

> **Отличие от спеки:** используется ESP-WROOM-32 (ESP32) вместо ESP32-C3. ESP32 имеет двухъядерный процессор, больше GPIO, встроенный TWAI (CAN) контроллер — подходит лучше.

---

## Распиновка (LIVE MINI KIT ESP32)

| ESP32 GPIO | Подключение | Сторона платы | Примечание |
|------------|-------------|---------------|------------|
| GPIO 22 | WCMCU-230 CTX (CAN TX) | Левая inner, строка 3 | TWAI TX |
| GPIO 21 | WCMCU-230 CRX (CAN RX) | Левая inner, строка 4 | TWAI RX |
| GPIO 16 | NEO-M8N TX | Левая inner, строка 6 | UART2 RX (GPS → ESP) |
| GPIO 17 | NEO-M8N RX | Левая inner, строка 5 | UART2 TX (ESP → GPS) |
| GPIO 18 | MPU-6050 SDA | Правая inner, строка 4 | I2C Data |
| GPIO 19 | MPU-6050 SCL | Правая inner, строка 5 | I2C Clock |
| GPIO 0 | Кнопка BOOT/Reset | Встроена | 5 сек → WiFi reset, 10 сек → factory reset |
| GPIO 2 | Встроенный LED | Встроен | Индикация состояния |
| 3.3V | Питание модулей | Правая, строка 8 | |
| GND | Общая земля | Левая, строка 1/7 | |

---

## Прогресс этапов

### Этап 1 ✓ — Среда и диагностика *(commit `1cc8a7a`)*

- [x] PlatformIO + Arduino framework
- [x] Диагностический скетч (`firmware/src/main.cpp` v0): WiFi / I2C / CAN-init / GPS NMEA
- [x] Тестовый стенд `firmware-test/` с веб-дашбордом, sky-plot, SNR
- [x] Документация API (`docs/api.html`)
- [x] Дизайн-документ провизионинга `PROVISIONING.md` (первая редакция — QR-claim flow)

### Этап 2 ✓ — Декодеры CAN *(commit `32a1c61`)*

- [x] J1939 декодер: 10 PGN (RPM, speed, coolant, oil pressure, fuel level, voltage, fuel rate, engine load, total distance, engine hours) + DM1 (single-frame DTC)
- [x] OBD-II поллер: 7 PID (Mode 01: load, coolant, RPM, speed, fuel, voltage, fuel rate)
- [x] Auto-baud: 500 → 250 кбит/с после таймаута
- [x] Auto-protocol: J1939 (listen-only) ↔ OBD-II (NORMAL + опрос 0x7DF)
- [x] WiFiMulti — две точки сразу (стол + телефон-хотспот в авто)
- [x] Карточка «Показатели автомобиля» в дашборде `firmware-test/`
- [x] Сквозной тест: USBCAN-2A → ESP32 → дашборд

### Этап 3 ✓ — Провизионинг (subdomain + 6-значный код) *(commits `06dced1`, `f4b0117`, `09699f8`, `aabde2e`)*

Архитектура: мультитенантность через wildcard `*.nonconf.ru`. Каждая компания = поддомен. Установщик в captive portal вводит WiFi + поддомен + код, ESP сразу делает один POST `/api/devices/enroll`.

- [x] Переписан `PROVISIONING.md` (subdomain + enrollment_codes вместо QR-claim)
- [x] NVS-обёртка `nvs_store.{h,cpp}` (factory / wifi / cloud namespaces)
- [x] Boot state machine: provisioning vs working — по содержимому NVS
- [x] SoftAP + DNS catch-all + AsyncWebServer + LittleFS
- [x] Captive portal `data/setup.html` (~6 КБ): WiFi-скан + поддомен + код
- [x] HTTPS POST `/api/devices/enroll` с маппингом 200/400/403/404/409/410
- [x] Перенос декодеров J1939/OBD-II в `firmware/src/`
- [x] DEV: 3-сек serial reset window в boot (любая клавиша → стереть wifi+cloud, оставить factory)

### Этап 4 ✓ — Working mode + телеметрия *(commit `838adad`, Тимур)*

- [x] `wifi_manager.{h,cpp}` — connect from NVS + автоматический reconnect
- [x] `can_module.{h,cpp}` — портирован auto-baud 500↔250↔500 + auto-protocol J1939 listen-only / OBD-II normal mode
- [x] `cloud::sendTelemetry()` — POST `/api/telemetry` (Bearer api_key + UTC ISO timestamp через NTP) каждые `sendIntervalMs`
- [x] `cloud::sendPing()` — heartbeat `/api/device/ping` каждые 60 сек
- [x] Форс HTTPS-схемы в backendUrl (фикс под `X-Forwarded-Proto`, иначе WiFiClientSecure валится с SSL invalid record на 80 порту)
- [x] `enterWorkingMode()` заполнен — periodic `[STAT]` лог с frames/baud/proto/responses/rssi
- [x] `tools/monitor.py` + `monitor_noreset.py` — pyserial обёртки под Windows
- [ ] Обработка 401 (ключ отозван) → стираем `cloud/api_key` → SoftAP
- [ ] Обработка 410 (deactivated) → SoftAP

### Этап 5 — GPS и IMU в основной firmware

- [ ] `gps_reader.{h,cpp}` — UART2 + TinyGPSPlus (адаптировать из `firmware-test/`)
- [ ] `imu_reader.{h,cpp}` — MPU-6050 через `Wire` (адаптировать из `firmware-test/`)
- [ ] Детекция событий IMU: резкое торможение (ax < -0.6g), удар (sqrt(a²) > 2g)
- [ ] Добавить координаты + IMU-snapshot в пакет телеметрии

### Этап 6 — Reset, LED, factory script

- [ ] Кнопка GPIO 0 — 5 сек → `NvsStore::resetWifi()`, 10 сек → `NvsStore::factoryReset()` + restart (сейчас доступно через serial-window в boot — этап 3)
- [ ] `led_status.{h,cpp}` — паттерны: 1 Гц SoftAP, 4 Гц connecting, постоянный working, double-flash error
- [ ] `tools/factory_provision.py` — esptool + запись serial (из MAC) + 32-байтного secret в NVS-партицию + отправка `serial + sha256(secret)` на бэкенд

### Этап 7 — Буферизация и надёжность

- [ ] LittleFS-буфер при потере WiFi (ring-buffer телеметрии, ~1 час истории)
- [ ] Повторная отправка при восстановлении связи
- [ ] Watchdog timer (`esp_task_wdt`)
- [ ] Защита от bus-off на CAN (auto-recover из firmware-test/ уже работает)

### Этап 8 — OTA-обновление *(отдельный документ)*

- [ ] HTTPS OTA с проверкой подписи прошивки
- [ ] Канал обновлений на тенант (stable / beta)

---

## Сопутствующая работа (вне firmware)

- **Backend + Frontend** *(commit `56963d9`, Тимур)* — мультитенантный VehicleLogger:
  - .NET 10 + EF Core + SQLite (`backend/`)
  - Vue 3 + Vite (`frontend/`) с docs-страницами и device-management UI
  - Endpoints: `/api/devices/{enroll,provision,claim,unclaim,rotate-key}`, `/api/telemetry`, `/api/device/ping`, `/api/enrollment-codes`, `/api/tenants`, `/api/vehicles/*`
  - Live: nonconf.ru (super-admin) + wildcard `*.nonconf.ru` (тенанты)
- **Симулятор устройства** `tools/device-sim/` — JS-эмулятор для тестов без железа

## Стек

- **Фреймворк:** Arduino-ESP32 через PlatformIO
- **Библиотеки** (`firmware/platformio.ini`):
  - `me-no-dev/ESPAsyncWebServer @ ^1.2.4` — captive portal
  - `me-no-dev/AsyncTCP @ ^1.1.1` — async TCP
  - `bblanchon/ArduinoJson @ ^7.0.0` — JSON
  - `mikalhart/TinyGPSPlus @ ^1.1.0` — NMEA-парсер
  - Built-in: `WiFi`, `WiFiClientSecure`, `HTTPClient`, `Preferences` (NVS), `LittleFS`, `DNSServer`, `Wire` (I2C), `driver/twai.h` (CAN)

## Структура `firmware/`

```
firmware/
├── plan.md                  # Этот файл
├── PROVISIONING.md          # Дизайн провизионинга (subdomain + enroll-code)
├── ASSEMBLY.md              # Инструкция по сборке
├── platformio.ini
├── data/
│   └── setup.html           # captive portal HTML
├── include/
│   └── config.h             # пины + AP_PASSWORD + BASE_DOMAIN (без секретов)
└── src/
    ├── main.cpp             # boot state machine + serialResetWindow + working loop
    ├── nvs_store.{h,cpp}    # обёртка Preferences (factory / wifi / cloud)
    ├── provisioning.{h,cpp} # SoftAP + DNS + captive portal + /api/setup
    ├── wifi_manager.{h,cpp} # connect from NVS + reconnect (этап 4)
    ├── cloud.{h,cpp}        # HTTPS POST /enroll + sendTelemetry + ping
    ├── can_module.{h,cpp}   # auto-baud/auto-proto в working mode (этап 4)
    ├── j1939.{h,cpp}        # декодер J1939 (этап 2)
    ├── obd2.{h,cpp}         # OBD-II поллер (этап 2)
    │
    ├── gps_reader.{h,cpp}   # TODO этап 5
    ├── imu_reader.{h,cpp}   # TODO этап 5
    └── led_status.{h,cpp}   # TODO этап 6
```

## Параллельный стенд `firmware-test/`

Используется для отладки декодеров и сенсоров без production-провизионинга. Содержит web-дашборд (LittleFS + WebSocket) с live-показателями автомобиля, GPS-картой и IMU-графиками. Не идёт в продакшн — переносим оттуда модули в `firmware/` по мере готовности этапов.