<script setup>
import { ref } from 'vue'
import { apiCalls } from '../api'
import { useModalBackdrop } from '../composables/useModalBackdrop'

const emit = defineEmits(['close', 'created'])

const name        = ref('')
const licensePlate = ref('')
const submitting  = ref(false)
const error       = ref('')

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const v = await apiCalls.createVehicle({
      name: name.value.trim(),
      licensePlate: licensePlate.value.trim()
    })
    emit('created', v)
    emit('close')
  } catch (e) {
    const code = e?.response?.status
    const err  = e?.response?.data?.error
    error.value =
      err === 'name_length'   ? 'Название: 2–100 символов' :
      err === 'plate_length'  ? 'Госномер: 1–20 символов' :
      err === 'use_subdomain' ? 'Создавать фуры можно только из поддомена компании' :
      code === 403            ? 'Нет прав' :
      err || e.message
  } finally {
    submitting.value = false
  }
}

const { onBackdropMouseDown, onBackdropMouseUp } =
  useModalBackdrop(() => emit('close'))
</script>

<template>
  <div class="modal-backdrop"
       @mousedown="onBackdropMouseDown"
       @mouseup="onBackdropMouseUp">
    <div class="modal" @mousedown.stop @mouseup.stop>
      <header class="modal__head">
        <h3>Новая фура</h3>
        <button class="modal__x" @click="emit('close')">×</button>
      </header>

      <div class="modal__body">
        <label>Название
          <input v-model="name" placeholder="МАН TGS 26.480" autocomplete="off" autofocus />
        </label>

        <label>Госномер
          <input v-model="licensePlate" placeholder="А123БВ77" autocomplete="off" />
        </label>

        <div v-if="error" class="modal__err">{{ error }}</div>

        <button class="modal__submit"
                :disabled="submitting || name.trim().length < 2 || !licensePlate.trim()"
                @click="submit">
          {{ submitting ? 'Создаём…' : 'Создать' }}
        </button>
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
.modal label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--text-muted); }
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
</style>
