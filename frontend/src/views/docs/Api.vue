<template>
  <h1>API эндпоинты</h1>
  <p class="lead">
    Все эндпоинты обслуживаются на любом из <code>nonconf.ru</code>,
    <code>&lt;sub&gt;.nonconf.ru</code>, <code>91.188.212.119.nip.io</code>.
    Бэкенд резолвит тенанта по <code>Host</code>.
  </p>

  <h2>Аутентификация</h2>
  <ul>
    <li><b>Устройство (новая прошивка)</b>: <code>Authorization: Bearer &lt;api-key&gt;</code></li>
    <li><b>Устройство (legacy / симулятор)</b>: <code>X-Device-Key: &lt;api-key&gt;</code> — оба работают</li>
    <li><b>Веб-панель</b>: <code>Authorization: Bearer &lt;jwt&gt;</code></li>
    <li><b>Enroll, provision, login, /auth/context, /health</b>: без авторизации</li>
  </ul>

  <h2>Tenant-резолюция</h2>
  <p>
    Все эндпоинты с JWT автоматически фильтруют по <code>tenant_id</code> текущего хоста.
    Если JWT.tenant_id не совпадает с tenant_id хоста — <code>403 tenant_mismatch</code>.
    Если хост — несуществующий поддомен — <code>404 unknown_subdomain</code> (для super-admin токена;
    без auth — 401).
  </p>

  <h2>Контекст и аутентификация</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Описание</th></tr></thead>
    <tbody>
      <tr><td><span class="m get">GET</span></td><td><code>/api/auth/context</code></td>
          <td>Без auth. Возвращает <code>{host, isSuperAdminHost, tenant, requestedSubdomain}</code> — для UI до логина.</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/auth/login</code></td>
          <td>Email/password → JWT (24ч). Скоуп пользователя зависит от Host.</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/health</code></td>
          <td>Health-check.</td></tr>
    </tbody>
  </table>

  <h2>Тенанты (только super-admin на apex)</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Описание</th></tr></thead>
    <tbody>
      <tr><td><span class="m post">POST</span></td><td><code>/api/tenants</code></td>
          <td>Создать компанию + первого admin'а.</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/tenants</code></td>
          <td>Список компаний со счётчиками устройств/фур/юзеров.</td></tr>
      <tr><td><span class="m delete">DELETE</span></td><td><code>/api/tenants/{id}</code></td>
          <td>Удалить пустого тенанта.</td></tr>
    </tbody>
  </table>

  <h3>POST /api/tenants</h3>
<pre>POST nonconf.ru/api/tenants
Authorization: Bearer &lt;super-admin jwt&gt;

{
  "subdomain":     "acme",         // a-z, 0-9, '-', 3-63 символа
  "name":          "ACME Logistics",
  "adminEmail":    "admin@acme.test",
  "adminPassword": "опционально, иначе сгенерится"
}

→ 200 {
   id, subdomain, name, url, createdAt,
   admin: { email, password, name }    // password один раз!
}
→ 400 invalid_subdomain | invalid_admin_email
→ 409 subdomain_exists | admin_email_exists</pre>

  <h2>Устройство (без авторизации админа)</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Описание</th><th>Auth</th></tr></thead>
    <tbody>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices/enroll</code></td>
          <td>Получить API-ключ (новая прошивка)</td><td>secret + код в теле</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices/provision</code></td>
          <td>Поллинг ключа (legacy)</td><td>secret в теле</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/telemetry</code></td>
          <td>Пакет телеметрии</td><td>Bearer / X-Device-Key</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/device/ping</code></td>
          <td>Heartbeat</td><td>Bearer / X-Device-Key</td></tr>
    </tbody>
  </table>

  <h3>POST /api/devices/enroll</h3>
<pre>POST https://&lt;sub&gt;.nonconf.ru/api/devices/enroll
Content-Type: application/json

{
  "serialNumber": "VL-A3F82B01",
  "deviceSecret": "&lt;64 hex&gt;",
  "enrollCode":   "&lt;6 цифр&gt;"
}

→ 200 {"apiKey":"...","backendUrl":"https://&lt;sub&gt;.nonconf.ru","sendIntervalMs":5000}
→ 400 invalid_code
→ 403 invalid_secret | wrong_tenant
→ 404 unknown_device | unknown_subdomain
→ 409 already_claimed
→ 410 deactivated</pre>

  <h3>POST /api/telemetry</h3>
<pre>POST https://&lt;sub&gt;.nonconf.ru/api/telemetry
Content-Type: application/json
Authorization: Bearer &lt;api-key&gt;

{
  "deviceId":  "VL-A3F82B01",
  "timestamp": "2026-04-30T12:00:00Z",
  "data": {
    "rpm": 1800, "speed": 85, "coolantTemp": 92,
    "oilPressure": 3.5, "fuelLevel": 45, "voltage": 13.8,
    "dtcCodes": ["P0301"]
  }
}

→ 200 {"stored":true,"id":N}
→ 401 неверный или отсутствующий ключ
→ 400 нет timestamp / кривой JSON</pre>

  <h2>Коды привязки (JWT tenant admin)</h2>
  <table class="docs-table api-table">
    <tbody>
      <tr><td><span class="m post">POST</span></td><td><code>/api/enrollment-codes</code></td>
          <td>Создать 6-значный код для своего тенанта. Plaintext один раз.</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/enrollment-codes</code></td>
          <td>Список активных кодов своего тенанта.</td></tr>
      <tr><td><span class="m delete">DELETE</span></td><td><code>/api/enrollment-codes/{id}</code></td>
          <td>Отозвать неиспользованный код.</td></tr>
    </tbody>
  </table>

  <h2>Устройства (JWT tenant admin)</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Описание</th></tr></thead>
    <tbody>
      <tr><td><span class="m get">GET</span></td>  <td><code>/api/devices</code></td><td>Список устройств своего тенанта. Фильтр <code>?status=manufactured</code></td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices</code></td><td>Зарегистрировать устройство в БД (status=manufactured)</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices/claim</code></td><td>Старая схема: привязка по фрагменту QR</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices/{id}/unclaim</code></td><td>Отвязать (status → manufactured)</td></tr>
      <tr><td><span class="m put">PUT</span></td>  <td><code>/api/devices/{id}/vehicle</code></td><td>Назначить на фуру</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/devices/{id}/rotate-key</code></td><td>Выпустить новый ключ</td></tr>
    </tbody>
  </table>

  <h2>Чтение для веб-панели (JWT tenant admin)</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Описание</th></tr></thead>
    <tbody>
      <tr><td><span class="m get">GET</span></td><td><code>/api/dashboard</code></td><td>KPI-сводка тенанта</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/vehicles</code></td><td>Список фур тенанта</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/vehicles/{id}</code></td><td>Детали фуры (404 если не из этого тенанта)</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/vehicles/{id}/telemetry?limit=N</code></td><td>Телеметрия</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/vehicles/{id}/alerts</code></td><td>Алерты</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/vehicles/{id}/refuels</code></td><td>Заправки</td></tr>
    </tbody>
  </table>

  <nav class="next-prev">
    <router-link to="/docs/firmware"><small>← Назад</small>Прошивка устройства</router-link>
    <router-link class="next" to="/docs/simulator"><small>Дальше →</small>Симулятор</router-link>
  </nav>
</template>
