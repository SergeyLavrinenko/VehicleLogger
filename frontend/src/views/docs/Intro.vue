<template>
  <h1>Что это и быстрый старт</h1>
  <p class="lead">
    VehicleLogger — мультитенантная система мониторинга фур.
    ESP32 в кабине читает CAN-шину, шлёт телеметрию на сервер,
    админ компании видит её в виде графиков. Каждая компания получает свой
    поддомен <code>&lt;sub&gt;.nonconf.ru</code> с изолированными данными.
  </p>

  <h2>Архитектура</h2>
  <ul>
    <li><b>Устройство (ESP32)</b> — читает CAN-шину, шлёт телеметрию по WiFi через HTTPS.</li>
    <li><b>Бэкенд + веб-панель</b> — .NET 10 + SQLite + Vue 3. Один бэкенд обслуживает все
      поддомены, тенант резолвится по <code>Host</code>-заголовку запроса.</li>
    <li><b>Telegram-бот водителя</b> — заправки и алерты (в работе).</li>
  </ul>

  <h2>Поток данных</h2>
  <pre>ESP32 (CAN)
  │  HTTPS POST /api/telemetry
  │  Authorization: Bearer &lt;api-key&gt;
  ▼
&lt;sub&gt;.nonconf.ru ─► Бэкенд (.NET) ─► SQLite (фильтр по TenantId)
                       │
                       │  GET /api/vehicles, /telemetry, /alerts
                       ▼
                Vue-фронт (polling 2-5 сек)</pre>

  <h2>Кому какие хосты</h2>
  <table class="docs-table">
    <thead><tr><th>URL</th><th>Кто заходит</th><th>Что видит</th></tr></thead>
    <tbody>
      <tr>
        <td><code>nonconf.ru</code></td>
        <td>Super-admin платформы</td>
        <td>Все компании, регистрация новых, глобальные данные</td>
      </tr>
      <tr>
        <td><code>&lt;sub&gt;.nonconf.ru</code></td>
        <td>Admin компании <code>&lt;sub&gt;</code></td>
        <td>Только свои устройства, фуры, заправки</td>
      </tr>
      <tr>
        <td><code>91.188.212.119.nip.io</code></td>
        <td>Симулятор / отладка</td>
        <td>Legacy режим, без тенанта</td>
      </tr>
    </tbody>
  </table>

  <h2>Быстрый старт</h2>

  <h3>Если ты super-admin платформы</h3>
  <ol class="steps">
    <li>Войди на <code>https://nonconf.ru</code> с <code>admin@vl.local</code> / <code>admin1234</code>.</li>
    <li>Открой <router-link to="/tenants">«Компании»</router-link> → <b>+ Зарегистрировать компанию</b>.</li>
    <li>Поддомен <code>acme</code>, название, email будущего admin'а.</li>
    <li>Бэкенд сгенерирует пароль. <b>Скопируй сразу — больше не покажется.</b></li>
    <li>Передай <code>https://acme.nonconf.ru</code> + email + пароль клиенту.</li>
  </ol>

  <h3>Если ты admin компании</h3>
  <ol class="steps">
    <li>Зайди на <code>https://&lt;sub&gt;.nonconf.ru/login</code> с выданными кредами.</li>
    <li>«Устройства» → <b>+ Зарегистрировать</b> → серийник + сгенерированный 256-битный секрет (зашить в NVS прошивки).</li>
    <li>В секции «Коды привязки» → <b>+ Сгенерировать код</b> → 6-значный код для установщика.</li>
    <li>Установщик в captive-portal ESP32 вводит WiFi + поддомен <code>&lt;sub&gt;</code> + код.</li>
    <li>Через ~10 сек устройство в админке как <span class="badge online">active</span>.</li>
  </ol>

  <h3>Если ты разработчик прошивки</h3>
  <p>
    Открой <router-link to="/docs/firmware">«Прошивка устройства»</router-link>.
    ESP32 шлёт на <code>https://&lt;sub&gt;.nonconf.ru/api/devices/enroll</code> и получает API-ключ.
  </p>

  <h2>Документация по разделам</h2>
  <table class="docs-table">
    <tbody>
      <tr><td><router-link to="/docs/web">Веб-панель</router-link></td>
          <td>Вход, дашборд, страница фуры, роли</td></tr>
      <tr><td><router-link to="/docs/tenants">Компании</router-link></td>
          <td>Мультитенантность, поддомены, super-admin</td></tr>
      <tr><td><router-link to="/docs/devices">Устройства</router-link></td>
          <td>Регистрация, выдача кодов, привязка</td></tr>
      <tr><td><router-link to="/docs/firmware">Прошивка</router-link></td>
          <td>Что должна делать ESP32</td></tr>
      <tr><td><router-link to="/docs/api">API</router-link></td>
          <td>Все эндпоинты</td></tr>
      <tr><td><router-link to="/docs/simulator">Симулятор</router-link></td>
          <td>Тестирование без железа</td></tr>
      <tr><td><router-link to="/docs/support">Roadmap / проблемы</router-link></td>
          <td>Что не готово, частые ошибки</td></tr>
    </tbody>
  </table>

  <nav class="next-prev">
    <span />
    <router-link class="next" to="/docs/web"><small>Дальше →</small>Веб-панель</router-link>
  </nav>
</template>
