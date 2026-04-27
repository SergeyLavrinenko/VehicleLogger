# Провизионинг устройства — Архитектура

Дизайн-документ: как покупатель настраивает модуль VehicleLogger и привязывает к своему аккаунту.

---

## Проблема

Сейчас WiFi, Device ID и API-ключ захардкожены в `config.h`. Для продакшена нужно:

1. **WiFi** — каждый покупатель использует свою сеть/хотспот
2. **Привязка к аккаунту** — модуль должен принадлежать конкретной компании
3. **Изоляция** — компания A не видит устройства компании B (мультитенантность)
4. **Безопасность** — API-ключ не должен быть захардкожен в прошивке

---

## Архитектура мультитенантности

- Базовый домен: `example.com` (продакшн: будет `vehiclelogger.ru` или похожий)
- Каждая компания получает поддомен: `<companyname>.example.com`
- Wildcard TLS-сертификат: `*.example.com`
- Один и тот же бэкенд обслуживает все поддомены, тенант резолвится по `Host`-заголовку запроса
- Прошивка одинакова для всех устройств — поддомен компании указывается установщиком при первичной настройке

---

## Жизненный цикл устройства

```
  ЗАВОД             ПОКУПАТЕЛЬ              ЭКСПЛУАТАЦИЯ
    |                   |                       |
    v                   v                       v
[Изготовлено]  →  [Не настроено]  →  [Привязано / Работает]
                       |                       |
                  (SoftAP режим)          [Смена WiFi] → обратно в "Не настроено"
                  Captive portal:              |
                  WiFi + поддомен         [Unclaim из ЛК] → обратно в "Изготовлено"
                  + код привязки
                       |
                       v
                  [Привязано / Работает]
```

### Состояния

| Состояние | WiFi в NVS | API-ключ в NVS | Что делает устройство |
|-----------|------------|-----------------|----------------------|
| Изготовлено | — | — | SoftAP (captive portal) |
| WiFi настроен, не привязано | Да | — | SoftAP с сообщением об ошибке (был неверный код/поддомен) |
| Привязано | Да | Да | Отправляет телеметрию (рабочий режим) |

---

## 1. Заводская подготовка

Прошивка **одинакова** для всех устройств. Отличаются только данные в NVS.

### Что записывается в NVS при производстве

| NVS Namespace | Ключ | Значение | Описание |
|---------------|------|----------|----------|
| `factory` | `serial` | `VL-A3F82B01` | Серийный номер (уникальный) |
| `factory` | `secret` | 32 случайных байта | Секрет устройства |

### Серийный номер

Формат: `VL-XXXXXXXX` — 8 hex-символов, вычисляется из MAC-адреса ESP32.

```
MAC: AA:BB:CC:DD:EE:FF → Serial: VL-CCDDEEFF
```

Каждый ESP32 имеет уникальный MAC — серийники не пересекутся.

### Секрет устройства

32 случайных байта (256 бит), генерируются при производстве. Хранятся только на устройстве (в NVS) и на бэкенде (в виде SHA-256-хеша).

### Маркировка корпуса

Наклейка содержит только серийный номер (для гарантии и инвентаризации):

```
VL-A3F82B01
```

QR-код **не используется** — привязка идёт через captive portal с вводом поддомена и кода привязки.

### Заводской скрипт (Python + esptool)

Запускается один раз на каждое устройство через USB:

```
1. Прошить firmware.bin (одинаковый для всех)
2. Прочитать MAC-адрес ESP32
3. Сгенерировать серийный номер из MAC
4. Сгенерировать 32 случайных байта (секрет)
5. Записать serial + secret в NVS-партицию
6. Вывести данные для печати наклейки
7. Отправить serial + SHA-256(secret) в БД бэкенда (batch API или CSV)
```

---

## 2. Настройка WiFi и привязка (SoftAP Captive Portal)

### Сценарий пользователя

1. Админ компании в ЛК (`acme.example.com/devices`) нажимает "Добавить устройство"
2. Бэкенд генерирует одноразовый **6-значный код привязки** (например, `428193`), TTL 30 минут
3. Админ передаёт установщику: поддомен компании (`acme`) и код (`428193`)
4. Установщик ставит модуль в фуру (OBD-II)
5. Модуль включается → нет WiFi-кредов → запускается **SoftAP**
6. На телефоне в списке WiFi появляется `VehicleLogger-CCDDEEFF`
7. Подключается к этой сети (пароль: `setup1234`, указан на наклейке или в инструкции)
8. Открывается **captive portal**
9. Установщик вводит:
   - WiFi-сеть (выбор из скана) и пароль
   - Поддомен компании: `acme`
   - Код привязки: `428193`
10. Нажимает "Подключить и привязать"
11. ESP подключается к WiFi → шлёт POST на `https://acme.example.com/api/devices/enroll` → получает API-ключ → сохраняет в NVS → переходит в рабочий режим
12. В админке `acme.example.com/devices` появляется новое устройство (статус `active`)

### Что делает ESP32

```
BOOT
  |
  Читаем NVS: wifi/ssid, cloud/api_key
  |
  ├── Нет WiFi-кредов → Режим SoftAP (captive portal)
  │     1. Сканируем WiFi-сети
  │     2. Запускаем AP: "VehicleLogger-{serial_last8}", пароль "setup1234"
  │     3. Запускаем DNS-сервер (все запросы → на себя)
  │     4. Запускаем HTTP-сервер на порту 80
  │     5. Раздаём страницу настройки (HTML из LittleFS)
  │     6. Ждём POST /api/setup с {ssid, password, subdomain, enrollCode}
  │     7. Подключаемся к указанной WiFi-сети
  │     8. Если WiFi FAIL → отвечаем ошибкой, остаёмся в SoftAP
  │     9. Если WiFi OK → POST на https://<subdomain>.example.com/api/devices/enroll
  │     10. Если 200 → сохраняем wifi-creds + api_key + backend_url в NVS, перезагружаемся
  │     11. Если 4xx → ошибка в /api/status (invalid_code/invalid_subdomain/already_claimed),
  │         WiFi-креды НЕ сохраняем (даём установщику повторить ввод)
  │
  ├── Есть WiFi, нет api_key → SoftAP (с прошлой сессии: предыдущий enroll не удался)
  │
  └── Есть WiFi и api_key → Подключаемся, рабочий режим
        ├── Telemetry: POST /api/telemetry с api_key в заголовке
        ├── Heartbeat: каждые 60 сек
        ├── 401 → api_key отозван → стираем из NVS → SoftAP
        └── 410 → устройство деактивировано → стираем api_key из NVS → SoftAP
```

### Captive Portal (веб-страница)

Минимальная HTML-страница (~6 КБ), хранится в LittleFS прошивки:

```
┌────────────────────────────────────┐
│   VehicleLogger — Настройка        │
│                                    │
│   1) WiFi-сеть                     │
│   ┌──────────────────────────┐     │
│   │ ▼ Keenetic-5935   -45 dBm│     │
│   │   TP-Link_Guest   -72 dBm│     │
│   │   MTS-Router      -80 dBm│     │
│   └──────────────────────────┘     │
│   Пароль:  [_________________]     │
│                                    │
│   2) Компания                      │
│   Поддомен: [acme] .example.com    │
│   Код привязки: [_ _ _ _ _ _]      │
│                                    │
│   [ Подключить и привязать ]       │
│                                    │
│   Серийный номер: VL-A3F82B01      │
│   Статус: ожидание настройки       │
└────────────────────────────────────┘
```

### Локальные HTTP-эндпоинты (на ESP32, в SoftAP)

| Путь | Метод | Описание |
|------|-------|----------|
| `/` | GET | Captive portal HTML из LittleFS |
| `/api/scan` | GET | Список WiFi-сетей: `[{"ssid":"...","rssi":-45,"secure":true}]` |
| `/api/setup` | POST | `{ssid, password, subdomain, enrollCode}` — connect WiFi + enroll одной операцией |
| `/api/status` | GET | `{wifi:"ok\|fail", enroll:"pending\|ok\|invalid_code\|invalid_subdomain\|already_claimed\|invalid_secret", ip}` |

`/api/setup` выполняется асинхронно: сразу возвращает `{accepted:true}`, фронт поллит `/api/status` каждую секунду до получения результата.

---

## 3. Enroll (привязка к тенанту)

### Эндпоинт бэкенда

`POST https://<subdomain>.example.com/api/devices/enroll`

**Запрос (без auth, ESP32 шлёт сразу после WiFi connect):**
```json
{
  "serialNumber": "VL-A3F82B01",
  "deviceSecret": "a1b2c3d4e5f6...полный_секрет_64_hex_символа",
  "enrollCode": "428193"
}
```

**Логика бэкенда:**
1. Резолвим tenant по поддомену из `Host` → если поддомена нет → 404 (`unknown_subdomain`)
2. Найти device по `serialNumber` → если нет → 404 (`unknown_device`)
3. Проверить `SHA-256(deviceSecret) == device.secret_hash` → если не совпало → 403 (`invalid_secret`)
4. Если `device.status == claimed` → 409 (`already_claimed`)
5. Если `device.status == deactivated` → 410 (`deactivated`)
6. Найти `enrollment_codes` для этого тенанта где `SHA-256(enrollCode) == code_hash AND used_at IS NULL AND expires_at > now()` → если нет → 400 (`invalid_code`)
7. Сгенерировать API-ключ (64 hex), сохранить SHA-256-хеш в `device.api_key_hash`
8. Обновить `device`: `tenant_id`, `status='claimed'`, `claimed_at=now()`
9. Пометить `enrollment_codes`: `used_at=now()`, `used_by_device=device.id`
10. Вернуть 200 + `{apiKey, backendUrl: "https://<subdomain>.example.com", sendIntervalMs: 5000}`

**Коды ответа:**

| Код | Тело | Ситуация |
|-----|------|----------|
| 200 | `{apiKey, backendUrl, sendIntervalMs}` | Привязано, ключ выдан |
| 400 | `{error:"invalid_code"}` | Код не найден / использован / просрочен |
| 403 | `{error:"invalid_secret"}` | deviceSecret не совпадает с заводским |
| 404 | `{error:"unknown_subdomain"}` или `{error:"unknown_device"}` | Поддомен или серийник не найдены |
| 409 | `{error:"already_claimed"}` | Устройство уже привязано (отвязать только через ЛК) |
| 410 | `{error:"deactivated"}` | Устройство снято с обслуживания |

**Безопасность:** Только по HTTPS. Полный секрет (256 бит) подтверждает что вызов идёт с реального устройства.

### Sequence Diagram

```
  Установщик          ESP32                Backend (acme.example.com)
       |                |                          |
       |  [Админ выдал код "428193", сообщил установщику]
       |                |                          |
       | -- WiFi: VehicleLogger-... --(SoftAP)-->  |
       | -- открывает 192.168.4.1 →               |
       | -- POST /api/setup ----------->|          |
       |    {ssid,pass,sub,code}        |          |
       |<-- {accepted:true} ------------|          |
       |    (поллит /api/status)        |          |
       |                                | (connect WiFi)
       |                                |--POST /api/devices/enroll-->|
       |                                |   {serial,secret,code}      |
       |                                |<-- 200 {apiKey,backendUrl}--|
       |                                | (save NVS, restart)         |
       |<-- /api/status: enroll=ok ----|                              |
       |                                |                              |
       |  [после reboot — рабочий режим]                              |
       |                                |--POST /api/telemetry-------->|
```

---

## 4. Мультитенантность

### Концепция

Каждая компания-покупатель = **тенант** (tenant) = поддомен `<name>.example.com`. Все данные изолированы: компания видит только свои устройства, фуры, водителей.

### Изменения в БД

#### Новая таблица: `tenants`

```sql
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subdomain   VARCHAR(63) UNIQUE NOT NULL,   -- "acme" → acme.example.com
    name        VARCHAR(200) NOT NULL,          -- "ООО Транспорт Логистик"
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Constraints на subdomain: a-z, 0-9, dash, 3-63 символа (RFC 1035)
ALTER TABLE tenants ADD CONSTRAINT subdomain_format
  CHECK (subdomain ~ '^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$');
```

#### Изменения в существующих таблицах

```sql
-- devices
ALTER TABLE devices ADD COLUMN tenant_id          UUID REFERENCES tenants(id);
ALTER TABLE devices ADD COLUMN device_secret_hash VARCHAR(128) NOT NULL;
ALTER TABLE devices ADD COLUMN api_key_hash       VARCHAR(128);
ALTER TABLE devices ADD COLUMN status             VARCHAR(20) NOT NULL DEFAULT 'manufactured';
        -- manufactured | claimed | deactivated
ALTER TABLE devices ADD COLUMN claimed_at         TIMESTAMPTZ;
ALTER TABLE devices ADD COLUMN claimed_by         UUID REFERENCES users(id);

-- vehicles, users — привязать к тенанту
ALTER TABLE vehicles ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE users    ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
```

#### Новая таблица: `enrollment_codes`

```sql
CREATE TABLE enrollment_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code_hash       VARCHAR(128) NOT NULL,       -- SHA-256(plaintext code)
    created_by      UUID NOT NULL REFERENCES users(id),
    expires_at      TIMESTAMPTZ NOT NULL,        -- +30 минут
    used_at         TIMESTAMPTZ,
    used_by_device  UUID REFERENCES devices(id),
    label           VARCHAR(100),                -- "Фура МАН А123" — для удобства админа
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_enrollment_codes_active
  ON enrollment_codes(tenant_id, code_hash) WHERE used_at IS NULL;
```

Plaintext-код возвращается админу **один раз** (в ответе на POST /api/enrollment-codes). Дальше виден только префикс (`428***`) для идентификации в списке.

### Как работает изоляция

```
Компания A (acme.example.com)         Компания B (logistics.example.com)
├── Фура "МАН А123" (vehicle)         ├── Фура "Скания Б456" (vehicle)
├── Устройство VL-001 (device)        ├── Устройство VL-005 (device)
├── Устройство VL-002 (device)        ├── Устройство VL-006 (device)
├── Админ Иван (user, admin)          ├── Админ Пётр (user, admin)
└── Водитель Олег (user, driver)      └── Водитель Сергей (user, driver)

Все запросы к <subdomain>.example.com → middleware резолвит tenant_id из Host
→ WHERE tenant_id = <resolved> применяется автоматически
→ Иван видит только VL-001, VL-002 и "МАН А123"
→ Пётр видит только VL-005, VL-006 и "Скания Б456"
```

---

## 5. API-эндпоинты провизионинга

### Со стороны устройства (без auth)

#### `POST /api/devices/enroll`

Описано в разделе 3.

#### `POST /api/telemetry`

Заголовок: `Authorization: Bearer <api_key>`. Ответы 401/410 → ESP стирает `api_key` из NVS и возвращается в SoftAP.

### Со стороны веб-панели (JWT, scope = tenant)

#### `POST /api/enrollment-codes`

Создать код привязки.

**Запрос:**
```json
{ "label": "Фура МАН А123" }
```

**Ответ:**
```json
{
  "id": "uuid",
  "code": "428193",
  "expiresAt": "2026-04-27T14:30:00Z",
  "label": "Фура МАН А123"
}
```

Полный код (`code`) возвращается **только в этом ответе**. Дальше виден только префикс.

#### `GET /api/enrollment-codes`

Список активных кодов тенанта (не использованных, не просроченных). В ответе только префикс кода.

#### `DELETE /api/enrollment-codes/{id}`

Отозвать неиспользованный код (помечает как использованный без привязки).

#### `POST /api/devices/{id}/unclaim`

Отвязать устройство (передача, продажа).

- Очищает `tenant_id`, `api_key_hash`, `claimed_at`, `claimed_by`
- Статус → `manufactured`
- Устройство при следующем запросе получит 401 → стирает api_key → SoftAP → можно привязать к другой компании (с новым кодом)

#### `POST /api/devices/{id}/rotate-key`

Ротация API-ключа (при компрометации).

- Генерирует новый ключ, обновляет хеш
- Устройство получит 401 → стирает ключ из NVS → SoftAP → нужен новый enroll code

#### `GET /api/devices`

Список устройств текущего тенанта.

```json
[
  {
    "id": "uuid",
    "serialNumber": "VL-A3F82B01",
    "vehicleName": "МАН А123БВ",
    "status": "claimed",
    "isOnline": true,
    "lastPingAt": "2026-04-27T14:00:00Z"
  }
]
```

#### `PUT /api/devices/{id}/vehicle`

Переназначить устройство на другую фуру внутри тенанта: `{ "vehicleId": "uuid" }`.

---

## 6. Изменения прошивки (план реализации)

### NVS вместо config.h

| Сейчас (config.h) | Будет (NVS) |
|-------|------|
| `WIFI_SSID` | `wifi/ssid` |
| `WIFI_PASSWORD` | `wifi/password` |
| `DEVICE_ID` | `factory/serial` (записано на заводе) |
| `DEVICE_API_KEY` | `cloud/api_key` (получено при enroll) |
| `BACKEND_URL` | `cloud/backend_url` (получено при enroll) |

В `config.h` остаются только **пины** и **аппаратные константы**:

```c
#pragma once

// ===== CAN (TWAI) =====
#define CAN_TX_PIN    GPIO_NUM_22
#define CAN_RX_PIN    GPIO_NUM_21

// ===== GPS (NEO-M8N) =====
#define GPS_RX_PIN    16
#define GPS_TX_PIN    17
#define GPS_BAUD      9600

// ===== IMU (MPU-6050) =====
#define MPU_SDA_PIN   18
#define MPU_SCL_PIN   19
#define MPU_ADDR      0x68

// ===== Провизионинг =====
#define AP_PASSWORD           "setup1234"
#define BASE_DOMAIN           "example.com"  // продакшн заменим
#define RESET_BUTTON_PIN      GPIO_NUM_0     // кнопка BOOT на DevKit
#define WIFI_RETRY_COUNT      5

// ===== LED =====
#define LED_PIN               GPIO_NUM_2
```

### Boot State Machine

```
                      BOOT
                       |
                Читаем NVS wifi/ssid
                       |
              +--------+--------+
              |                 |
         Нет кредов       Есть креды
              |                 |
       SoftAP режим      Пробуем WiFi
       (captive portal)        |
                        +------+------+
                        |             |
                   Подключено    Не удалось (5 раз)
                        |             |
                 Читаем NVS      SoftAP режим
                 cloud/api_key
                        |
               +--------+--------+
               |                 |
          Нет ключа        Есть ключ
               |                 |
        SoftAP режим      РАБОЧИЙ РЕЖИМ
        (предыдущий       (телеметрия + heartbeat)
        enroll не удался)
```

Обратите внимание: **поллинг `/provision` каждые 10 сек больше не нужен**. Enroll выполняется синхронно в `/api/setup`, результат сразу известен.

### Структура файлов прошивки (целевая)

```
firmware/src/
├── main.cpp              — setup() + loop(), state machine
├── nvs_store.h/.cpp      — обёртка Preferences (factory/wifi/cloud namespaces)
├── provisioning.h/.cpp   — SoftAP + DNS + AsyncWebServer + LittleFS + /api/setup
├── wifi_manager.h/.cpp   — connect from NVS, reconnect
├── cloud.h/.cpp          — HTTPS POST: /enroll, /telemetry, /heartbeat
├── led_status.h/.cpp     — индикация состояния через LED
├── j1939.h/.cpp          — декодер J1939 (перенос из firmware-test/)
└── obd2.h/.cpp           — OBD-II поллер (перенос из firmware-test/)

firmware/data/
└── setup.html            — captive portal

firmware/include/
└── config.h              — только пины и AP_PASSWORD/BASE_DOMAIN
```

### Кнопка сброса

Используем GPIO 0 (кнопка BOOT на DevKit). В продакшен-плате — отдельная кнопка.

| Действие | Удержание | Что сбрасывается | Что сохраняется |
|----------|-----------|-------------------|-----------------|
| Сброс WiFi | 5 секунд | `wifi/ssid`, `wifi/password` | factory/*, cloud/* (api_key выживает) |
| Factory reset | 10 секунд | wifi/* + cloud/* | factory/serial, factory/secret |

После сброса WiFi → устройство в SoftAP, можно ввести новые WiFi-креды без повторного enroll (api_key сохраняется).

После factory reset → устройство как новое. Нужен новый enroll-код от админа.

### LED-индикация

| Паттерн | Состояние |
|---------|-----------|
| Медленное мигание (1 Гц) | SoftAP — ожидание captive portal |
| Быстрое мигание (4 Гц) | Подключение к WiFi / выполнение /enroll |
| Горит постоянно | Рабочий режим |
| Двойная вспышка каждые 3 сек | Ошибка (нет связи с бэкендом после успешного enroll) |

---

## 7. Безопасность

### Транспорт

- **ESP32 → Бэкенд**: только HTTPS. Прошивка содержит корневой CA-сертификат (Let's Encrypt R3 / ISRG Root X1 / X2).
- **SoftAP**: локальная сеть, пароль на наклейке/в инструкции. WiFi-пароль и enroll-код передаются по HTTP (локально, не в интернет). При необходимости можно добавить self-signed TLS на ESP32 — но это усложняет UX (предупреждение в браузере).

### API-ключи

- Генерируются на бэкенде при enroll (64 hex = 256 бит)
- Бэкенд хранит только **хеш** (SHA-256)
- Plaintext существует только: в ответе на /enroll (один раз) и в NVS устройства
- При компрометации — ротация через `/rotate-key`

### Защита enroll

Чтобы привязать устройство, нужны **три фактора**:
1. **Физический доступ к устройству** — для подключения к его SoftAP
2. **Знание поддомена компании** — публичная информация, но осмысленный ввод
3. **Знание enroll-кода** — выдан админом конкретного тенанта, TTL 30 мин, single-use

Дополнительно: device-secret (256 бит из NVS) подтверждает что обращается реальное устройство (не подделка с тем же серийником).

**Сценарий с опечаткой в поддомене**: установщик ошибся (`acne` вместо `acme`). Если поддомен `acne` существует — у того тенанта enroll-код `428193` не валидный → 400 `invalid_code`. Если не существует — 404. В обоих случаях устройство не привяжется к чужой компании.

### Защита от утечки enroll-кода

- TTL 30 минут
- Single-use (после успешного enroll помечается `used_at`)
- Админ может отозвать неиспользованный код через `DELETE /api/enrollment-codes/{id}`
- Без device-secret код бесполезен (нужен физический доступ к устройству)

### Ротация и отзыв

| Сценарий | Действие |
|----------|----------|
| Подозрение на компрометацию ключа | `/rotate-key` → устройство получит 401 → перезаявит через новый enroll-код |
| Продажа/передача устройства | `/unclaim` → устройство теряет привязку, новый владелец привязывает с новым кодом |
| Потерянное устройство | `/unclaim` + `status='deactivated'` → устройство получит 410 и больше не активируется |

---

## 8. Смена WiFi-сети

Когда устройство переезжает в другую фуру с другим хотспотом:

1. Удерживать кнопку сброса **5 секунд** → LED мигнёт 3 раза
2. Устройство перезагружается в SoftAP-режим
3. Подключиться телефоном, ввести новые WiFi-креды (поля поддомена и кода **остаются пустыми** — api_key уже в NVS)
4. ESP подключается к новой сети с **тем же API-ключом** — повторный enroll не нужен
5. Если нужно переназначить на другую фуру → через веб-панель (`PUT /devices/{id}/vehicle`)

---

## 9. Зависимости для реализации

### Прошивка (Сергей)

| Библиотека | Назначение |
|------------|------------|
| `ESPAsyncWebServer` | HTTP-сервер для captive portal |
| `AsyncTCP` | Async TCP для ESPAsyncWebServer |
| `DNSServer` (встроенная) | Перенаправление DNS для captive portal |
| `Preferences` (встроенная) | NVS read/write |
| `WiFiClientSecure` (встроенная) | HTTPS для связи с бэкендом |
| `LittleFS` | Раздача setup.html и сертификатов |

### Бэкенд (Тимур)

- Таблицы `tenants` (с `subdomain`), `enrollment_codes` + `tenant_id` во всех таблицах
- Wildcard-роутинг `*.example.com` → middleware резолвит tenant по `Host`
- Эндпоинты: `/api/devices/enroll`, `/api/devices/{id}/unclaim`, `/api/devices/{id}/rotate-key`, `/api/devices/{id}/vehicle`, `/api/enrollment-codes` (GET/POST/DELETE)
- JWT содержит `tenant_id` → middleware фильтрует все запросы
- Страницы в Vue 3: список устройств, модалка выдачи кода, список активных кодов

---

## 10. Порядок реализации

Провизионинг реализуется **после** Setup-этапа (когда уже работает базовая отправка телеметрии):

| Шаг | Что | Кто |
|-----|-----|-----|
| 1 | NVS-обёртка + boot state machine + scaffold модулей | Сергей |
| 2 | SoftAP + captive portal (только WiFi-настройка локально) | Сергей |
| 3 | Таблицы `tenants` (subdomain) + `enrollment_codes` + миграции | Тимур |
| 4 | Эндпоинт `/api/devices/enroll` + `/api/enrollment-codes` (POST/GET/DELETE) | Тимур |
| 5 | Cloud-модуль на ESP: HTTPS POST /enroll → сохранение в NVS | Сергей |
| 6 | Frontend: страница "Устройства" + модалка выдачи кода | Тимур |
| 7 | Перенос J1939/OBD-II из `firmware-test/` в `firmware/` | Сергей |
| 8 | Кнопка сброса + LED-индикация | Сергей |
| 9 | Заводской скрипт (Python, esptool) — отложен до массового производства | Сергей |
| 10 | Сквозной тест на реальном поддомене | Все |
