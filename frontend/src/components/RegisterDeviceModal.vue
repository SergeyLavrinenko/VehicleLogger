<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { useModalBackdrop, copyToClipboard } from '../composables/useModalBackdrop'

const emit = defineEmits(['close', 'created'])

const serial    = ref('')
const useCustom = ref(false)
const secret    = ref('')
const submitting = ref(false)
const error     = ref('')
const result    = ref(null)
const copied    = ref(false)

function genHex(n) {
  const arr = new Uint8Array(n)
  crypto.getRandomValues(arr)
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('')
}

function generateSecret() {
  secret.value = genHex(32)
}

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const body = { serialNumber: serial.value.trim() }
    if (useCustom.value && secret.value.trim()) {
      body.deviceSecret = secret.value.trim().toLowerCase()
    }
    const r = await api.post('/devices', body)
    result.value = r.data
    emit('created', r.data)
  } catch (e) {
    const code = e?.response?.status
    const err  = e?.response?.data?.error
    error.value =
      code === 409 ? 'Устройство с таким серийником уже существует' :
      err === 'serial_length' ? 'Серийник должен быть 3–64 символа' :
      err === 'secret_must_be_64_hex' ? 'Секрет должен быть 64 hex-символа (0–9, a–f)' :
      err || e.message
  } finally {
    submitting.value = false
  }
}

async function copySecret() {
  if (!result.value?.deviceSecret) return
  if (await copyToClipboard(result.value.deviceSecret)) {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  }
}

// Бэкдроп блокируется пока показан plaintext секрет
const { onBackdropMouseDown, onBackdropMouseUp } =
  useModalBackdrop(() => emit('close'), () => !!result.value)
</script>

<template>
  <div class="modal-backdrop"
       @mousedown="onBackdropMouseDown"
       @mouseup="onBackdropMouseUp">
    <div class="modal" @mousedown.stop @mouseup.stop>
      <header class="modal__head">
        <h3>Зарегистрировать устройство</h3>
        <button class="modal__x" @click="emit('close')">×</button>
      </header>

      <div v-if="!result" class="modal__body">
        <p class="modal__hint">
          Создаёт запись в БД со статусом <code>manufactured</code>. После этого ESP32
          с этим серийником и секретом сможет начать <code>/provision</code>.
        </p>

        <label>Серийный номер
          <input v-model="serial" placeholder="VL-A3F82B01" autocomplete="off" autofocus />
        </label>

        <label class="checkbox">
          <input type="checkbox" v-model="useCustom" />
          <span>Свой секрет (иначе сгенерится случайный)</span>
        </label>

        <template v-if="useCustom">
          <label>Секрет (64 hex)
            <div style="display: flex; gap: 6px;">
              <input v-model="secret" placeholder="a1b2c3d4..." autocomplete="off" style="flex: 1; font-family: 'SF Mono', Consolas, monospace; font-size: 12px;" />
              <button type="button" @click="generateSecret">⟳</button>
            </div>
          </label>
        </template>

        <div v-if="error" class="modal__err">{{ error }}</div>

        <button class="modal__submit" :disabled="submitting || !serial.trim() || (useCustom && secret.trim().length !== 64)" @click="submit">
          {{ submitting ? 'Создаём…' : 'Создать' }}
        </button>
      </div>

      <div v-else class="modal__body modal__success">
        <div class="badge online">Создано</div>
        <p style="margin: 0;">Устройство <b>{{ result.serialNumber }}</b> зарегистрировано (id {{ result.id }}).</p>

        <div class="callout callout--danger" style="margin: 6px 0 0;">
          <b>Скопируй секрет сейчас.</b> Он показывается ровно один раз —
          в БД хранится только хеш. Если потеряешь — придётся удалить устройство и завести заново.
        </div>

        <h3 class="modal__field-label">Полный секрет (зашить в NVS factory/secret)</h3>
        <div class="copy-row">
          <code class="copy-row__value">{{ result.deviceSecret }}</code>
          <button @click="copySecret">{{ copied ? '✓' : 'Копировать' }}</button>
        </div>

        <h3 class="modal__field-label">Фрагмент (на QR-наклейке)</h3>
        <code class="apikey">{{ result.secretFragment }}</code>

        <h3 class="modal__field-label">Статус</h3>
        <span class="badge offline">{{ result.status }}</span>

        <p style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
          Дальше: запусти ESP32 с этим серийником и секретом. Оно будет поллить
          <code>/provision</code>. Чтобы выпустить ему API-ключ — нажми <b>+ Привязать</b>
          и введи серийник + первые 8 символов секрета.
        </p>

        <button @click="emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 480px; max-width: 92vw;
  max-height: 92vh; overflow: auto;
}
.modal__head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-soft);
}
.modal__head h3 { margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: .5px; color: var(--text-muted); }
.modal__x { background: transparent; border: 0; color: var(--text-muted); font-size: 22px; cursor: pointer; }
.modal__x:hover { color: var(--text); background: transparent; }
.modal__body { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.modal__hint { font-size: 12px; color: var(--text-muted); margin: 0; }
.modal label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--text-muted); }
.modal label.checkbox { flex-direction: row; align-items: center; gap: 8px; cursor: pointer; }
.modal input[type=checkbox] { width: auto; margin: 0; }
.modal input {
  background: var(--bg); border: 1px solid var(--border); color: var(--text);
  border-radius: 6px; padding: 8px 10px; font-size: 14px;
  font-family: inherit;
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
.modal__success { align-items: stretch; }
.modal__success p { font-size: 14px; }
.modal__field-label {
  margin: 12px 0 4px;
  font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
  color: var(--text-muted); font-weight: 600;
}
.callout { padding: 10px 14px; border-radius: 6px; font-size: 12px; border-left: 3px solid; }
.callout--danger { background: rgba(248,81,73,.06); border-color: var(--red); color: var(--text); }
.apikey {
  display: block; word-break: break-all;
  background: var(--bg); border: 1px solid var(--border);
  padding: 8px 10px; border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
}
.copy-row {
  display: flex; gap: 6px; align-items: stretch;
}
.copy-row__value {
  flex: 1; word-break: break-all;
  background: var(--bg); border: 1px solid var(--border);
  padding: 8px 10px; border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 11px;
}
.copy-row button { padding: 0 12px; font-size: 12px; }
</style>
