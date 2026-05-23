# VehicleLogger

Система мониторинга состояния коммерческого транспорта в реальном времени.

- **Бэкенд** (`backend/`) — .NET 10 + ASP.NET Core + EF Core + SQLite + JWT.
- **Фронтенд** (`frontend/`) — Vue 3 + Vite + Chart.js.
- **Прошивка ESP32** (`firmware/`, `firmware-test/`) — PlatformIO + Arduino.
- **Симулятор устройства** (`tools/device-sim/`) — Node.js без внешних зависимостей.

## Что нужно поставить

- [.NET 10 SDK](https://dotnet.microsoft.com/download)
- [Node.js 18+](https://nodejs.org/) (для фронта и симулятора)
- (только для прошивки) [PlatformIO](https://platformio.org/) или VS Code + расширение

## Запустить локально

### Бэкенд

```bash
cd backend
dotnet run
```

Слушает `http://localhost:5000`. БД (`vehiclelogger.db`) и тестовые данные (фуры, устройства, учётки) создаются автоматически при первом запуске.

### Фронтенд

```bash
cd frontend
npm install   # один раз
npm run dev
```

Открыть `http://127.0.0.1:5173`. Прокси `/api` уже настроен на бэкенд.

### Симулятор устройства (отправляет фейковую телеметрию)

```bash
cd tools/device-sim
node sim.js
```

REPL принимает `start`, `stop`, `send`, `anomaly overheat`, `quit` и т.д. По умолчанию шлёт на прод (`https://nonconf.ru`); чтобы на локальный бэкенд — запустить с флагом `--url http://localhost:5000`.

## Тестовые учётки (создаются автосидером)

| Кто         | Email             | Пароль       | Где                |
|-------------|-------------------|--------------|--------------------|
| super-admin | `admin@vl.local`  | `admin1234`  | apex (`localhost`) |
| acme admin  | `admin@acme.test` | `sbCN4rvYnGdq` | поддомен `acme`  |
| delta admin | `admin@delta.test`| `mc7uKCFF3vsf` | поддомен `delta` |

Локально мультитенантность работает только если ходить через поддомен (`acme.localhost:5173` и т.п.); проще логиниться на `localhost` под super-admin'ом.

## ИИ-сводка состояния

На странице фуры — карточка «ИИ сводка» с кнопкой «Обновить». Генерируется большой языковой моделью (`gpt-oss:120b` через Ollama Cloud), кэшируется на 5 минут. При заходе на страницу — берётся из кэша или генерируется заново; без захода — не генерируется. Ключ от Ollama Cloud уже прописан в `backend/appsettings.json`.

## Где что искать

- `Description.md` — подробное описание системы и контрактов.
- `Communication.md` — JSON-форматы между компонентами.
- `Timur.md`, `Sergey.md`, `Payrav.md` — зоны ответственности.
- `Setup.md` — план этапов реализации.
- `docs/api.html` — список REST-эндпоинтов сервера.
- `reports/` — отчёты по стадиям.
