<script setup>
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { apiCalls } from './api'
import { usePolling } from './composables/usePolling'
import { useAuth } from './composables/useAuth'
import { useTenant } from './composables/useTenant'

const router = useRouter()
const route  = useRoute()
const { isAuthed, isAdmin, user, clearSession } = useAuth()
const { isSuperAdminHost, tenant, unknownSubdomain, reload: reloadTenant } = useTenant()

const isLoginPage = computed(() => route.name === 'login')

const { data: dashboard } = usePolling(
  () => isAuthed.value ? apiCalls.getDashboard().catch(() => null) : Promise.resolve(null),
  5000
)

const updatedTxt = computed(() => {
  if (!dashboard.value) return '—'
  return `${dashboard.value.devicesOnline}/${dashboard.value.vehiclesTotal} онлайн`
})

const ctxLabel = computed(() => {
  if (unknownSubdomain.value) return '⚠ неизвестный поддомен'
  if (isSuperAdminHost.value) return 'SUPER-ADMIN'
  return tenant.value ? tenant.value.name : ''
})

onMounted(() => reloadTenant())

function logout() {
  clearSession()
  router.replace({ name: 'login' })
}
</script>

<template>
  <router-view v-if="isLoginPage" />

  <div v-else class="app-shell">
    <header class="topbar">
      <div class="topbar__brand">
        <h1>VehicleLogger</h1>
        <span class="version">v0.3</span>
        <span v-if="ctxLabel" class="topbar__ctx" :class="{ 'topbar__ctx--super': isSuperAdminHost, 'topbar__ctx--warn': unknownSubdomain }">
          {{ ctxLabel }}
        </span>
      </div>
      <nav class="topbar__nav">
        <router-link to="/">Дашборд</router-link>
        <router-link v-if="isAdmin" to="/devices">Устройства</router-link>
        <router-link v-if="isAdmin && isSuperAdminHost" to="/tenants">Компании</router-link>
        <router-link to="/docs">Документация</router-link>
      </nav>
      <div class="topbar__spacer" />
      <div class="topbar__live">{{ updatedTxt }}</div>
      <div class="topbar__user" v-if="user">
        <span class="topbar__user-name">{{ user.name }}</span>
        <button class="topbar__logout" @click="logout" title="Выйти">Выйти</button>
      </div>
      <div class="topbar__user" v-else>
        <router-link to="/login" class="topbar__login">Войти</router-link>
      </div>
    </header>

    <div v-if="unknownSubdomain" class="bad-host-banner">
      Этот поддомен (<code>{{ $route.fullPath }}</code>) не зарегистрирован.
      Нужно создать компанию через <a href="https://nonconf.ru/tenants">панель super-admin</a>.
    </div>

    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.topbar__user { display: flex; align-items: center; gap: 10px; padding-left: 16px; border-left: 1px solid var(--border); }
.topbar__user-name { font-size: 12px; color: var(--text-muted); }
.topbar__logout { padding: 4px 10px; font-size: 12px; }
.topbar__login {
  padding: 4px 12px; font-size: 12px;
  background: var(--accent); color: #06121e;
  border-radius: 6px; font-weight: 600;
}
.topbar__login:hover { text-decoration: none; background: #79b8ff; }
.topbar__ctx {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: rgba(88,166,255,.12); color: var(--accent);
  border: 1px solid rgba(88,166,255,.3); font-weight: 500;
}
.topbar__ctx--super {
  background: rgba(188,140,255,.15); color: var(--purple);
  border-color: rgba(188,140,255,.3);
}
.topbar__ctx--warn {
  background: rgba(248,81,73,.12); color: var(--red);
  border-color: rgba(248,81,73,.3);
}
.bad-host-banner {
  background: rgba(248,81,73,.08); color: var(--text);
  border-bottom: 1px solid rgba(248,81,73,.3);
  padding: 10px 24px; font-size: 13px;
}
.bad-host-banner code {
  background: var(--bg); padding: 1px 6px; border-radius: 3px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
}
</style>
