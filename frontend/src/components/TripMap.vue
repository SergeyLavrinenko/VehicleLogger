<template>
  <div class="trip-map-host">
    <div ref="mapEl" class="trip-map"></div>
    <div v-if="loading"  class="trip-map-overlay">Загрузка трека…</div>
    <div v-else-if="empty" class="trip-map-overlay">Точек GPS нет</div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, ref } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({
  points: { type: Array, default: () => [] },   // [[lat,lng,speed,ts], ...]
  loading: { type: Boolean, default: false }
})

const mapEl = ref(null)
let map = null
let polyline = null
let startMarker = null
let endMarker = null

const empty = ref(false)

function destroyLayers() {
  if (polyline) { polyline.remove(); polyline = null }
  if (startMarker) { startMarker.remove(); startMarker = null }
  if (endMarker) { endMarker.remove(); endMarker = null }
}

function render() {
  if (!map) return
  destroyLayers()
  const pts = props.points
  if (!pts || pts.length === 0) {
    empty.value = true
    map.setView([55.7558, 37.6173], 5)
    return
  }
  empty.value = false
  const coords = pts.map(p => [p[0], p[1]])
  // Цвет трека = усреднённый по скорости (просто синий пока)
  polyline = L.polyline(coords, { color: '#1f6feb', weight: 4, opacity: 0.85 }).addTo(map)
  const startIcon = L.divIcon({
    html: '<div style="background:#16a34a;color:#fff;border-radius:50%;width:24px;height:24px;line-height:24px;text-align:center;font-size:12px;font-weight:700;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,.4)">S</div>',
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  })
  const endIcon = L.divIcon({
    html: '<div style="background:#dc2626;color:#fff;border-radius:50%;width:24px;height:24px;line-height:24px;text-align:center;font-size:12px;font-weight:700;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,.4)">F</div>',
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  })
  startMarker = L.marker(coords[0], { icon: startIcon }).addTo(map)
  endMarker = L.marker(coords[coords.length - 1], { icon: endIcon }).addTo(map)
  map.fitBounds(polyline.getBounds(), { padding: [24, 24] })
}

onMounted(() => {
  map = L.map(mapEl.value, { zoomControl: true, scrollWheelZoom: true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19
  }).addTo(map)
  render()
})

onBeforeUnmount(() => {
  destroyLayers()
  if (map) { map.remove(); map = null }
})

watch(() => props.points, render, { deep: false })
</script>

<style scoped>
.trip-map-host { position: relative; width: 100%; height: 360px; border-radius: 8px; overflow: hidden; }
.trip-map { width: 100%; height: 100%; }
.trip-map-overlay {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.65); color: #475569; font-size: 14px; pointer-events: none;
}
</style>