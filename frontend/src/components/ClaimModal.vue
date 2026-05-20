<script setup>
import { ref, computed } from 'vue'
import { apiCalls } from '../api'
import QrScanner from './QrScanner.vue'
import { useModalBackdrop } from '../composables/useModalBackdrop'

const props = defineProps({ vehicles: { type: Array, default: () => [] } })
const emit = defineEmits(['close', 'claimed'])

const mode      = ref('manual') // 'manual' | 'qr'
const serial    = ref('')
const fragment  = ref('')
const vehicleId = ref('')
const qrError   = ref('')
const submitting = ref(false)
const submitErr  = ref('')
const result     = ref(null)

function onDecode(text) {
  // Ожидаем либо https://.../claim?sn=VL-...&ds=XXXX, либо просто "VL-...|XXXX"
  try {
    const u = new URL(text)
    const sn = u.searchParams.get('sn')
    const ds = u.searchParams.get('ds')
    if (sn && ds) { serial.value = sn; fragment.value = ds; mode.value = 'manual'; return }
  } catch {}
  if (text.includes('|')) {
    const [sn, ds] = text.split('|', 2)
    serial.value = sn.trim(); fragment.value = ds.trim(); mode.value = 'manual'; return
  }
  qrError.value = 'Это не QR от VehicleLogger'
}

async function submit() {
  submitErr.value = ''
  submitting.value = true
  try {
    const body = {
      serialNumber: serial.value.trim(),
      deviceSecretFragment: fragment.value.trim()
    }
    if (vehicleId.value) body.vehicleId = Number(vehicleId.value)
    result.value = await apiCalls.claimDevice(body)
    emit('claimed', result.value)
  } catch (e) {
    const code = e?.response?.status
    const err  = e?.response?.data?.error
    submitErr.value =
      code === 400 ? 'Фрагмент секрета не совпадает' :
      code === 404 ? 'Серийный номер не найден' :
      code === 409 ? `Устройство уже привязано (${e.response.data.status})` :
      err || e.message
  } finally {
    submitting.value = false
  }
}

// Бэкдроп блокируется когда показан apiKey
const { onBackdropMouseDown, onBackdropMouseUp } =
  useModalBackdrop(() => emit('close'), () => !!result.value)
</script>

<template>
  <div class="modal-backdrop"
       @mousedown="onBackdropMouseDown"
       @mouseup="onBackdropMouseUp">
    <div class="modal" @mousedown.stop @mouseup.stop>
      <header class="modal__head">
        <h3>Привязать устройство</h3>
        <button class="modal__x" @click="emit('close')">×</button>
      </header>

      <div v-if="!result" class="modal__body">
        <div class="modal__tabs">
          <button :class="{ active: mode === 'manual' }" @click="mode = 'manual'">Ввод вручную</button>
          <button :class="{ active: mode === 'qr' }" @click="mode = 'qr'; qrError = ''">Сканировать QR</button>
        </div>

        <template v-if="mode === 'qr'">
          <QrScanner @decode="onDecode" @error="qrError = $event" />
          <div v-if="qrError" class="modal__err">{{ qrError }}</div>
        </template>

        <template v-else>
          <label>Серийный номер
            <input v-model="serial" placeholder="VL-PROV-001" autocomplete="off" />
          </label>

          <label>Фрагмент секрета (с QR)
            <input v-model="fragment" placeholder="a1b2c3d4" autocomplete="off" />
          </label>

          <label>Привязать к фуре (опционально)
            <select v-model="vehicleId">
              <option value="">— не назначать —</option>
              <option v-for="v in vehicles" :key="v.id" :value="v.id">
                {{ v.name }} ({{ v.licensePlate }})
              </option>
            </select>
          </label>

          <div v-if="submitErr" class="modal__err">{{ submitErr }}</div>

          <button class="modal__submit" :disabled="submitting || !serial || !fragment" @click="submit">
            {{ submitting ? 'Привязываем…' : 'Привязать' }}
          </button>
        </template>
      </div>

      <div v-else class="modal__body modal__success">
        <div class="badge online">Готово</div>
        <p>Устройство <b>{{ result.serialNumber }}</b> привязано (id {{ result.deviceId }}).</p>
        <p style="font-size: 12px; color: var(--text-muted);">
          API-ключ устройства будет выдан ESP32 при следующем <code>/provision</code>.
          Сейчас он также скопирован в буфер для теста:
        </p>
        <code class="apikey">{{ result.apiKey }}</code>
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
  width: 420px; max-width: 92vw;
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
.modal__tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-soft); padding-bottom: 8px; }
.modal__tabs button {
  background: transparent; border: 0; color: var(--text-muted);
  padding: 6px 12px; border-radius: 6px; font-size: 13px;
}
.modal__tabs button.active { background: var(--surface-2); color: var(--text); }
.modal label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--text-muted); }
.modal input, .modal select {
  background: var(--bg); border: 1px solid var(--border); color: var(--text);
  border-radius: 6px; padding: 8px 10px; font-size: 14px;
  font-family: inherit;
}
.modal input:focus, .modal select:focus { outline: none; border-color: var(--accent); }
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
.modal__success { align-items: flex-start; }
.modal__success p { margin: 0; font-size: 14px; }
.apikey {
  display: block; word-break: break-all;
  background: var(--bg); border: 1px solid var(--border);
  padding: 8px 10px; border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
}
</style>
