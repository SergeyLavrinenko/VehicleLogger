<script setup>
import { ref, computed } from 'vue'
import { apiCalls } from '../api'
import { usePolling } from '../composables/usePolling'
import { useModalBackdrop, copyToClipboard } from '../composables/useModalBackdrop'

const { data: tenants, refresh } = usePolling(apiCalls.listTenants, 10000)

const list = computed(() => tenants.value || [])

const showCreate = ref(false)
const subdomain  = ref('')
const name       = ref('')
const adminEmail = ref('')
const adminPassword = ref('')
const customPassword = ref(false)
const submitting = ref(false)
const created    = ref(null)
const error      = ref('')
const copied     = ref(null)
const busyId     = ref(null)

function fmt(ts) { return ts ? new Date(ts).toLocaleString('ru-RU') : '—' }

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const body = {
      subdomain: subdomain.value.trim().toLowerCase(),
      name:      name.value.trim(),
      adminEmail: adminEmail.value.trim().toLowerCase()
    }
    if (customPassword.value && adminPassword.value.trim())
      body.adminPassword = adminPassword.value.trim()
    created.value = await apiCalls.createTenant(body)
    refresh()
  } catch (e) {
    const code = e?.response?.status
    const err  = e?.response?.data?.error
    error.value =
      code === 409 ? (err === 'subdomain_exists' ? 'Этот поддомен уже занят' : 'Email админа уже используется') :
      err === 'invalid_subdomain' ? 'Неверный формат поддомена (a-z, 0-9, "-", 3-63 символа)' :
      err === 'invalid_admin_email' ? 'Неверный email' :
      err || e.message
  } finally {
    submitting.value = false
  }
}

function reset() {
  showCreate.value = false
  created.value = null
  subdomain.value = ''
  name.value = ''
  adminEmail.value = ''
  adminPassword.value = ''
  customPassword.value = false
  copied.value = null
}

async function copy(text, key) {
  if (await copyToClipboard(text)) {
    copied.value = key
    setTimeout(() => { if (copied.value === key) copied.value = null }, 2000)
  }
}

// Бэкдроп НЕ закрывает модалку пока показаны одноразовые креды.
const { onBackdropMouseDown, onBackdropMouseUp } =
  useModalBackdrop(reset, () => !!created.value)

async function del(t) {
  if (!confirm(`Удалить компанию "${t.name}" (${t.subdomain})? У неё ${t.userCount} пользователей и ${t.deviceCount} устройств. Удалить можно только пустые тенанты.`)) return
  busyId.value = t.id
  try {
    await apiCalls.deleteTenant(t.id)
    refresh()
  } catch (e) {
    alert(e?.response?.data?.error === 'has_users' ? 'У тенанта есть пользователи — сначала удалите их' :
          e?.response?.data?.error === 'has_devices' ? 'У тенанта есть устройства — сначала отвяжите их' :
          (e?.response?.data?.error || e.message))
  } finally { busyId.value = null }
}
</script>

<template>
  <div class="section-divider">
    <h2 class="section-divider__title">Компании / тенанты</h2>
    <span class="section-divider__count">{{ list.length || '0' }}</span>
    <div style="flex: 1" />
    <button @click="showCreate = true">+ Зарегистрировать компанию</button>
  </div>

  <p class="muted-inline" style="font-size:12px; margin: 0 0 12px;">
    Каждая компания получает поддомен <code>&lt;subdomain&gt;.nonconf.ru</code> и изолированный набор
    устройств, фур и пользователей. Wildcard TLS-cert уже выдан, новый поддомен начинает работать сразу.
  </p>

  <div v-if="!list.length" class="muted">Нет ни одной компании.</div>

  <table v-else class="tenants-table">
    <thead>
      <tr>
        <th>Поддомен</th>
        <th>Название</th>
        <th>Устройств</th>
        <th>Фур</th>
        <th>Юзеров</th>
        <th>Создан</th>
        <th>Действия</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="t in list" :key="t.id">
        <td>
          <a :href="t.url" target="_blank">{{ t.subdomain }}.nonconf.ru</a>
        </td>
        <td>{{ t.name }}</td>
        <td>{{ t.deviceCount }}</td>
        <td>{{ t.vehicleCount }}</td>
        <td>{{ t.userCount }}</td>
        <td class="muted-inline">{{ fmt(t.createdAt) }}</td>
        <td>
          <button class="danger" :disabled="busyId === t.id" @click="del(t)">Удалить</button>
        </td>
      </tr>
    </tbody>
  </table>

  <!-- Модалка создания -->
  <div v-if="showCreate"
       class="modal-backdrop"
       @mousedown="onBackdropMouseDown"
       @mouseup="onBackdropMouseUp">
    <div class="modal" @mousedown.stop @mouseup.stop>
      <header class="modal__head">
        <h3>{{ created ? 'Компания создана' : 'Новая компания' }}</h3>
        <button class="modal__x" @click="reset" title="Закрыть">×</button>
      </header>

      <div v-if="!created" class="modal__body">
        <p class="modal__hint">
          Создаст поддомен <code>&lt;subdomain&gt;.nonconf.ru</code> и первого admin-пользователя.
          Пароль показывается один раз.
        </p>

        <label>Поддомен (только a-z, 0-9, дефис)
          <input v-model="subdomain" placeholder="acme" autocomplete="off" autofocus />
        </label>

        <label>Название компании
          <input v-model="name" placeholder="ACME Logistics" autocomplete="off" />
        </label>

        <label>Email первого admin'а
          <input v-model="adminEmail" type="email" placeholder="admin@acme.com" autocomplete="off" />
        </label>

        <label class="checkbox">
          <input type="checkbox" v-model="customPassword" />
          <span>Свой пароль (иначе сгенерим)</span>
        </label>

        <label v-if="customPassword">Пароль
          <input v-model="adminPassword" type="text" placeholder="минимум 8 символов" autocomplete="off" />
        </label>

        <div v-if="error" class="modal__err">{{ error }}</div>

        <button class="modal__submit" :disabled="submitting || !subdomain.trim() || !name.trim() || !adminEmail.includes('@')" @click="submit">
          {{ submitting ? 'Создаём…' : 'Создать' }}
        </button>
      </div>

      <div v-else class="modal__body modal__success">
        <div class="badge online">Готово</div>

        <div class="callout callout--danger">
          <b>Запиши креды первого админа сейчас.</b> Пароль показывается ровно один раз.
        </div>

        <h3 class="modal__field-label">URL панели для этой компании</h3>
        <div class="copy-row">
          <a class="copy-row__value" :href="created.url" target="_blank">{{ created.url }}</a>
          <button @click="copy(created.url, 'url')">{{ copied === 'url' ? '✓' : 'Копировать' }}</button>
        </div>

        <h3 class="modal__field-label">Email</h3>
        <div class="copy-row">
          <code class="copy-row__value">{{ created.admin.email }}</code>
          <button @click="copy(created.admin.email, 'em')">{{ copied === 'em' ? '✓' : 'Копировать' }}</button>
        </div>

        <h3 class="modal__field-label">Пароль (один раз)</h3>
        <div class="copy-row">
          <code class="copy-row__value">{{ created.admin.password }}</code>
          <button @click="copy(created.admin.password, 'pw')">{{ copied === 'pw' ? '✓' : 'Копировать' }}</button>
        </div>

        <button @click="reset">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tenants-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden;
}
.tenants-table th {
  text-align: left; padding: 10px 14px;
  background: var(--surface-2);
  color: var(--text-muted); font-size: 11px;
  text-transform: uppercase; letter-spacing: .5px; font-weight: 600;
  border-bottom: 1px solid var(--border-soft);
}
.tenants-table td { padding: 10px 14px; border-bottom: 1px solid var(--border-soft); }
.tenants-table tr:last-child td { border-bottom: none; }
.tenants-table button { padding: 4px 10px; font-size: 12px; }
.tenants-table button.danger { color: var(--red); border-color: rgba(248,81,73,.3); }
.tenants-table a { font-family: 'SF Mono', Consolas, monospace; }
.muted-inline { color: var(--text-muted); font-size: 12px; }

.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; width: 480px; max-width: 92vw; max-height: 92vh; overflow: auto;
}
.modal__head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--border-soft);
}
.modal__head h3 { margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: .5px; color: var(--text-muted); }
.modal__x { background: transparent; border: 0; color: var(--text-muted); font-size: 22px; cursor: pointer; }
.modal__body { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.modal__hint { font-size: 12px; color: var(--text-muted); margin: 0; }
.modal label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--text-muted); }
.modal label.checkbox { flex-direction: row; align-items: center; gap: 8px; cursor: pointer; }
.modal input[type=checkbox] { width: auto; margin: 0; }
.modal input {
  background: var(--bg); border: 1px solid var(--border); color: var(--text);
  border-radius: 6px; padding: 8px 10px; font-size: 14px;
}
.modal input:focus { outline: none; border-color: var(--accent); }
.modal__submit {
  margin-top: 4px; padding: 9px 12px;
  background: var(--accent); color: #06121e; font-weight: 600;
}
.modal__submit:hover:not(:disabled) { background: #79b8ff; border-color: var(--accent); }
.modal__submit:disabled { opacity: .55; cursor: default; }
.modal__err {
  font-size: 13px; color: var(--red);
  background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3);
  padding: 6px 10px; border-radius: 6px;
}
.modal__field-label {
  margin: 12px 0 4px;
  font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
  color: var(--text-muted); font-weight: 600;
}
.callout { padding: 10px 14px; border-radius: 6px; font-size: 12px; border-left: 3px solid; }
.callout--danger { background: rgba(248,81,73,.06); border-color: var(--red); color: var(--text); }
.copy-row { display: flex; gap: 6px; align-items: stretch; }
.copy-row__value {
  flex: 1; word-break: break-all;
  background: var(--bg); border: 1px solid var(--border);
  padding: 8px 10px; border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  text-decoration: none; color: var(--text);
}
.copy-row button { padding: 0 12px; font-size: 12px; }
</style>
