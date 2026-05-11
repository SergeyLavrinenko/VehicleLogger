<script setup>
import { ref } from 'vue'
import { apiCalls } from '../api'
import { useModalBackdrop } from '../composables/useModalBackdrop'
import AddVehicleModal from './AddVehicleModal.vue'

const props = defineProps({
  device:   { type: Object, required: true },
  vehicles: { type: Array,  default: () => [] }
})
const emit = defineEmits(['close', 'assigned', 'vehicleCreated'])

const vehicleId  = ref(props.device.vehicleId ?? '')
const submitting = ref(false)
const error      = ref('')
const showAdd    = ref(false)

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const id = vehicleId.value === '' ? null : Number(vehicleId.value)
    await apiCalls.assignVehicle(props.device.id, id)
    emit('assigned')
    emit('close')
  } catch (e) {
    const code = e?.response?.status
    const err  = e?.response?.data?.error
    error.value =
      code === 404 ? 'Фура не найдена' :
      code === 409 ? 'На эту фуру уже назначено другое устройство' :
      err || e.message
  } finally { submitting.value = false }
}

function onCreated(v) {
  emit('vehicleCreated', v)
  vehicleId.value = v.id
  showAdd.value = false
}

const { onBackdropMouseDown, onBackdropMouseUp } =
  useModalBackdrop(() => emit('close'), () => showAdd.value)
</script>

<template>
  <div class="modal-backdrop"
       @mousedown="onBackdropMouseDown"
       @mouseup="onBackdropMouseUp">
    <div class="modal" @mousedown.stop @mouseup.stop>
      <header class="modal__head">
        <h3>Привязать к фуре</h3>
        <button class="modal__x" @click="emit('close')">×</button>
      </header>

      <div class="modal__body">
        <p class="modal__hint">
          Устройство <code>{{ device.serialNumber }}</code>
        </p>

        <template v-if="vehicles.length">
          <label>Фура
            <select v-model="vehicleId">
              <option value="">— снять привязку —</option>
              <option v-for="v in vehicles" :key="v.id" :value="v.id">
                {{ v.name }} ({{ v.licensePlate }})
              </option>
            </select>
          </label>

          <button class="link-btn" @click="showAdd = true">+ Создать новую фуру</button>
        </template>

        <template v-else>
          <div class="callout">
            В компании пока нет фур. Создайте первую — устройство сразу можно будет привязать.
          </div>
          <button class="modal__submit" @click="showAdd = true">+ Создать фуру</button>
        </template>

        <div v-if="error" class="modal__err">{{ error }}</div>

        <button v-if="vehicles.length"
                class="modal__submit"
                :disabled="submitting"
                @click="submit">
          {{ submitting ? 'Сохраняем…' : 'Сохранить' }}
        </button>
      </div>
    </div>
  </div>

  <AddVehicleModal v-if="showAdd"
                   @close="showAdd = false"
                   @created="onCreated" />
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
.modal__hint { font-size: 13px; color: var(--text-muted); margin: 0; }
.modal__hint code {
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  background: var(--bg); padding: 1px 6px; border-radius: 3px;
}
.modal label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--text-muted); }
.modal select {
  background: var(--bg); border: 1px solid var(--border); color: var(--text);
  border-radius: 6px; padding: 8px 10px; font-size: 14px;
  font-family: inherit;
}
.modal select:focus { outline: none; border-color: var(--accent); }
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
.link-btn {
  background: transparent; border: 0; color: var(--accent);
  padding: 0; font-size: 12px; align-self: flex-start; cursor: pointer;
}
.link-btn:hover { background: transparent; color: #79b8ff; }
.callout {
  background: rgba(56,139,253,.08);
  border: 1px solid rgba(56,139,253,.25);
  border-left: 3px solid var(--accent);
  padding: 10px 12px; border-radius: 6px;
  font-size: 13px; color: var(--text);
}
</style>
