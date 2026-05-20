<script setup>
import { ref, computed } from 'vue'
import { apiCalls } from '../api'
import { usePolling } from '../composables/usePolling'
import ClaimModal from '../components/ClaimModal.vue'
import RegisterDeviceModal from '../components/RegisterDeviceModal.vue'
import EnrollmentCodesPanel from '../components/EnrollmentCodesPanel.vue'
import AddVehicleModal from '../components/AddVehicleModal.vue'
import AssignVehicleModal from '../components/AssignVehicleModal.vue'

const { data: devices, refresh: refreshDevices } = usePolling(apiCalls.getDevices, 5000)
const { data: vehicles, refresh: refreshVehicles } = usePolling(apiCalls.getVehicles, 30000)

const list = computed(() => devices.value || [])
const showClaim = ref(false)
const showRegister = ref(false)
const showAddVehicle = ref(false)
const assignTarget = ref(null)
const busyId = ref(null)
const flash = ref(null)

function fmt(ts) { return ts ? new Date(ts).toLocaleString('ru-RU') : '—' }

async function unclaim(d) {
  if (!confirm(`Отвязать устройство ${d.serialNumber}? Оно перестанет слать данные.`)) return
  busyId.value = d.id
  try {
    await apiCalls.unclaimDevice(d.id)
    flash.value = { type: 'ok', text: `${d.serialNumber}: отвязано` }
    refreshDevices()
  } catch (e) {
    flash.value = { type: 'err', text: e?.response?.data?.error || e.message }
  } finally { busyId.value = null }
}
async function rotate(d) {
  if (!confirm(`Сгенерировать новый API-ключ для ${d.serialNumber}? Старый перестанет работать.`)) return
  busyId.value = d.id
  try {
    await apiCalls.rotateKey(d.id)
    flash.value = { type: 'ok', text: `${d.serialNumber}: ключ ротирован, устройство получит новый при следующем /provision` }
    refreshDevices()
  } catch (e) {
    flash.value = { type: 'err', text: e?.response?.data?.error || e.message }
  } finally { busyId.value = null }
}
function assign(d) {
  assignTarget.value = d
}
function onAssigned() {
  flash.value = { type: 'ok', text: `${assignTarget.value.serialNumber}: назначено` }
  refreshDevices()
}

function onClaimed(_) {
  refreshDevices()
}
</script>

<template>
  <div class="section-divider">
    <h2 class="section-divider__title">Устройства</h2>
    <span class="section-divider__count">{{ list.length || '—' }}</span>
    <div style="flex: 1" />
    <button @click="showAddVehicle = true">+ Добавить фуру</button>
    <button @click="showRegister = true">+ Зарегистрировать</button>
    <button @click="showClaim = true">+ Привязать</button>
  </div>

  <div v-if="flash" class="flash" :class="flash.type" @click="flash = null">
    {{ flash.text }}
  </div>

  <div v-if="!list.length" class="muted">
    <span class="spinner" /> Загрузка…
  </div>

  <table v-else class="devices-table">
    <thead>
      <tr>
        <th>Серийник</th>
        <th>Статус</th>
        <th>Фура</th>
        <th>Online</th>
        <th>Last ping</th>
        <th>Фрагмент</th>
        <th>Действия</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="d in list" :key="d.id">
        <td><code>{{ d.serialNumber }}</code></td>
        <td>
          <span class="badge" :class="{
            online: d.status === 'active',
            warning: d.status === 'claimed',
            offline: d.status === 'manufactured',
            critical: d.status === 'deactivated'
          }">{{ d.status }}</span>
        </td>
        <td>
          <span v-if="d.vehicleName">{{ d.vehicleName }} <span class="muted-inline">({{ d.vehiclePlate }})</span></span>
          <span v-else class="muted-inline">—</span>
        </td>
        <td>
          <span class="badge" :class="d.isOnline ? 'online' : 'offline'">
            {{ d.isOnline ? 'онлайн' : 'оффлайн' }}
          </span>
        </td>
        <td class="muted-inline">{{ fmt(d.lastPingAt) }}</td>
        <td><code v-if="d.secretFragment">{{ d.secretFragment }}</code><span v-else class="muted-inline">—</span></td>
        <td class="actions">
          <button v-if="d.status !== 'manufactured'" :disabled="busyId === d.id" @click="assign(d)">Фура</button>
          <button v-if="d.status !== 'manufactured'" :disabled="busyId === d.id" @click="rotate(d)">Ротация</button>
          <button v-if="d.status !== 'manufactured'" :disabled="busyId === d.id" class="danger" @click="unclaim(d)">Unclaim</button>
        </td>
      </tr>
    </tbody>
  </table>

  <ClaimModal v-if="showClaim"
              :vehicles="vehicles || []"
              @close="showClaim = false"
              @claimed="onClaimed" />

  <RegisterDeviceModal v-if="showRegister"
              @close="showRegister = false"
              @created="refreshDevices" />

  <AddVehicleModal v-if="showAddVehicle"
              @close="showAddVehicle = false"
              @created="refreshVehicles" />

  <AssignVehicleModal v-if="assignTarget"
              :device="assignTarget"
              :vehicles="vehicles || []"
              @close="assignTarget = null"
              @assigned="onAssigned"
              @vehicleCreated="refreshVehicles" />

  <EnrollmentCodesPanel />
</template>

<style scoped>
.devices-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  font-size: 13px;
}
.devices-table th {
  text-align: left; padding: 10px 14px;
  background: var(--surface-2);
  color: var(--text-muted); font-size: 11px;
  text-transform: uppercase; letter-spacing: .5px; font-weight: 600;
  border-bottom: 1px solid var(--border-soft);
}
.devices-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-soft);
  vertical-align: middle;
}
.devices-table tr:last-child td { border-bottom: none; }
.devices-table code {
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  background: var(--bg); padding: 1px 6px; border-radius: 3px;
}
.muted-inline { color: var(--text-muted); font-size: 12px; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.actions button { padding: 4px 10px; font-size: 12px; }
.actions button.danger { color: var(--red); border-color: rgba(248,81,73,.3); }
.actions button.danger:hover { border-color: var(--red); }

.flash {
  padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; cursor: pointer;
  font-size: 13px;
}
.flash.ok  { background: rgba(63,185,80,.08); border: 1px solid rgba(63,185,80,.3); color: var(--green); }
.flash.err { background: rgba(248,81,73,.08); border: 1px solid rgba(248,81,73,.3); color: var(--red); }
</style>
