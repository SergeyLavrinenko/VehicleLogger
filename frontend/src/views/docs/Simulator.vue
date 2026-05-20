<template>
  <h1>Симулятор устройства</h1>
  <p class="lead">
    Node.js-программа в <code>tools/device-sim/</code> репозитория.
    Шлёт реалистичные пакеты с твоего ноута — для разработки и демо без железки.
  </p>

  <h2>Что внутри</h2>
  <ul>
    <li><code>sim.js</code> — программа.</li>
    <li><code>run.bat</code> — обёртка для Windows. Двойной клик → откроется консоль.</li>
    <li><code>run.sh</code> — то же для Linux/macOS.</li>
  </ul>
  <p>
    Зависимостей нет, нужен только Node.js 18+. Использует встроенный <code>fetch</code>.
  </p>

  <h2>Запуск</h2>
  <pre>cd tools/device-sim
node sim.js               # интерактивный режим
node sim.js --once        # один пакет и выход (для проверки)</pre>

  <h2>Команды (после старта)</h2>
  <table class="docs-table">
    <thead><tr><th>Команда</th><th>Алиас</th><th>Что делает</th></tr></thead>
    <tbody>
      <tr><td><code>start</code></td>          <td>s</td><td>Запустить цикл (по умолчанию каждые 5 сек)</td></tr>
      <tr><td><code>stop</code></td>           <td>x</td><td>Остановить</td></tr>
      <tr><td><code>send</code></td>           <td>—</td><td>Один пакет</td></tr>
      <tr><td><code>ping</code></td>           <td>—</td><td>Один heartbeat</td></tr>
      <tr><td><code>anomaly overheat</code></td><td>a</td><td>Перегрев ОЖ (~106°C)</td></tr>
      <tr><td><code>anomaly oilpressure</code></td><td>a</td><td>Падение давления масла</td></tr>
      <tr><td><code>anomaly dtc</code></td>    <td>a</td><td>Отдаёт DTC-коды P0301, P0217</td></tr>
      <tr><td><code>anomaly none</code></td>   <td>a</td><td>Снять аномалию</td></tr>
      <tr><td><code>interval 2000</code></td>  <td>i</td><td>Сменить частоту (мс)</td></tr>
      <tr><td><code>device VL-A3F82B02</code></td><td>d</td><td>Сменить deviceId</td></tr>
      <tr><td><code>key dev-key-002</code></td><td>k</td><td>Сменить X-Device-Key</td></tr>
      <tr><td><code>url http://localhost:5000</code></td><td>u</td><td>Сменить URL бэка</td></tr>
      <tr><td><code>status</code></td>         <td>—</td><td>Текущее состояние и счётчики</td></tr>
      <tr><td><code>reset</code></td>          <td>—</td><td>Сбросить накопленный state (rpm, fuel и т.д.)</td></tr>
      <tr><td><code>help</code></td>           <td>h</td><td>Список команд</td></tr>
      <tr><td><code>quit</code></td>           <td>q</td><td>Выход</td></tr>
    </tbody>
  </table>

  <h2>Дефолты</h2>
  <table class="docs-table">
    <tbody>
      <tr><td>URL</td><td><code>https://nonconf.ru</code></td></tr>
      <tr><td>deviceId</td><td><code>VL-A3F82B01</code></td></tr>
      <tr><td>X-Device-Key</td><td><code>dev-key-001</code></td></tr>
      <tr><td>интервал</td><td>5000 мс</td></tr>
      <tr><td>ping</td><td>раз в 6 пакетов (~30 сек)</td></tr>
    </tbody>
  </table>
  <p>
    Эти пары serial+key зашиты в seed бэкенда — можно слать прямо сейчас.
    Симулятор работает в legacy-режиме (без тенанта) — устройство <code>VL-A3F82B01</code> не привязано
    ни к одной компании, видно только super-admin'у на <code>nonconf.ru</code>.
  </p>
  <p>
    Чтобы протестировать <b>tenant-flow</b> — зарегистрируй новое устройство через
    <code>POST /api/devices</code> на своём поддомене, выпусти enroll-код,
    запусти симулятор с этими параметрами:
  </p>
<pre>node sim.js \
  --url=https://acme.nonconf.ru \
  --device=VL-MY-001 \
  --key=&lt;ключ из ответа /enroll&gt;</pre>

  <h2>CLI-флаги (без интерактива)</h2>
  <pre>node sim.js --once
node sim.js --interval=2000 --anomaly=overheat
node sim.js --device=VL-A3F82B02 --key=dev-key-002
node sim.js --url=http://localhost:5000</pre>

  <h2>Что симулирует</h2>
  <ul>
    <li>Реалистичный дрейф параметров вокруг базовых значений
      (RPM ~1700, скорость ~70, темп ОЖ ~88°C и т.д.).</li>
    <li>Уровень топлива плавно падает (как при езде).</li>
    <li>Heartbeat параллельно с телеметрией.</li>
    <li>Аномалии (перегрев / давление / DTC) — для проверки будущего AI-анализатора.</li>
    <li>Формат запросов <b>идентичен</b> тому, который будет слать ESP32.</li>
  </ul>

  <nav class="next-prev">
    <router-link to="/docs/api"><small>← Назад</small>API эндпоинты</router-link>
    <router-link class="next" to="/docs/support"><small>Дальше →</small>Что не готово</router-link>
  </nav>
</template>
