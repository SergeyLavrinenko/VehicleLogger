<template>
  <div class="trips-tab">
    <div class="trips-header">
      <h3>Поездки</h3>
      <button class="reload-btn" @click="reload" :disabled="loading">↻ Обновить</button>
    </div>

    <div v-if="loading && items.length === 0" class="state">Загрузка…</div>
    <div v-else-if="!loading && items.length === 0" class="state state-empty">
      Поездок пока нет — устройство ещё не передавало GPS-данные или находится в покое.
    </div>

    <div v-else>
      <div v-for="trip in items" :key="trip.id">
        <TripCard :trip="trip" :open="openTripId === trip.id" @toggle="toggle(trip.id)" />
        <div v-if="openTripId === trip.id" class="trip-detail">
          <TripMap :points="currentTrackPoints" :loading="trackLoading" />
          <div v-if="currentTrip" class="trip-extra">
            <div class="extra-row">
              <span>Точек в треке:</span>
              <b>{{ currentTrip.pointCount }}</b>
            </div>
            <div class="extra-row">
              <span>Средние обороты:</span>
              <b>{{ currentTrip.avgRpm ? currentTrip.avgRpm.toFixed(0) : '—' }} об/мин</b>
            </div>
            <div class="extra-row">
              <span>Максимальные обороты:</span>
              <b>{{ currentTrip.maxRpm ? currentTrip.maxRpm.toFixed(0) : '—' }} об/мин</b>
            </div>
            <div class="extra-row" v-if="currentTrip.fuelStartPercent != null">
              <span>Топливо начало/конец:</span>
              <b>{{ currentTrip.fuelStartPercent.toFixed(1) }} % → {{ currentTrip.fuelEndPercent != null ? currentTrip.fuelEndPercent.toFixed(1) + ' %' : '—' }}</b>
            </div>
            <div class="extra-row" v-if="currentTrip.odoStartKm != null">
              <span>Одометр начало/конец:</span>
              <b>{{ currentTrip.odoStartKm.toFixed(1) }} → {{ currentTrip.odoEndKm != null ? currentTrip.odoEndKm.toFixed(1) : '—' }} км</b>
            </div>
            <div class="extra-row" v-if="currentTrip.dtcCodes && currentTrip.dtcCodes.length">
              <span>Коды ошибок:</span>
              <b>{{ currentTrip.dtcCodes.join(', ') }}</b>
            </div>
          </div>
        </div>
      </div>

      <div class="pager" v-if="total > take">
        <button @click="prev" :disabled="skip === 0">← Назад</button>
        <span>{{ skip + 1 }}–{{ Math.min(skip + items.length, total) }} из {{ total }}</span>
        <button @click="next" :disabled="skip + items.length >= total">Вперёд →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { apiCalls } from '../api'
import TripCard from './TripCard.vue'
import TripMap from './TripMap.vue'

const props = defineProps({
  vehicleId: { type: Number, required: true }
})

const items = ref([])
const total = ref(0)
const skip  = ref(0)
const take  = ref(20)
const loading = ref(false)

const openTripId = ref(null)
const currentTrip = ref(null)
const currentTrack = ref(null)
const trackLoading = ref(false)

const currentTrackPoints = computed(() => currentTrack.value?.points || [])

async function reload() {
  loading.value = true
  try {
    const data = await apiCalls.listTrips(props.vehicleId, skip.value, take.value)
    items.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

async function toggle(tripId) {
  if (openTripId.value === tripId) {
    openTripId.value = null
    currentTrip.value = null
    currentTrack.value = null
    return
  }
  openTripId.value = tripId
  currentTrip.value = null
  currentTrack.value = null
  trackLoading.value = true
  try {
    const [t, track] = await Promise.all([
      apiCalls.getTrip(tripId),
      apiCalls.getTripTrack(tripId)
    ])
    currentTrip.value = t
    currentTrack.value = track
  } finally {
    trackLoading.value = false
  }
}

function prev() {
  if (skip.value === 0) return
  skip.value = Math.max(0, skip.value - take.value)
  reload()
}
function next() {
  if (skip.value + items.value.length >= total.value) return
  skip.value += take.value
  reload()
}

watch(() => props.vehicleId, () => { skip.value = 0; openTripId.value = null; reload() })
onMounted(reload)
</script>

<style scoped>
.trips-tab { margin: 0; }
.trips-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.trips-header h3 { margin: 0; font-size: 18px; color: #0f172a; }
.reload-btn {
  background: #f1f5f9; border: 1px solid #cbd5e1; color: #334155;
  padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.reload-btn:hover:not(:disabled) { background: #e2e8f0; }
.state { padding: 30px; text-align: center; color: #64748b; }
.state-empty { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; }
.trip-detail { margin: 0 0 16px 0; padding: 12px; background: #f8fafc; border-radius: 8px; }
.trip-extra { margin-top: 12px; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 6px 16px; }
.extra-row { display: flex; justify-content: space-between; color: #475569; font-size: 13px; padding: 3px 0; }
.extra-row b { color: #0f172a; }
.pager { display: flex; justify-content: center; gap: 16px; align-items: center; margin: 16px 0; color: #475569; }
.pager button {
  background: #f1f5f9; border: 1px solid #cbd5e1; color: #334155;
  padding: 6px 12px; border-radius: 6px; cursor: pointer;
}
.pager button:disabled { opacity: .4; cursor: not-allowed; }
</style>