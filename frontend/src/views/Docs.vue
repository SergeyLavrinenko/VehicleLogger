<script setup>
const sections = [
  { to: '/docs/intro',      title: 'Что это и быстрый старт', desc: 'Обзор системы за 5 минут' },
  { to: '/docs/web',        title: 'Веб-панель',              desc: 'Логин, дашборд, страница фуры' },
  { to: '/docs/tenants',    title: 'Компании / тенанты',      desc: 'Мультитенантность, поддомены, super-admin' },
  { to: '/docs/devices',    title: 'Управление устройствами', desc: 'Регистрация, привязка, ротация' },
  { to: '/docs/firmware',   title: 'Прошивка устройства',     desc: 'Что должна делать ESP32, по шагам' },
  { to: '/docs/api',        title: 'API эндпоинты',           desc: 'Полный справочник запросов' },
  { to: '/docs/simulator',  title: 'Симулятор устройства',    desc: 'Как тестировать без железа' },
  { to: '/docs/support',    title: 'Что ещё не готово',       desc: 'Roadmap и решение проблем' }
]
</script>

<template>
  <div class="docs-layout">
    <aside class="docs-toc">
      <div class="docs-toc__head">Документация</div>
      <router-link v-for="s in sections" :key="s.to" :to="s.to" class="docs-toc__link">
        <span class="docs-toc__title">{{ s.title }}</span>
        <span class="docs-toc__desc">{{ s.desc }}</span>
      </router-link>
    </aside>

    <article class="docs-main">
      <router-view />
    </article>
  </div>
</template>

<style>
.docs-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 32px;
  align-items: flex-start;
}
@media (max-width: 880px) {
  .docs-layout { grid-template-columns: 1fr; }
  .docs-toc { position: static !important; max-height: none !important; }
}

.docs-toc {
  position: sticky;
  top: 76px;
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 0;
}
.docs-toc__head {
  padding: 0 16px 10px;
  font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
  color: var(--text-muted); font-weight: 600;
  border-bottom: 1px solid var(--border-soft);
}
.docs-toc__link {
  display: flex; flex-direction: column; gap: 2px;
  padding: 10px 16px;
  color: var(--text-muted);
  border-left: 2px solid transparent;
}
.docs-toc__link:hover { background: rgba(255,255,255,.03); color: var(--text); text-decoration: none; }
.docs-toc__link.router-link-active {
  color: var(--text);
  background: rgba(88,166,255,.08);
  border-left-color: var(--accent);
}
.docs-toc__title { font-size: 13px; font-weight: 500; color: var(--text); }
.docs-toc__desc  { font-size: 11px; color: var(--text-muted); }
.docs-toc__link.router-link-active .docs-toc__title { color: var(--accent); }

/* Общие стили docs-страниц */
.docs-main { max-width: 820px; padding-bottom: 60px; }
.docs-main h1 { margin: 0 0 4px; font-size: 26px; font-weight: 600; }
.docs-main .lead {
  color: var(--text-muted); font-size: 14px;
  margin: 0 0 24px; padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.docs-main h2 {
  margin: 28px 0 12px; font-size: 18px; font-weight: 600;
  padding-top: 20px; border-top: 1px solid var(--border-soft);
}
.docs-main h2:first-of-type { padding-top: 0; border-top: none; margin-top: 8px; }
.docs-main h3 {
  margin: 18px 0 8px; font-size: 13px; font-weight: 600;
  color: var(--text-muted); text-transform: uppercase; letter-spacing: .5px;
}
.docs-main p, .docs-main li { font-size: 14px; line-height: 1.65; }
.docs-main ul, .docs-main ol { padding-left: 22px; margin: 8px 0; }
.docs-main li { margin: 4px 0; }
.docs-main code {
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  background: var(--bg); padding: 1px 6px; border-radius: 3px;
  border: 1px solid var(--border-soft);
}
.docs-main pre {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px; line-height: 1.5;
  overflow-x: auto;
  margin: 12px 0;
  white-space: pre;
}

.steps { counter-reset: step; list-style: none; padding-left: 0; }
.steps li {
  counter-increment: step;
  position: relative;
  padding: 6px 0 6px 36px;
}
.steps li::before {
  content: counter(step);
  position: absolute; left: 0; top: 6px;
  width: 24px; height: 24px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600;
  color: var(--accent);
}

.docs-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }
.docs-table th, .docs-table td {
  text-align: left; padding: 8px 12px;
  border-bottom: 1px solid var(--border-soft);
}
.docs-table th {
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
  font-weight: 600;
}
.docs-table tr:last-child td { border-bottom: none; }

.api-table .m {
  display: inline-block;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 11px; font-weight: 700;
  padding: 2px 6px; border-radius: 3px;
  min-width: 42px; text-align: center;
}
.api-table .m.get  { background: rgba(63,185,80,.15);  color: var(--green); }
.api-table .m.post { background: rgba(88,166,255,.15); color: var(--accent); }
.api-table .m.put  { background: rgba(210,153,34,.15); color: var(--yellow); }
.api-table .m.delete { background: rgba(248,81,73,.15); color: var(--red); }

.callout {
  padding: 10px 14px; border-radius: 6px;
  font-size: 13px; margin: 12px 0;
  border-left: 3px solid;
}
.callout--info { background: rgba(88,166,255,.06);  border-color: var(--accent); color: var(--text); }
.callout--warn { background: rgba(210,153,34,.06);  border-color: var(--yellow); color: var(--text); }
.callout--danger { background: rgba(248,81,73,.06); border-color: var(--red); color: var(--text); }

.next-prev {
  display: flex; justify-content: space-between; gap: 12px;
  margin-top: 40px; padding-top: 16px;
  border-top: 1px solid var(--border-soft);
}
.next-prev a {
  flex: 1; max-width: 50%;
  padding: 10px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 13px;
}
.next-prev a:hover { border-color: var(--accent); color: var(--text); text-decoration: none; }
.next-prev a small { display: block; font-size: 11px; opacity: .7; }
.next-prev a.next { text-align: right; margin-left: auto; }
</style>
