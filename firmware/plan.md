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

Пины подобраны под разводку платы — каждая пара физически рядом на разъёмах.

| ESP32 GPIO | Подключение | Сторона платы | Примечание |
|------------|-------------|---------------|------------|
| GPIO 22 | WCMCU-230 CTX (CAN TX) | Левая inner, строка 3 | TWAI TX |
| GPIO 21 | WCMCU-230 CRX (CAN RX) | Левая inner, строка 4 | TWAI RX |
| GPIO 16 | NEO-M8N TX | Левая inner, строка 6 | UART2 RX (GPS → ESP) |
| GPIO 17 | NEO-M8N RX | Левая inner, строка 5 | UART2 TX (ESP → GPS) |
| GPIO 18 | MPU-6050 SDA | Правая inner, строка 4 | I2C Data |
| GPIO 19 | MPU-6050 SCL | Правая inner, строка 5 | I2C Clock |
| 3.3V | Питание модулей | Правая, строка 8 | |
| GND | Общая земля | Левая, строка 1/7 | |

---

## Этапы разработки

### Этап 0 — Диагностика (текущий)

Цель: проверить работоспособность и правильность подключения всех модулей.

**Файл:** `src/main.cpp` (диагностический скетч)

**Тесты:**
- [x] Wi-Fi — подключение к сети, вывод IP и RSSI
- [x] I2C scan + MPU-6050 — поиск устройств на шине, чтение WHO_AM_I, чтение акселерометра/гироскопа
- [x] CAN/TWAI (WCMCU-230) — инициализация драйвера, приём фреймов (5 сек)
- [x] GPS (NEO-M8N) — чтение UART, парсинг NMEA, поиск фикса

**Как запустить:**
1. Вписать Wi-Fi в `include/config.h`
2. Собрать и прошить: `pio run -t upload`
3. Открыть Serial Monitor: `pio device monitor`
4. Смотреть результаты — OK/FAIL по каждому модулю

---

### Этап 1 — Setup ✓

Цель: настройка среды, проверка железа, тестовый стенд.

**Задачи:**

- [x] Создать PlatformIO проект (Arduino framework)
- [x] Подключение к Wi-Fi (SSID/пароль в конфиге)
- [x] Диагностика всех модулей (Wi-Fi, IMU, CAN, GPS)
- [x] Тестовый веб-дашборд (`firmware-test/`) с live-графиками, sky plot, SNR
- [x] Проектирование провизионинга (`PROVISIONING.md`)
- [x] Документация API (`docs/api.html`)
- [ ] Отправка тестовой телеметрии `POST /api/telemetry` → перенесено на Этап 2 (ждёт бэкенд)
- [ ] Отправка heartbeat `POST /api/device/ping` → перенесено на Этап 2
- [ ] Заголовок `X-Device-Key` с тестовым ключом → перенесено на Этап 2

**Формат тестового пакета:**

```json
{
  "deviceId": "ESP32-TEST-001",
  "timestamp": "2026-03-22T14:30:00Z",
  "data": {
    "rpm": 1500,
    "speed": 60,
    "coolantTemp": 85,
    "oilPressure": 3.2,
    "fuelLevel": 70,
    "voltage": 13.6,
    "dtcCodes": []
  }
}
```

**Зависимость:** URL бэкенда Тимура (пока можно тестировать на httpbin.org или локальный сервер).

### Этап 2 — CAN-шина

- [ ] Инициализация TWAI (CAN) контроллера
- [ ] Подключение WCMCU-230, приём CAN-кадров
- [ ] Парсинг OBD-II PID: обороты, температура, скорость, давление масла, уровень топлива, напряжение
- [ ] Чтение DTC-кодов
- [ ] Замена тестовых данных на реальные

### Этап 3 — GPS

- [ ] Инициализация UART2 для NEO-M8N
- [ ] Парсинг NMEA (библиотека TinyGPSPlus)
- [ ] Добавление координат и GPS-скорости в пакет телеметрии

### Этап 4 — IMU (MPU-6050)

- [ ] Инициализация I2C, чтение данных с MPU-6050
- [ ] Детекция событий: резкое торможение, ускорение, сильная вибрация
- [ ] Добавление данных IMU в пакет телеметрии

### Этап 5 — Провизионинг и мультитенантность

> Подробный дизайн-документ: [`PROVISIONING.md`](PROVISIONING.md)

- [ ] NVS-обёртка (замена hardcode config.h на NVS для WiFi/ключей)
- [ ] Boot state machine (SoftAP → WiFi → Provision → Operational)
- [ ] SoftAP + captive portal (настройка WiFi через телефон)
- [ ] Поллинг `POST /api/devices/provision` (получение API-ключа)
- [ ] Кнопка сброса (GPIO 0): 5 сек = WiFi reset, 10 сек = factory reset
- [ ] LED-индикация состояний
- [ ] Заводской скрипт (Python + esptool): серийный номер + секрет в NVS

### Этап 6 — Буферизация и надёжность

- [ ] Локальный буфер (SPIFFS/LittleFS) при потере Wi-Fi
- [ ] Повторная отправка при восстановлении связи
- [ ] Watchdog timer

---

## Стек

- **Фреймворк:** Arduino (через PlatformIO)
- **Сборка:** PlatformIO CLI
- **Библиотеки:**
  - WiFi.h (встроенная)
  - HTTPClient.h (встроенная)
  - ArduinoJson (JSON)
  - driver/twai.h (CAN, ESP-IDF компонент)
  - TinyGPSPlus (GPS NMEA парсинг)
  - Wire.h + MPU6050 lib (I2C, IMU)
  - ESPAsyncWebServer (captive portal, этап 5)
  - Preferences.h (NVS, этап 5)
  - WiFiClientSecure (HTTPS, этап 5)

## Структура проекта (целевая)

```
firmware/
├── plan.md              # Этот файл
├── ASSEMBLY.md          # Инструкция по сборке
├── PROVISIONING.md      # Дизайн провизионинга
├── platformio.ini       # Конфигурация PlatformIO
├── src/
│   ├── main.cpp         # State machine: boot → provision → operational
│   ├── provisioning.cpp # SoftAP, DNS, captive portal
│   ├── wifi_manager.cpp # WiFi подключение, NVS-креды
│   ├── cloud.cpp        # HTTP: provision, telemetry, heartbeat
│   ├── nvs_store.cpp    # Обёртка над NVS
│   ├── can_reader.cpp   # CAN/TWAI
│   ├── gps_reader.cpp   # GPS NMEA
│   ├── imu_reader.cpp   # MPU-6050
│   └── led_status.cpp   # LED-индикация
├── include/
│   └── config.h         # Только пины и аппаратные константы
└── lib/
```
