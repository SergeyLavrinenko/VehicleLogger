<template>
  <h1>Компании / тенанты</h1>
  <p class="lead">
    VehicleLogger — мультитенантная система. Каждая компания получает изолированный
    набор устройств, фур, пользователей и собственный поддомен <code>&lt;subdomain&gt;.nonconf.ru</code>.
  </p>

  <h2>Архитектура</h2>
  <pre>nonconf.ru                ← apex, super-admin (создание компаний)
├─ acme.nonconf.ru        ← компания ACME (admin@acme.test, свои устройства)
├─ delta.nonconf.ru       ← компания Delta (admin@delta.test, свои устройства)
└─ &lt;любой&gt;.nonconf.ru     ← если subdomain не зарегистрирован → 404 unknown_subdomain</pre>

  <p>
    Один и тот же сервер обслуживает все поддомены через wildcard TLS-cert
    (<code>*.nonconf.ru</code>). Бэкенд резолвит тенанта по <code>Host</code>-заголовку
    и автоматически фильтрует все запросы по <code>WHERE TenantId = current</code>.
  </p>

  <h2>Роли</h2>
  <table class="docs-table">
    <thead><tr><th>Роль</th><th>Где живёт</th><th>Может</th></tr></thead>
    <tbody>
      <tr>
        <td><b>super-admin</b></td>
        <td><code>nonconf.ru</code> (apex)</td>
        <td>Создавать/удалять компании, видеть всё.<br>На поддомен зайти <b>не может</b> (403).</td>
      </tr>
      <tr>
        <td><b>tenant admin</b></td>
        <td><code>&lt;sub&gt;.nonconf.ru</code></td>
        <td>Управлять устройствами, кодами привязки, фурами своей компании.<br>На apex и чужой поддомен — 403.</td>
      </tr>
      <tr>
        <td><b>tenant driver</b></td>
        <td><code>&lt;sub&gt;.nonconf.ru</code></td>
        <td>Видит только свою фуру (через Telegram-бот, когда подключим).</td>
      </tr>
    </tbody>
  </table>

  <h2>Создание новой компании</h2>
  <p>Делает super-admin на <code>nonconf.ru</code>:</p>
  <ol class="steps">
    <li>Войти на <code>https://nonconf.ru</code> как <code>admin@vl.local / admin1234</code>.</li>
    <li>Перейти в <router-link to="/tenants">«Компании»</router-link> → <b>+ Зарегистрировать компанию</b>.</li>
    <li>Заполнить:
      <ul>
        <li><b>Поддомен</b> (a-z, 0-9, дефис, 3-63 символа) — например <code>acme</code>.</li>
        <li><b>Название компании</b> — отобразится в шапке у пользователей.</li>
        <li><b>Email первого admin'а</b>.</li>
        <li><b>Пароль</b> (опционально — иначе сгенерится 12-значный).</li>
      </ul>
    </li>
    <li>Нажать <b>Создать</b>. Модалка покажет:
      <ul>
        <li>URL панели <code>https://acme.nonconf.ru</code></li>
        <li>Email и <b>пароль</b> первого admin'а — <i>показывается ровно один раз</i>.</li>
      </ul>
    </li>
    <li>Передать креды представителю компании. Он логинится на свой поддомен и работает в изолированной среде.</li>
  </ol>

  <h2>Изоляция данных</h2>
  <p>На каждой сущности (Device, Vehicle, User, EnrollmentCode) есть поле <code>TenantId</code>.
    Все API-эндпоинты автоматически фильтруют по нему:</p>
  <ul>
    <li><b>На поддомене</b>: <code>WHERE TenantId == &lt;current&gt;</code> — admin видит только свою компанию.</li>
    <li><b>На apex</b>: super-admin видит вообще всё (для отладки), без фильтра.</li>
    <li>JWT содержит <code>tenant_id</code>-claim. Если кто-то попробует использовать токен на чужом поддомене — middleware вернёт 403 <code>tenant_mismatch</code>.</li>
    <li>Если зайти на несуществующий поддомен (<code>unknown.nonconf.ru</code>) — 404 <code>unknown_subdomain</code>.</li>
  </ul>

  <h2>Жизненный цикл устройства в мультитенантности</h2>
  <ol class="steps">
    <li>Tenant admin регистрирует устройство через
      <router-link to="/devices">«Устройства» → + Зарегистрировать</router-link> на своём поддомене.
      Бэк ставит <code>device.TenantId = tenant.Id</code>.</li>
    <li>Tenant admin генерирует enrollment-код там же — он тоже привязан к тенанту.</li>
    <li>Установщик в captive-portal ESP32 вводит:
      WiFi + <b>поддомен компании</b> + <b>код привязки</b>.</li>
    <li>ESP32 шлёт <code>POST https://&lt;sub&gt;.nonconf.ru/api/devices/enroll</code>. Бэкенд проверяет:
      <ul>
        <li>устройство существует и принадлежит этому tenant'у (или ещё не привязано — тогда привяжется);</li>
        <li>enroll-код принадлежит этому tenant'у, не использован, не просрочен.</li>
      </ul>
    </li>
    <li>Возвращается <code>apiKey</code>. ESP сохраняет в NVS и шлёт телеметрию на <code>https://&lt;sub&gt;.nonconf.ru/api/telemetry</code>.</li>
  </ol>

  <h2>Удаление компании</h2>
  <p>
    Super-admin → /tenants → кнопка <b>Удалить</b>. Удалять можно только пустые
    тенанты (без устройств и пользователей). Сначала нужно отвязать всё.
  </p>

  <div class="callout callout--warn">
    <b>Старые тестовые устройства</b> (<code>VL-A3F82B01</code>, <code>VL-PROV-001</code>, <code>VL-PROV-002</code>)
    были созданы до мультитенантности и не привязаны ни к одному тенанту.
    Они видны только super-admin'у на apex. Симулятор device-sim продолжает их использовать
    через legacy-эндпоинт <code>/api/telemetry</code> (без tenant-фильтра).
  </div>

  <h2>API</h2>
  <table class="docs-table api-table">
    <thead><tr><th>Метод</th><th>URL</th><th>Кто может</th></tr></thead>
    <tbody>
      <tr><td><span class="m get">GET</span></td><td><code>/api/auth/context</code></td><td>любой (без auth) — узнать какой тенант на текущем хосте</td></tr>
      <tr><td><span class="m post">POST</span></td><td><code>/api/tenants</code></td><td>super-admin — создать компанию + первого admin'а</td></tr>
      <tr><td><span class="m get">GET</span></td><td><code>/api/tenants</code></td><td>super-admin — список компаний со счётчиками</td></tr>
      <tr><td><span class="m delete">DELETE</span></td><td><code>/api/tenants/{id}</code></td><td>super-admin — удалить пустого тенанта</td></tr>
    </tbody>
  </table>

  <nav class="next-prev">
    <router-link to="/docs/web"><small>← Назад</small>Веб-панель</router-link>
    <router-link class="next" to="/docs/devices"><small>Дальше →</small>Управление устройствами</router-link>
  </nav>
</template>
