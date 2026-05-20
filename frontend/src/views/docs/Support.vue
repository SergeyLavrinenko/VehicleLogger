<template>
  <h1>Что не готово и решение проблем</h1>
  <p class="lead">
    Честный roadmap и список частых проблем — что искать, если что-то не работает.
  </p>

  <h2>Что готово</h2>
  <ul>
    <li>✅ <b>HTTPS</b> с wildcard-cert <code>*.nonconf.ru</code> от Let's Encrypt
      (DNS-01 через Beget API). Auto-renewal через acme.sh cron.</li>
    <li>✅ <b>Мультитенантность</b> с поддоменами: таблица <code>Tenants</code>,
      <code>TenantId</code> в Devices/Vehicles/Users/EnrollmentCodes,
      middleware резолва по <code>Host</code>, фильтрация всех запросов.</li>
    <li>✅ <b>JWT</b> с <code>tenant_id</code>-claim, защита от cross-tenant токенов.</li>
    <li>✅ Регистрация новой компании одной формой (создаёт tenant + первого admin'а с генератором пароля).</li>
    <li>✅ <b>Provisioning flow</b> — <code>/api/devices/enroll</code> с 6-значным кодом.
      Старый <code>/provision</code> + <code>/claim</code> оставлен для совместимости.</li>
    <li>✅ Графики в реальном времени, polling 2-5 сек, дашборд KPI, журнал телеметрии, алерты, заправки.</li>
  </ul>

  <h2>Что ещё не готово (TODO)</h2>
  <ul>
    <li><b>Telegram-бот</b> — для водителей: вход заправок, алерты. Зона Пайрава.</li>
    <li><b>AI-анализатор</b> — детекция аномалий и рекомендации. Алерты пока не генерятся.</li>
    <li><b>WebSocket</b> — заменить polling на push (Чекпоинт 7 в CLAUDE.md).</li>
    <li><b>Postgres</b> — сейчас SQLite. Для тенантов от десятков до сотен устройств — ок.
      На тысячи — переключим провайдер EF Core.</li>
    <li><b>Хранение хеша API-ключа</b> вместо plaintext (по PROVISIONING.md).
      Сейчас в БД лежит plaintext, plaintext должен жить только в provisioning_token (10 мин).</li>
    <li><b>Driver UI</b> — задумано, но интерфейса для роли <code>driver</code> пока нет.</li>
    <li><b>Управление пользователями внутри тенанта</b> — admin может создавать ещё
      админов/водителей своего тенанта. Сейчас только через первый admin при создании компании.</li>
    <li><b>Удаление устройств / unenroll</b> с очисткой телеметрии — пока есть только Unclaim.</li>
  </ul>

  <h2>Частые проблемы</h2>
  <table class="docs-table">
    <thead><tr><th>Симптом</th><th>Причина / решение</th></tr></thead>
    <tbody>
      <tr>
        <td>«Последний пакет: 2 ч назад» при работающем симуляторе</td>
        <td>Время на машине неверное. Симулятор шлёт <code>new Date().toISOString()</code> —
          ts уезжает в будущее/прошлое относительно сервера. Проверь часы.</td>
      </tr>
      <tr>
        <td><code>POST /api/telemetry → 401</code></td>
        <td>Не совпадают <code>X-Device-Key</code>/Bearer и <code>deviceId</code>. Ключ привязан к одному serial.</td>
      </tr>
      <tr>
        <td><code>POST /api/devices/enroll → 400 invalid_code</code></td>
        <td>Код не найден / использован / просрочен / не от этого тенанта.
          Сгенерируй новый на правильном поддомене и введи в captive-portal.</td>
      </tr>
      <tr>
        <td><code>POST /api/devices/enroll → 403 wrong_tenant</code></td>
        <td>Устройство уже привязано к <i>другому</i> тенанту. Установщик ввёл не тот поддомен,
          или нужен <i>unclaim</i> в той компании.</td>
      </tr>
      <tr>
        <td><code>POST /api/devices/enroll → 404 unknown_subdomain</code></td>
        <td>Поддомен компании не зарегистрирован. Проверь поле «поддомен» в captive-portal.</td>
      </tr>
      <tr>
        <td><code>POST /api/devices/enroll → 404 unknown_device</code></td>
        <td>Серийник не зарегистрирован в БД. Tenant admin должен сначала
          <router-link to="/devices">«Устройства» → + Зарегистрировать</router-link>.</td>
      </tr>
      <tr>
        <td><code>POST /api/devices/enroll → 403 invalid_secret</code></td>
        <td>SHA-256 от <code>factory/secret</code> не совпадает с тем что в БД.
          Прошивка зашита неправильным секретом или серийник чужой.</td>
      </tr>
      <tr>
        <td><code>403 tenant_mismatch</code> в админке</td>
        <td>JWT-токен от другой компании. Перезайди на правильный поддомен.</td>
      </tr>
      <tr>
        <td><code>403 use_subdomain</code></td>
        <td>Tenant admin пытается зайти на apex (<code>nonconf.ru</code>) под своим токеном.
          Зайди на свой <code>&lt;sub&gt;.nonconf.ru</code>.</td>
      </tr>
      <tr>
        <td><code>404 unknown_subdomain</code> в API</td>
        <td>Запрос идёт на поддомен, которого нет в БД. Создай тенант через super-admin или проверь URL.</td>
      </tr>
      <tr>
        <td>Login → «неверный email/пароль»</td>
        <td>Email чувствителен к регистру (нижний регистр). Также юзер должен принадлежать
          этому тенанту: на <code>acme.nonconf.ru</code> пускают только пользователей с
          <code>tenant_id == acme</code>.</td>
      </tr>
      <tr>
        <td>На странице фуры пусто</td>
        <td>Фура без устройства, либо устройство ни разу не присылало пакетов.
          Запусти симулятор или подключи реальный ESP32.</td>
      </tr>
      <tr>
        <td>«Этот поддомен не зарегистрирован» на /login</td>
        <td>Зашёл на <code>&lt;что-то&gt;.nonconf.ru</code>, чего нет в БД. Super-admin создаёт
          компании на <code>https://nonconf.ru/tenants</code>.</td>
      </tr>
      <tr>
        <td>«unauthorized» после долгой паузы</td>
        <td>JWT протух (24 часа). Перезайди.</td>
      </tr>
    </tbody>
  </table>

  <h2>Где смотреть логи (бэк)</h2>
  <pre>ssh user@91.188.212.119
sudo journalctl -u vehiclelogger -f          # хвост логов бэка
sudo systemctl status vehiclelogger          # статус сервиса
sudo tail -f /var/log/nginx/vehiclelogger.access.log
sudo tail -f /var/log/nginx/vehiclelogger.error.log
~/.acme.sh/acme.sh --list                    # текущие сертификаты</pre>

  <h2>Контакты</h2>
  <p>По вопросам — Тимуру.</p>

  <nav class="next-prev">
    <router-link to="/docs/simulator"><small>← Назад</small>Симулятор</router-link>
    <span />
  </nav>
</template>
