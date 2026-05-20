<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import {
  Chart, LineController, LineElement, PointElement,
  LinearScale, TimeScale, CategoryScale, Tooltip, Filler
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement,
  LinearScale, TimeScale, CategoryScale, Tooltip, Filler)

const props = defineProps({
  label:  { type: String, required: true },
  unit:   { type: String, default: '' },
  color:  { type: String, default: '#58a6ff' },
  points: { type: Array,  required: true }, // [{x: Date|ms, y: Number}]
  yMin:   { type: Number, default: undefined },
  yMax:   { type: Number, default: undefined }
})

const canvasEl = ref(null)
let chart = null

function fmtTime(ts) {
  const d = new Date(ts)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function makeData() {
  const labels = props.points.map(p => fmtTime(p.x))
  const values = props.points.map(p => p.y)
  return {
    labels,
    datasets: [{
      label: props.label,
      data: values,
      borderColor: props.color,
      backgroundColor: props.color + '22',
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.25,
      fill: true
    }]
  }
}

function makeOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0d1117',
        borderColor: '#30363d',
        borderWidth: 1,
        titleColor: '#e6edf3',
        bodyColor: '#e6edf3',
        callbacks: {
          label: (ctx) => `${ctx.parsed.y}${props.unit ? ' ' + props.unit : ''}`
        }
      }
    },
    scales: {
      x: {
        grid: { color: '#21262d' },
        ticks: { color: '#7d8590', maxTicksLimit: 6, autoSkip: true, font: { size: 10 } }
      },
      y: {
        min: props.yMin, max: props.yMax,
        grid: { color: '#21262d' },
        ticks: { color: '#7d8590', font: { size: 10 } }
      }
    }
  }
}

onMounted(() => {
  chart = new Chart(canvasEl.value, {
    type: 'line',
    data: makeData(),
    options: makeOptions()
  })
})

watch(() => props.points, () => {
  if (!chart) return
  const d = makeData()
  chart.data.labels = d.labels
  chart.data.datasets[0].data = d.datasets[0].data
  chart.update('none')
}, { deep: true })

onBeforeUnmount(() => { chart?.destroy() })
</script>

<template>
  <div class="mini-chart">
    <div class="mini-chart__head">
      <span class="mini-chart__label">{{ label }}</span>
      <span class="mini-chart__last" v-if="points.length">
        {{ points[points.length - 1].y }}<span v-if="unit"> {{ unit }}</span>
      </span>
    </div>
    <div class="mini-chart__body">
      <canvas ref="canvasEl" />
    </div>
  </div>
</template>

<style scoped>
.mini-chart {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}
.mini-chart__head {
  display: flex; align-items: baseline; justify-content: space-between;
}
.mini-chart__label {
  font-size: 12px; text-transform: uppercase; letter-spacing: .5px;
  color: var(--text-muted); font-weight: 600;
}
.mini-chart__last {
  font-size: 18px; font-weight: 600; color: var(--text);
  font-variant-numeric: tabular-nums;
}
.mini-chart__body {
  position: relative; height: 140px;
}
</style>
