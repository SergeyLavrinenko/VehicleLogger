import { ref, computed } from 'vue'
import axios from 'axios'

/**
 * Контекст текущего хоста: apex (super-admin) или поддомен (тенант).
 * Подгружаем с бэка через /api/auth/context.
 */
const ctx = ref({
  loaded: false,
  host: typeof window !== 'undefined' ? window.location.hostname : '',
  isSuperAdminHost: false,
  tenant: null,                  // { id, subdomain, name } или null
  requestedSubdomain: null       // если поддомен в URL, но в БД не зарегистрирован
})

let loading = null

async function load() {
  if (loading) return loading
  loading = (async () => {
    try {
      const r = await axios.get('/api/auth/context', { timeout: 5000 })
      ctx.value = { loaded: true, ...r.data }
    } catch (e) {
      // если не отдаётся — считаем apex без тенанта
      ctx.value.loaded = true
    }
    return ctx.value
  })()
  return loading
}

export function useTenant() {
  if (!ctx.value.loaded) load()
  const isSuperAdminHost = computed(() => ctx.value.isSuperAdminHost === true)
  const tenant           = computed(() => ctx.value.tenant)
  const tenantName       = computed(() => ctx.value.tenant?.name)
  const subdomain        = computed(() => ctx.value.tenant?.subdomain)
  const unknownSubdomain = computed(() =>
    ctx.value.requestedSubdomain && !ctx.value.tenant)
  return { ctx, isSuperAdminHost, tenant, tenantName, subdomain, unknownSubdomain, reload: load }
}
