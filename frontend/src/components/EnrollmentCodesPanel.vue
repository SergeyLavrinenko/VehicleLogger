<script setup>
import { ref, computed } from 'vue'
import { apiCalls } from '../api'
import { usePolling } from '../composables/usePolling'
import { useModalBackdrop, copyToClipboard } from '../composables/useModalBackdrop'

const { data: codes, refresh } = usePolling(apiCalls.listEnrollmentCodes, 10000)

const list = computed(() => codes.value || [])

const showCreate = ref(false)
const label      = ref('')
const submitting = ref(false)
const created    = ref(null)
const copied     = ref(false)
const error      = ref('')
const busyId     = ref(null)

function fmt(ts) { return ts ? new Date(ts).toLocaleString('ru-RU') : '—' }
function timeLeft(ts) {
  if (!ts) return ''
  const ms = new Date(ts).getTime() - Date.now()
  if (ms <= 0) return 'истёк'
  const m = Math.floor(ms / 60000)
  if (m < 60) return `${m} мин`
  return `${Math.floor(m / 60)} ч`
}

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    created.value = await apiCalls.createEnrollmentCode({ label: label.value.trim() || null })
    label.value = ''
    refresh()
  } catch (e) {
    error.value = e?.response?.data?.error || e.message
  } finally {
    submitting.value = false
  }
}

async function copy() {
  if (!created.value?.code) return
  if (await copyToClipboard(created.value.code)) {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  }
}

function closeCreated() {
  created.value = null
  showCreate.value = false
  copied.value = false
}

const { onBackdropMouseDown, onBackdropMouseUp } =
  useModalBackdrop(closeCreated, () => !!created.value)

async function revoke(c) {
  if (!confirm(`Отозвать код ${c.prefix}…? После этого его нельзя использовать для привязки.`)) return
  busyId.value = c.id
  try {
    await apiCalls.revokeEnrollmentCode(c.id)
    refresh()
  } catch (e) {
    alert(e?.response?.data?.error || e.message)
  } finally { busyId.value = null }
}
</script>

<template>
  <div class="section-divider">
    <h2 class="section-divider__title">Коды привязки</h2>
    <span class="section-divider__count">{{ list.length || '0' }}</span>
    <div style="flex:1" />
    <button @click="showCreate = true">+ Сгенерировать код</button>
  </div>

  <p class="muted-inline" style="font-size:12px; margin: 0 0 12px;">
    6-значный код, который установщик вводит в captive-portal ESP32 при первичной настройке.
    Действует 30 минут, single-use.
  </p>

  <div v-if="!list.length" class="muted">Активных кодов нет.</div>

  <table v-else class="codes-table">
    <thead>
      <tr>
        <th>Префикс</th>
        <th>Метка</th>
        <th>Создан</th>
        <th>Истекает</th>
        <th>Действия</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="c in list" :key="c.id">
        <td><code>{{ c.prefix }}…</code></td>
        <td>{{ c.label || '—' }}</td>
        <td class="muted-inline">{{ fmt(c.createdAt) }}</td>
        <td>
          <span v-if="c.usedAt" class="badge offline">использован</span>
          <span v-else-if="c.isExpired" class="badge offline">истёк</span>
          <span v-else class="badge warning">{{ timeLeft(c.expiresAt) }}</span>
        </td>
        <td>
          <button v-if="!c.usedAt && !c.isExpired" :disabled="busyId === c.id" class="danger" @click="revoke(c)">Отозвать</button>
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
        <h3>Новый код привязки</h3>
        <button class="modal__x" @click="showCreate = false; created = null">×</button>
      </header>

      <div v-if="!created" class="modal__body">
        <p class="modal__hint">
          Передай этот код установщику. Он введёт его в captive-portal ESP32 вместе с WiFi-кредами.
        </p>

        <label>Метка (опционально)
          <input v-model="label" placeholder="Фура МАН А123" autocomplete="off" autofocus />
        </label>

        <div v-if="error" class="modal__err">{{ error }}</div>

        <button class="modal__submit" :disabled="submitting" @click="submit">
          {{ submitting ? 'Создаём…' : 'Создать код' }}
        </button>
      </div>

      <div v-else class="modal__body modal__success">
        <div class="badge online">Готово</div>

        <div class="callout callout--danger">
          <b>Запиши код сейчас.</b> Он показывается ровно один раз.
        </div>

        <div class="big-code">{{ created.code }}</div>

        <button class="modal__submit" @click="copy">
          {{ copied ? '✓ Скопировано' : 'Скопировать в буфер' }}
        </button>

        <p style="font-size: 12px; color: var(--text-muted); margin: 8px 0 0;">
          Действует 30 минут до {{ fmt(created.expiresAt) }}.
          После использования или истечения — пропадёт из списка.
        </p>

        <button @click="closeCreated">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.codes-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  font-size: 13px;
  margin-top: 4px;
}
.codes-table th {
  text-align: left; padding: 10px 14px;
  background: var(--surface-2);
  color: var(--text-muted); font-size: 11px;
  text-transform: uppercase; letter-spacing: .5px; font-weight: 600;
  border-bottom: 1px solid var(--border-soft);
}
.codes-table td { padding: 10px 14px; border-bottom: 1px solid var(--border-soft); }
.codes-table tr:last-child td { border-bottom: none; }
.codes-table code {
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  background: var(--bg); padding: 1px 6px; border-radius: 3px;
}
.muted-inline { color: var(--text-muted); font-size: 12px; }
.codes-table button { padding: 4px 10px; font-size: 12px; }
.codes-table button.danger { color: var(--red); border-color: rgba(248,81,73,.3); }
.codes-table button.danger:hover { border-color: var(--red); }

.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; width: 420px; max-width: 92vw;
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
.modal__err {
  font-size: 13px; color: var(--red);
  background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3);
  padding: 6px 10px; border-radius: 6px;
}
.modal__success { align-items: stretch; }
.callout { padding: 10px 14px; border-radius: 6px; font-size: 12px; border-left: 3px solid; }
.callout--danger { background: rgba(248,81,73,.06); border-color: var(--red); color: var(--text); }
.big-code {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 38px; font-weight: 600;
  text-align: center; letter-spacing: 8px;
  background: var(--bg); border: 1px solid var(--border);
  padding: 18px 14px; border-radius: 10px;
  color: var(--accent);
  user-select: all;
}
</style>
