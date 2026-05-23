<template>
  <div class="trip-card" :class="{ open }" @click="$emit('toggle')">
    <div class="trip-card-head">
      <div class="trip-card-when">
        <span class="trip-card-date">{{ dateText }}</span>
        <span class="trip-card-status" :class="trip.status">
          {{ trip.status === 'open' ? 'в движении' : 'завершена' }}
        </span>
      </div>
      <div class="trip-card-time">{{ timeText }}</div>
    </div>

    <div class="trip-card-stats">
      <div class="stat">
        <div class="stat-label">Длительность</div>
        <div class="stat-value">{{ durationText }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">
          Пробег
          <span v-if="trip.gpsSpoofSuspect" class="spoof-badge" :title="spoofTooltip">⚠</span>
        </div>
        <div class="stat-value" :title="distanceTooltip">{{ distanceText }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Макс. скорость</div>
        <div class="stat-value">{{ trip.maxSpeed ? trip.maxSpeed.toFixed(0) + ' км/ч' : '—' }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Средняя скорость</div>
        <div class="stat-value">{{ trip.avgSpeed ? trip.avgSpeed.toFixed(0) + ' км/ч' : '—' }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Расход топлива</div>
        <div class="stat-value">{{ trip.fuelUsedPercent ? trip.fuelUsedPercent.toFixed(1) + ' %' : '—' }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Ошибки</div>
        <div class="stat-value">{{ trip.dtcCount || 0 }}</div>
      </div>
    </div>

    <div class="trip-card-toggle">
      {{ open ? 'Скрыть детали и карту ▴' : 'Подробнее и карта ▾' }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  trip: { type: Object, required: true },
  open: { type: Boolean, default: false }
})
defineEmits(['toggle'])

const dateText = computed(() => {
  const d = new Date(props.trip.startedAt)
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })
})
const timeText = computed(() => {
  const a = new Date(props.trip.startedAt)
  const start = a.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  if (!props.trip.endedAt) return start + ' → …'
  const b = new Date(props.trip.endedAt)
  return start + ' → ' + b.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})
const durationText = computed(() => {
  const s = props.trip.durationSec || 0
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h} ч ${m} мин`
  return `${m} мин`
})
const distanceText = computed(() => {
  const d = props.trip.distanceOdoKm ?? props.trip.distanceGpsKm ?? props.trip.distanceSpeedKm
  if (d == null) return '—'
  return d.toFixed(1) + ' км'
})
const distanceTooltip = computed(() => {
  const fmt = v => v == null ? '—' : v.toFixed(2) + ' км'
  return `Три независимых оценки:\nОдометр J1939: ${fmt(props.trip.distanceOdoKm)}\nГеометрия GPS: ${fmt(props.trip.distanceGpsKm)}\nИнтеграл скорости: ${fmt(props.trip.distanceSpeedKm)}`
})
const spoofTooltip = computed(() => {
  return 'Расхождение GPS-пробега и интеграла скорости превышает 30 %. Возможна подмена координат.'
})
</script>

<style scoped>
.trip-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: box-shadow .15s ease, border-color .15s ease;
}
.trip-card:hover { border-color: #94a3b8; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.trip-card.open { border-color: #1f6feb; box-shadow: 0 1px 4px rgba(31,111,235,.18); }
.trip-card-head {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 10px;
}
.trip-card-date { font-weight: 600; color: #0f172a; font-size: 15px; }
.trip-card-status {
  margin-left: 10px;
  font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
  padding: 2px 8px; border-radius: 999px;
  background: #e0e7ff; color: #3730a3;
}
.trip-card-status.open { background: #d1fae5; color: #065f46; }
.trip-card-time { color: #475569; font-size: 13px; font-variant-numeric: tabular-nums; }
.trip-card-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px 14px;
}
.stat .stat-label { color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; }
.stat .stat-value { color: #0f172a; font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; }
.spoof-badge { color: #d97706; cursor: help; margin-left: 4px; }
.trip-card-toggle { margin-top: 10px; color: #1f6feb; font-size: 13px; text-align: right; }
</style>