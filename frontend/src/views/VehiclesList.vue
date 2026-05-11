<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiCalls } from '../api'
import { usePolling } from '../composables/usePolling'
import { useAuth } from '../composables/useAuth'
import AddVehicleModal from '../components/AddVehicleModal.vue'

const router = useRouter()
const { isAdmin } = useAuth()

const { data: vehicles, loading, refresh } = usePolling(apiCalls.getVehicles, 5000)
const { data: dashboard } = usePolling(apiCalls.getDashboard, 5000)

const list = computed(() => vehicles.value || [])
const showAdd = ref(false)

function open(id) {
  router.push({ name: 'vehicle-details', params: { id } })
}

function fmt(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleTimeString('ru-RU')
}

function ago(ts) {
  if (!ts) return '—'
  const diff = (Date.now() - new Date(ts).getTime()) / 1000
  if (diff < 0)     return 'только что'
  if (diff < 5)     return 'только что'
  if (diff < 60)    return `${Math.round(diff)} с назад`
  if (diff < 3600)  return `${Math.round(diff / 60)} мин назад`
  if (diff < 86400) return `${Math.round(diff / 3600)} ч назад`
  return `${Math.round(diff / 86400)} д назад`
}
</script>

<template>
  <section class="kpis">
    <div class="kpi kpi--accent">
      <div class="kpi__label">Всего фур</div>
      <div class="kpi__value">{{ dashboard?.vehiclesTotal ?? '—' }}</div>
    </div>
    <div class="kpi kpi--good">
      <div class="kpi__label">Онлайн</div>
      <div class="kpi__value">{{ dashboard?.devicesOnline ?? '—' }}</div>
      <div class="kpi__sub">из {{ dashboard?.vehiclesTotal ?? '—' }}</div>
    </div>
    <div class="kpi kpi--warn">
      <div class="kpi__label">Алертов</div>
      <div class="kpi__value">{{ dashboard?.alertsUnread ?? 0 }}</div>
      <div class="kpi__sub">непрочитанных</div>
    </div>
    <div class="kpi">
      <div class="kpi__label">Заправок сегодня</div>
      <div class="kpi__value">{{ dashboard?.refuelsToday ?? 0 }}</div>
    </div>
  </section>

  <div class="section-divider">
    <h2 class="section-divider__title">Автопарк</h2>
    <span class="section-divider__count">{{ list.length || '—' }}</span>
    <div style="flex: 1" />
    <button v-if="isAdmin" @click="showAdd = true">+ Добавить фуру</button>
  </div>

  <div v-if="loading && !list.length" class="muted">
    <span class="spinner" /> Загрузка фур…
  </div>

  <div v-else-if="!list.length" class="muted">
    Нет ни одной фуры.
    <template v-if="isAdmin">
      Нажмите <b>«+ Добавить фуру»</b>, затем привяжите к ней устройство на странице
      <router-link to="/devices">Устройства</router-link>.
    </template>
  </div>

  <section v-else class="cards">
    <div v-for="v in list" :key="v.id" class="card" @click="open(v.id)">
      <div class="card__head">
        <div>
          <div class="card__name">{{ v.name }}</div>
          <div class="card__plate">{{ v.licensePlate }}</div>
        </div>
        <span class="badge" :class="v.device?.isOnline ? 'online' : 'offline'">
          {{ v.device?.isOnline ? 'онлайн' : 'оффлайн' }}
        </span>
      </div>

      <div class="card__metrics">
        <div class="card__metric">
          <span>Устройство</span>
          <strong style="font-size: 12px; font-family: 'SF Mono', Consolas, monospace;">
            {{ v.device?.serialNumber || '—' }}
          </strong>
        </div>
        <div class="card__metric">
          <span>Последний пакет</span>
          <strong style="font-size: 13px;">{{ ago(v.lastTelemetryAt) }}</strong>
        </div>
      </div>
    </div>
  </section>

  <AddVehicleModal v-if="showAdd"
                   @close="showAdd = false"
                   @created="refresh" />
</template>
