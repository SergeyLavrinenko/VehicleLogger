<template>
  <h1>Веб-панель</h1>
  <p class="lead">Вход, дашборд, страница фуры, роли. Раздел про создание компаний — в
    <router-link to="/docs/tenants">«Тенанты»</router-link>.</p>

  <h2>Аутентификация</h2>
  <p>JWT, токен живёт 24 часа. Хранится в localStorage. Передаётся в заголовке
    <code>Authorization: Bearer &lt;token&gt;</code> на каждом запросе.</p>

  <h3>Вход зависит от хоста</h3>
  <table class="docs-table">
    <thead><tr><th>Зашёл на</th><th>Кто пускается</th></tr></thead>
    <tbody>
      <tr><td><code>nonconf.ru/login</code></td>
          <td>Только super-admin (без <code>tenant_id</code> в БД)</td></tr>
      <tr><td><code>&lt;sub&gt;.nonconf.ru/login</code></td>
          <td>Только пользователи этого тенанта</td></tr>
      <tr><td><code>unknown.nonconf.ru/login</code></td>
          <td>Никто — поддомен не зарегистрирован, форма заблокирована</td></tr>
    </tbody>
  </table>

  <h3>Запрет cross-tenant</h3>
  <p>Если получить токен на <code>acme.nonconf.ru</code> и попробовать им запросить
    <code>delta.nonconf.ru/api/devices</code> — middleware вернёт <code>403 tenant_mismatch</code>.
    То же для super-admin токена на любом поддомене (<code>403 use_subdomain</code>).</p>

  <h2>Дашборд (главная)</h2>
  <p>Что показывается:</p>
  <ul>
    <li><b>4 KPI-карточки</b>: всего фур, онлайн, непрочитанные алерты, заправки за сегодня.
      Числа считаются <b>в скоупе текущего тенанта</b> (на apex — глобально).</li>
    <li><b>Список фур</b> карточками. Только фуры этого тенанта.</li>
    <li>Polling каждые 5 секунд.</li>
  </ul>

  <h2>Страница фуры</h2>
  <p>Адрес <code>/vehicles/{id}</code>. Доступна только если фура принадлежит твоему тенанту, иначе 404.</p>
  <ul>
    <li>Шапка: название, гос. номер, серийник устройства, последний ping, статус online/offline.</li>
    <li><b>6 графиков 2×3</b>: RPM, скорость, темп ОЖ, давление масла, топливо, напряжение. Polling 2 сек.</li>
    <li><b>Последние 15 пакетов</b> — таблица в скроллящемся блоке.</li>
    <li><b>Алерты</b> и <b>заправки</b> — справа в боковой панели.</li>
  </ul>

  <h2>Топбар</h2>
  <p>Слева у логотипа бейдж текущего контекста:</p>
  <ul>
    <li><span class="badge info">acme · ACME Logistics</span> — ты в админке тенанта.</li>
    <li><span class="badge info" style="background:rgba(188,140,255,.15);color:var(--purple);border-color:rgba(188,140,255,.3)">SUPER-ADMIN</span> — ты на apex.</li>
    <li><span class="badge critical">⚠ неизвестный поддомен</span> — поддомен в URL не существует, войти нельзя.</li>
  </ul>
  <p>Пункт <b>«Компании»</b> в шапке появляется только у super-admin на apex.</p>

  <h2>Роли</h2>
  <table class="docs-table">
    <thead><tr><th>Роль</th><th>Может</th><th>Не может</th></tr></thead>
    <tbody>
      <tr>
        <td><b>super-admin</b></td>
        <td>Создавать/удалять компании, видеть всё на apex</td>
        <td>Заходить на поддомены под своим токеном</td>
      </tr>
      <tr>
        <td><b>tenant admin</b></td>
        <td>Регистрировать устройства, выдавать коды привязки, управлять фурами своей компании</td>
        <td>Видеть другие компании; создавать новые</td>
      </tr>
      <tr>
        <td><b>tenant driver</b> (планируется)</td>
        <td>Видеть свою фуру, вносить заправки через TG-бот</td>
        <td>Управлять устройствами</td>
      </tr>
    </tbody>
  </table>

  <div class="callout callout--warn">
    Тестовая super-admin учётка <code>admin@vl.local</code> / <code>admin1234</code>
    лежит в seed'е — на проде <b>удалить и завести своих super-admin'ов</b>.
  </div>

  <nav class="next-prev">
    <router-link to="/docs/intro"><small>← Назад</small>Введение</router-link>
    <router-link class="next" to="/docs/tenants"><small>Дальше →</small>Компании</router-link>
  </nav>
</template>
