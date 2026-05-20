<script setup>
import { computed } from 'vue'
import { apiCalls } from '../api'
import { usePolling } from '../composables/usePolling'
import MiniChart from '../components/MiniChart.vue'

const props = defineProps({ id: { type: [String, Number], required: true } })

const { data: vehicle }   = usePolling(() => apiCalls.getVehicle(props.id), 3000)
const { data: telemetry } = usePolling(() => apiCalls.getTelemetry(props.id, 200), 2000)
const { data: alerts }    = usePolling(() => apiCalls.getAlerts(props.id), 5000)
const { data: refuels }   = usePolling(() => apiCalls.getRefuels(props.id), 10000)

const points = computed(() => {
  const t = telemetry.value || []
  return t.map(p => ({ ts: new Date(p.timestamp).getTime(), ...p }))
})

const rpmPoints   = computed(() => points.value.filter(p => p.rpm != null).map(p => ({ x: p.ts, y: p.rpm })))
const speedPoints = computed(() => points.value.filter(p => p.speed != null).map(p => ({ x: p.ts, y: p.speed })))
const tempPoints  = computed(() => points.value.filter(p => p.coolantTemp != null).map(p => ({ x: p.ts, y: p.coolantTemp })))
const oilPoints   = computed(() => points.value.filter(p => p.oilPressure != null).map(p => ({ x: p.ts, y: p.oilPressure })))
const fuelPoints  = computed(() => points.value.filter(p => p.fuelLevel != null).map(p => ({ x: p.ts, y: p.fuelLevel })))
const voltPoints  = computed(() => points.value.filter(p => p.voltage != null).map(p => ({ x: p.ts, y: p.voltage })))

const recentLog = computed(() => (telemetry.value || []).slice(-15).reverse())

function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleTimeString('ru-RU')
}
function fmtFull(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('ru-RU')
}
</script>

<template>
  <router-link to="/" class="back-link">← К списку фур</router-link>

  <template v-if="vehicle">
    <div class="detail-head">
      <div class="detail-head__title">
        <h2>{{ vehicle.name }}</h2>
        <div class="sub">{{ vehicle.licensePlate }}</div>
      </div>
      <div class="detail-head__meta">
        <span>
          Устройство:
          <b style="font-family: 'SF Mono', Consolas, monospace; font-size: 12px;">
            {{ vehicle.device?.serialNumber || '—' }}
          </b>
        </span>
        <span>Последний ping: <b>{{ fmtTime(vehicle.device?.lastPingAt) }}</b></span>
        <span>
          Статус:
          <span class="badge" :class="vehicle.device?.isOnline ? 'online' : 'offline'">
            {{ vehicle.device?.isOnline ? 'онлайн' : 'оффлайн' }}
          </span>
        </span>
      </div>
    </div>

    <section class="charts">
      <MiniChart label="RPM"           unit=""    color="#58a6ff" :points="rpmPoints" />
      <MiniChart label="Скорость"      unit="км/ч" color="#3fb950" :points="speedPoints" />
      <MiniChart label="Темп. ОЖ"      unit="°C"   color="#d29922" :points="tempPoints" :y-min="60" :y-max="120" />
      <MiniChart label="Давление масла" unit="бар"  color="#bc8cff" :points="oilPoints" />
      <MiniChart label="Топливо"       unit="%"    color="#db6d28" :points="fuelPoints" :y-min="0" :y-max="100" />
      <MiniChart label="Напряжение"    unit="В"    color="#f85149" :points="voltPoints" :y-min="11" :y-max="15" />
    </section>

    <div class="detail-grid">
      <div class="panel">
        <div class="panel__head">
          <h3>Последние пакеты</h3>
          <span class="panel__meta">{{ recentLog.length }} строк</span>
        </div>
        <div class="panel__body log-scroll">
          <table class="log-table">
            <thead>
              <tr>
                <th>Время</th>
                <th class="col-num">RPM</th>
                <th class="col-num">км/ч</th>
                <th class="col-num">°C ОЖ</th>
                <th class="col-num">бар</th>
                <th class="col-num">%</th>
                <th class="col-num">В</th>
                <th>DTC</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in recentLog" :key="i">
                <td class="col-time">{{ fmtTime(t.timestamp) }}</td>
                <td class="col-num">{{ t.rpm ?? '—' }}</td>
                <td class="col-num">{{ t.speed ?? '—' }}</td>
                <td class="col-num">{{ t.coolantTemp ?? '—' }}</td>
                <td class="col-num">{{ t.oilPressure ?? '—' }}</td>
                <td class="col-num">{{ t.fuelLevel ?? '—' }}</td>
                <td class="col-num">{{ t.voltage ?? '—' }}</td>
                <td>
                  <template v-if="t.dtcCodes?.length">
                    <span v-for="code in t.dtcCodes" :key="code" class="tag">{{ code }}</span>
                  </template>
                  <template v-else>—</template>
                </td>
              </tr>
              <tr v-if="!recentLog.length">
                <td colspan="8" class="muted">Нет данных</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <aside style="display: flex; flex-direction: column; gap: 16px;">
        <div class="panel">
          <div class="panel__head">
            <h3>Алерты</h3>
            <span class="panel__meta">{{ alerts?.length || 0 }}</span>
          </div>
          <div class="panel__body">
            <div v-if="!alerts?.length" class="muted">Нет алертов</div>
            <div v-else class="list">
              <div v-for="a in alerts" :key="a.id" class="list__item">
                <div class="list__row">
                  <span class="badge" :class="a.severity">{{ a.severity }}</span>
                  <span class="list__time">{{ fmtTime(a.timestamp) }}</span>
                </div>
                <div class="list__main">{{ a.description }}</div>
                <div v-if="a.recommendation" class="list__sub">→ {{ a.recommendation }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel__head">
            <h3>Заправки</h3>
            <span class="panel__meta">{{ refuels?.length || 0 }}</span>
          </div>
          <div class="panel__body">
            <div v-if="!refuels?.length" class="muted">Нет заправок</div>
            <div v-else class="list">
              <div v-for="r in refuels" :key="r.id" class="list__item">
                <div class="list__row">
                  <span class="list__main">{{ r.liters }} л</span>
                  <span class="list__time">{{ fmtFull(r.timestamp) }}</span>
                </div>
                <div class="list__sub">{{ r.cost?.toLocaleString('ru-RU') }} ₽</div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </template>

  <div v-else class="muted">
    <span class="spinner" /> Загрузка фуры…
  </div>
</template>
