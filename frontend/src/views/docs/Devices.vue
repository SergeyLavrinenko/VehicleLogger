<template>
  <h1>Управление устройствами</h1>
  <p class="lead">
    Жизненный цикл: <b>регистрация</b> в БД → выдача <b>кода привязки</b> установщику →
    ESP32 в captive-portal делает <b>enroll</b> → телеметрия. Все действия — на странице
    <router-link to="/devices">«Устройства»</router-link> своего тенанта.
  </p>

  <h2>Статусы устройства</h2>
  <table class="docs-table">
    <thead><tr><th>Статус</th><th>Что значит</th></tr></thead>
    <tbody>
      <tr><td><span class="badge offline">manufactured</span></td>
          <td>Зарегистрировано в БД (есть serial + secret_hash). Если ESP запустить — он будет ждать enroll-код.</td></tr>
      <tr><td><span class="badge warning">claimed</span></td>
          <td>Старая схема: ключ выпущен, ESP его ещё не забрал. В новой схеме (enroll) — после ротации ключа.</td></tr>
      <tr><td><span class="badge online">active</span></td>
          <td>ESP получил ключ через <code>/enroll</code> (или legacy <code>/provision</code>) и шлёт телеметрию.</td></tr>
      <tr><td><span class="badge critical">deactivated</span></td>
          <td>Отключено вручную. На <code>/enroll</code>/<code>/provision</code> отвечает 410.</td></tr>
    </tbody>
  </table>

  <h2>Шаг 1. Регистрация устройства в БД</h2>
  <p>
    Делает tenant admin на своём поддомене. Сохраняет серийник + SHA-256 от секрета.
    Устройство автоматически привязывается к <b>тенанту того, кто регистрирует</b>.
  </p>
  <ol class="steps">
    <li>На своём поддомене <code>https://&lt;sub&gt;.nonconf.ru/devices</code> →
      <b>+ Зарегистрировать</b>.</li>
    <li>Введи серийник <code>VL-XXXXXXXX</code> (8 hex от MAC ESP32, по соглашению).</li>
    <li>Секрет — оставь пустым (сгенерится 256-битный) или введи свой 64-hex.</li>
    <li><b>Скопируй полный секрет!</b> Показывается ровно один раз. Зашей в NVS прошивки в
      <code>factory/secret</code>. См. <router-link to="/docs/firmware">«Прошивка»</router-link>.</li>
  </ol>

  <h2>Шаг 2. Установка в фуру + код привязки</h2>
  <p>Когда устройство уже стоит в фуре:</p>
  <ol class="steps">
    <li>На «Устройствах» → секция <b>«Коды привязки»</b> → <b>+ Сгенерировать код</b>.
      Опциональная метка («Фура МАН А123») — для своего удобства.</li>
    <li>Бэкенд возвращает 6-значный код (например <code>428193</code>). Показывается один раз.
      Код привязан к <b>твоему тенанту</b> — зайдёт только на <code>&lt;твой-sub&gt;.nonconf.ru</code>.</li>
    <li>Действует 30 минут, использовать можно один раз.</li>
    <li>Установщик подключается телефоном к WiFi устройства <code>VehicleLogger-XXXXXXXX</code>
      (пароль на наклейке).</li>
    <li>В captive-portal вводит:
      <ul>
        <li>домашний WiFi (SSID и пароль)</li>
        <li><b>поддомен компании</b>: <code>&lt;sub&gt;</code> (без <code>.nonconf.ru</code>)</li>
        <li>код привязки</li>
      </ul>
    </li>
    <li>ESP подключается к WiFi → шлёт <code>POST https://&lt;sub&gt;.nonconf.ru/api/devices/enroll</code>
      → получает API-ключ → ребут → шлёт телеметрию.</li>
    <li>Через несколько секунд устройство в админке как <span class="badge online">active</span>.</li>
  </ol>

  <div class="callout callout--info">
    Если установщик ввёл код, но что-то пошло не так — отзови его кнопкой <b>Отозвать</b>
    в списке кодов и сгенерируй новый.
  </div>

  <h2>Шаг 3. Эксплуатация</h2>
  <p>На каждой строке таблицы устройств:</p>
  <ul>
    <li><b>Фура</b> — переназначить устройство на другую фуру внутри своей компании. Ключ не меняется.</li>
    <li><b>Ротация</b> — выпустить новый API-ключ. Устройство получит 401 → стирает ключ из NVS
      → SoftAP — нужен новый enroll-код.</li>
    <li><b>Unclaim</b> — отвязать. Статус → manufactured, ключ обнуляется. Используется при
      продаже устройства / передаче в другую компанию (там нужно зарегистрировать заново).</li>
  </ul>

  <h2>Тестовые устройства (общие, без тенанта)</h2>
  <p>
    Для отладки прошивки/симулятора. Эти устройства существовали до мультитенантности —
    не привязаны к компании, видны только super-admin'у на apex:
  </p>
  <table class="docs-table">
    <thead><tr><th>Серийник</th><th>Полный секрет</th><th>Кому</th></tr></thead>
    <tbody>
      <tr>
        <td><code>VL-PROV-001</code></td>
        <td><code style="font-size:10px;">a1b2c3d40000000000000000000000000000000000000000000000000000abcd</code></td>
        <td>Старый <code>/provision</code> + <code>/claim</code> flow</td>
      </tr>
      <tr>
        <td><code>VL-PROV-002</code></td>
        <td><code style="font-size:10px;">deadbeef0000000000000000000000000000000000000000000000000000feed</code></td>
        <td>Резерв</td>
      </tr>
      <tr>
        <td><code>VL-A3F82B01</code></td>
        <td><i>—</i> (api-key захардкожен <code>dev-key-001</code>)</td>
        <td>Симулятор <code>tools/device-sim/sim.js</code></td>
      </tr>
    </tbody>
  </table>

  <nav class="next-prev">
    <router-link to="/docs/tenants"><small>← Назад</small>Компании</router-link>
    <router-link class="next" to="/docs/firmware"><small>Дальше →</small>Прошивка устройства</router-link>
  </nav>
</template>
