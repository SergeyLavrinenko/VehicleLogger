<template>
  <h1>Прошивка устройства — что должна делать ESP32</h1>
  <p class="lead">
    Точная инструкция для разработчика прошивки. Соответствует
    <code>firmware/PROVISIONING.md</code> в ветке <code>feature/esp32-firmware</code>.
  </p>

  <div class="callout callout--info">
    <b>Это новая схема (apr-2026).</b> Вместо опроса <code>/api/devices/provision</code>
    + <i>claim</i> по QR теперь — синхронный <code>/api/devices/enroll</code> с
    6-значным кодом привязки, который установщик вводит в captive-portal вместе
    с WiFi-кредами. Старая схема осталась для совместимости с симулятором.
  </div>

  <h2>0. NVS до старта</h2>
  <table class="docs-table">
    <thead><tr><th>Namespace</th><th>Ключ</th><th>Что хранится</th></tr></thead>
    <tbody>
      <tr><td><code>factory</code></td><td><code>serial</code></td><td>Серийник <code>VL-XXXXXXXX</code></td></tr>
      <tr><td><code>factory</code></td><td><code>secret</code></td><td>32 случайных байта (256 бит, hex 64 символа)</td></tr>
      <tr><td><code>wifi</code></td><td><code>ssid</code> / <code>password</code></td><td>Заполняется в captive-portal</td></tr>
      <tr><td><code>cloud</code></td><td><code>api_key</code></td><td>Получается при <code>/enroll</code></td></tr>
      <tr><td><code>cloud</code></td><td><code>backend_url</code></td><td>Получается при <code>/enroll</code></td></tr>
    </tbody>
  </table>
  <p>
    На заводе записываются только <code>factory/serial</code> и <code>factory/secret</code>.
    Остальное появится при установке. Серийник + SHA-256 от секрета должны быть заранее
    в БД бэкенда — это делает админ через <router-link to="/devices">«Устройства» → + Зарегистрировать</router-link>.
  </p>

  <h2>1. State machine при старте</h2>
  <pre>BOOT
  │
  ▼
Прочитать NVS wifi/ssid и cloud/api_key
  │
  ├── нет WiFi-кредов            → SoftAP (captive portal)
  ├── есть WiFi, нет api_key     → SoftAP (предыдущий enroll не удался)
  └── есть и WiFi, и api_key     → Подключаемся к WiFi → РАБОЧИЙ режим
                                     │
                                     └── 5 раз FAIL подключения → SoftAP

В SoftAP установщик заполняет: WiFi (SSID/пароль) + поддомен компании + 6-значный код привязки
ESP подключается к WiFi и шлёт POST на &lt;backend&gt;/api/devices/enroll
  ├── 200 → сохраняем wifi-creds + api_key + backend_url в NVS, перезагружаемся → РАБОЧИЙ
  └── 4xx → НЕ сохраняем wifi-creds, остаёмся в SoftAP, показываем ошибку</pre>

  <h2>2. Captive portal (на ESP32 в SoftAP)</h2>
  <p>HTML-страница в LittleFS прошивки. Поля:</p>
  <ul>
    <li><b>WiFi-сеть</b> и пароль (выбор из <code>/api/scan</code>)</li>
    <li><b>Поддомен компании</b> (например <code>acme</code> для <code>acme.example.com</code>) —
      пока мультитенантности нет, можно оставить пустым или вводить любой Host)</li>
    <li><b>Код привязки</b> — 6 цифр, выдаёт админ из веб-панели</li>
  </ul>
  <p>Локальные эндпоинты на ESP:</p>
  <table class="docs-table api-table">
    <tbody>
      <tr><td><span class="m get">GET</span></td><td><code>/</code></td><td>captive portal HTML</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/scan</code></td><td><code>[{ssid, rssi, secure}]</code></td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/setup</code></td><td>тело: <code>{ssid, password, subdomain, enrollCode}</code> → возвращает <code>{accepted:true}</code> сразу, фронт поллит <code>/api/status</code></td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/status</code></td><td><code>{wifi, enroll, ip}</code></td></tr>
    </tbody>
  </table>

  <h2>3. POST /api/devices/enroll — главный запрос</h2>
  <pre>POST &lt;backend&gt;/api/devices/enroll
Content-Type: application/json

{
  "serialNumber": "VL-A3F82B01",
  "deviceSecret": "&lt;factory/secret из NVS, 64 hex&gt;",
  "enrollCode":   "&lt;6 цифр от админа&gt;"
}</pre>

  <table class="docs-table">
    <thead><tr><th>Код</th><th>Тело</th><th>Действие ESP</th></tr></thead>
    <tbody>
      <tr><td><b>200</b></td>
          <td><code>{apiKey, backendUrl, sendIntervalMs}</code></td>
          <td>Сохранить всё в NVS, ребут → РАБОЧИЙ режим</td></tr>
      <tr><td>400</td><td><code>{"error":"invalid_code"}</code></td>
          <td>Код неверный/просрочен/использован. Показать в captive portal, дать ввести заново.</td></tr>
      <tr><td>403</td><td><code>{"error":"invalid_secret"}</code></td>
          <td>Секрет не совпал с заводским. LED ошибки. Скорее всего серийник не наш.</td></tr>
      <tr><td>404</td><td><code>"unknown_device"</code> или <code>"unknown_subdomain"</code></td>
          <td>Серийник или поддомен не найдены. Проверить ввод поддомена.</td></tr>
      <tr><td>409</td><td><code>"already_claimed"</code></td>
          <td>Устройство уже привязано. Нужен <i>unclaim</i> от админа.</td></tr>
      <tr><td>410</td><td><code>"deactivated"</code></td>
          <td>Снято с обслуживания. Прекратить попытки.</td></tr>
    </tbody>
  </table>

  <div class="callout callout--warn">
    Поллинга нет. Один синхронный запрос — один результат.
  </div>

  <h2>4. Рабочий режим</h2>

  <h3>Цикл A — телеметрия (каждые 5 сек по умолчанию, см. sendIntervalMs)</h3>
<pre>POST &lt;backend_url&gt;/api/telemetry
Content-Type: application/json
Authorization: Bearer &lt;api_key из NVS&gt;

{
  "deviceId":  "VL-A3F82B01",
  "timestamp": "2026-04-30T12:00:00Z",
  "data": {
    "rpm":         1800,
    "speed":       85,
    "coolantTemp": 92,
    "oilPressure": 3.5,
    "fuelLevel":   45,
    "voltage":     13.8,
    "dtcCodes":    ["P0301"]
  }
}</pre>
  <p>
    <code>timestamp</code> — UTC ISO-8601 с буквой <code>Z</code>. Время по NTP, иначе фура
    будет «оффлайн» из-за неправильного времени.
  </p>

  <h3>Цикл B — heartbeat (каждые 60 сек)</h3>
<pre>POST &lt;backend_url&gt;/api/device/ping
Content-Type: application/json
Authorization: Bearer &lt;api_key&gt;

{ "deviceId": "VL-A3F82B01" }</pre>

  <h2>5. Обработка ошибок в рабочем режиме</h2>
  <table class="docs-table">
    <thead><tr><th>Код</th><th>Что делать</th></tr></thead>
    <tbody>
      <tr><td>200</td><td>Всё ок.</td></tr>
      <tr><td>401</td>
        <td>Ключ отозван (rotate-key/unclaim). <b>Стереть NVS cloud/api_key</b>, перейти в SoftAP — нужен новый enroll-код от админа.</td></tr>
      <tr><td>410</td>
        <td>Устройство деактивировано. Стереть api_key, в SoftAP — обращение к админу.</td></tr>
      <tr><td>таймаут / нет сети</td>
        <td>Положить пакет в LittleFS-буфер, переподключиться к WiFi, при восстановлении — слать буфер по 10 пакетов.</td></tr>
    </tbody>
  </table>

  <h2>6. Минимальный пример (Arduino)</h2>
<pre>#include &lt;HTTPClient.h&gt;
#include &lt;ArduinoJson.h&gt;
#include &lt;Preferences.h&gt;

bool enrollDevice(const String&amp; subdomain, const String&amp; enrollCode) {
  Preferences nvs;
  nvs.begin("factory", true);
    String serial = nvs.getString("serial");
    String secret = nvs.getString("secret");
  nvs.end();

  // Пока мультитенантности нет — собирай URL без поддомена,
  // backendUrl бэкенд вернёт сам в ответе.
  String url = "https://nonconf.ru/api/devices/enroll";
  // С мультитенантностью: "https://" + subdomain + ".example.com/api/devices/enroll"

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  JsonDocument req;
  req["serialNumber"] = serial;
  req["deviceSecret"] = secret;
  req["enrollCode"]   = enrollCode;
  String body; serializeJson(req, body);

  int code = http.POST(body);
  String resp = http.getString();
  http.end();

  if (code == 200) {
    JsonDocument r; deserializeJson(r, resp);
    nvs.begin("cloud", false);
      nvs.putString("api_key",     r["apiKey"].as&lt;const char*&gt;());
      nvs.putString("backend_url", r["backendUrl"].as&lt;const char*&gt;());
    nvs.end();
    return true;
  }
  return false;
}

void sendTelemetry(const TelemetryData&amp; t) {
  Preferences nvs;
  String key, url;
  nvs.begin("cloud", true);
    key = nvs.getString("api_key");
    url = nvs.getString("backend_url");
  nvs.end();

  HTTPClient http;
  http.begin(url + "/api/telemetry");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + key);   // ← новый заголовок

  JsonDocument doc;
  doc["deviceId"]  = "VL-A3F82B01";
  doc["timestamp"] = isoNowUtc();
  JsonObject data  = doc["data"].to&lt;JsonObject&gt;();
  data["rpm"]         = t.rpm;
  data["speed"]       = t.speed;
  data["coolantTemp"] = t.coolantTemp;
  // ...
  data["dtcCodes"].to&lt;JsonArray&gt;();

  String body; serializeJson(doc, body);
  int code = http.POST(body);
  http.end();

  if (code == 401 || code == 410) {
    nvs.begin("cloud", false); nvs.remove("api_key"); nvs.end();
    // Перейти в SoftAP — нужен новый enroll-код.
  }
}</pre>

  <h2>7. UTC время через NTP</h2>
<pre>#include &lt;time.h&gt;
configTime(0, 0, "pool.ntp.org", "time.google.com");

String isoNowUtc() {
  time_t now = time(nullptr);
  struct tm tm; gmtime_r(&amp;now, &amp;tm);
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &amp;tm);
  return String(buf);
}</pre>

  <h2>8. Сводка эндпоинтов для прошивки</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Когда</th><th>Auth</th></tr></thead>
    <tbody>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices/enroll</code></td>
          <td>Один раз при первичной настройке (из captive-portal)</td><td>secret в теле</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/telemetry</code></td>
          <td>В рабочем режиме каждые 5 сек</td><td><code>Authorization: Bearer</code></td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/device/ping</code></td>
          <td>В рабочем режиме каждые 60 сек</td><td><code>Authorization: Bearer</code></td></tr>
    </tbody>
  </table>

  <div class="callout callout--info">
    Бэк принимает оба варианта аутентификации в <code>/telemetry</code> и <code>/device/ping</code>:
    <code>Authorization: Bearer &lt;key&gt;</code> (новая прошивка) и
    <code>X-Device-Key: &lt;key&gt;</code> (legacy для симулятора).
    Прошивка должна слать <b>Bearer</b> — это новый стандарт.
  </div>

  <h2>9. Старая схема (deprecated, для понимания)</h2>
  <p>
    Старая прошивка опрашивала <code>POST /api/devices/provision</code> каждые 10 сек,
    параллельно админ через <code>/api/devices/claim</code> с фрагментом секрета привязывал.
    Эти эндпоинты остались в бэке для совместимости с симулятором и существующими
    тестовыми устройствами (<code>VL-PROV-001</code>, <code>VL-PROV-002</code>),
    но новая прошивка их не использует.
  </p>

  <nav class="next-prev">
    <router-link to="/docs/devices"><small>← Назад</small>Управление устройствами</router-link>
    <router-link class="next" to="/docs/api"><small>Дальше →</small>API эндпоинты</router-link>
  </nav>
</template>
