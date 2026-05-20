<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { apiCalls } from '../api'
import { useAuth } from '../composables/useAuth'
import { useTenant } from '../composables/useTenant'

const router = useRouter()
const route = useRoute()
const { setSession } = useAuth()
const { isSuperAdminHost, tenant, unknownSubdomain, reload: reloadTenant } = useTenant()

const email    = ref('')
const password = ref('')
const error    = ref('')
const loading  = ref(false)

const heading = computed(() => {
  if (unknownSubdomain.value) return 'Неизвестный поддомен'
  if (isSuperAdminHost.value) return 'Super-admin'
  return tenant.value?.name || 'Вход'
})
const hint = computed(() => {
  if (isSuperAdminHost.value) return 'admin@vl.local / admin1234'
  if (tenant.value) return `Поддомен: ${tenant.value.subdomain}.nonconf.ru`
  return ''
})

onMounted(async () => {
  await reloadTenant()
  // Дефолтное значение email для super-admin
  if (isSuperAdminHost.value && !email.value) email.value = 'admin@vl.local'
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const r = await apiCalls.login(email.value.trim(), password.value)
    setSession(r)
    const next = route.query.next || '/'
    router.replace(next)
  } catch (e) {
    error.value = e?.response?.status === 401
      ? 'Неверный email или пароль'
      : (e.message || 'Ошибка входа')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-shell">
    <form class="login-card" @submit.prevent="submit">
      <h1>VehicleLogger</h1>
      <div class="login-card__sub">{{ heading }}</div>
      <div v-if="unknownSubdomain" class="login-card__err" style="margin-top: 0;">
        Этот поддомен не зарегистрирован в системе. Войти невозможно.
      </div>

      <label>Email
        <input v-model="email" type="email" autocomplete="username" required />
      </label>

      <label>Пароль
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>

      <div v-if="error" class="login-card__err">{{ error }}</div>

      <button type="submit" :disabled="loading || unknownSubdomain">
        {{ loading ? 'Входим…' : 'Войти' }}
      </button>

      <div class="login-card__hint" v-if="hint">{{ hint }}</div>
    </form>
  </div>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg);
}
.login-card {
  width: 360px; max-width: 92vw;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 28px 24px;
  display: flex; flex-direction: column; gap: 14px;
}
.login-card h1 { margin: 0; font-size: 20px; font-weight: 600; }
.login-card__sub { color: var(--text-muted); font-size: 13px; margin-bottom: 8px; }
.login-card label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--text-muted); }
.login-card input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 14px;
}
.login-card input:focus { outline: none; border-color: var(--accent); }
.login-card button {
  margin-top: 6px;
  padding: 9px 12px;
  background: var(--accent);
  color: #06121e;
  font-weight: 600;
}
.login-card button:hover:not(:disabled) { background: #79b8ff; border-color: var(--accent); }
.login-card button:disabled { opacity: .6; cursor: default; }
.login-card__err {
  font-size: 13px;
  color: var(--red);
  background: rgba(248,81,73,.1);
  border: 1px solid rgba(248,81,73,.3);
  padding: 6px 10px;
  border-radius: 6px;
}
.login-card__hint {
  font-size: 11px; color: var(--text-muted); text-align: center;
  border-top: 1px solid var(--border-soft); padding-top: 10px;
}
.login-card__hint code {
  background: var(--bg); padding: 1px 5px; border-radius: 3px;
  font-family: 'SF Mono', Consolas, monospace;
}
</style>
