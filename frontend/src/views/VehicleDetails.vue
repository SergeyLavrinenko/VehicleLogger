<script setup>
import { computed, ref, onMounted } from 'vue'
import { apiCalls } from '../api'
import { usePolling } from '../composables/usePolling'
import MiniChart from '../components/MiniChart.vue'
import TripsTab from '../components/TripsTab.vue'

const props = defineProps({ id: { type: [String, Number], required: true } })

const { data: vehicle }   = usePolling(() => apiCalls.getVehicle(props.id), 3000)
const { data: telemetry } = usePolling(() => apiCalls.getTelemetry(props.id, 200), 2000)
const { data: alerts }    = usePolling(() => apiCalls.getAlerts(props.id), 5000)
const { data: refuels }   = usePolling(() => apiCalls.getRefuels(props.id), 10000)

const aiSummary = ref(null)
const aiLoading = ref(false)
const aiError   = ref('')

async function loadAiSummary(force = false) {
  aiLoading.value = true
  aiError.value   = ''
  try {
    const data = force
      ? await apiCalls.regenerateAiSummary(props.id)
      : await apiCalls.getAiSummary(props.id)
    aiSummary.value = data
  } catch (e) {
    aiError.value = e?.response?.data?.message || e?.message || 'Не удалось получить сводку'
  } finally {
    aiLoading.value = false
  }
}

onMounted(() => { loadAiSummary(false) })

// Парсим ответ модели в структуру { verdict, risks[], actions[] }.
// Бэкенд просит формат "VERDICT: ...\nRISK: ...\nACTION: ...", но если
// модель ушла в свободный текст — fallback на показ как есть.
const parsedSummary = computed(() => {
  const raw = aiSummary.value?.content || ''
  if (!raw) return null
  // нормализуем неразрывные пробелы и markdown
  const cleaned = raw
    .replace(/ | /g, ' ')
    .replace(/\*\*/g, '')
    .replace(/__/g, '')

  const lines = cleaned.split('\n').map(s => s.trim()).filter(Boolean)
  const verdicts = []
  const risks    = []
  const actions  = []
  let recognized = 0

  for (const line of lines) {
    const m = line.match(/^(VERDICT|RISK|ACTION)\s*[:\-]\s*(.+)$/i)
    if (m) {
      recognized++
      const tag  = m[1].toUpperCase()
      const text = m[2].trim().replace(/^[-•·]\s*/, '')
      if      (tag === 'VERDICT') verdicts.push(text)
      else if (tag === 'RISK')    risks.push(text)
      else if (tag === 'ACTION')  actions.push(text)
    }
  }

  if (recognized === 0) {
    return { structured: false, raw: cleaned, verdict: '', risks: [], actions: [] }
  }
  return {
    structured: true,
    raw: cleaned,
    verdict: verdicts.join(' '),
    risks,
    actions
  }
})

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
function fmtRelative(ts) {
  if (!ts) return ''
  const diffMs = Date.now() - new Date(ts).getTime()
  const sec = Math.round(diffMs / 1000)
  if (sec < 5) return 'только что'
  if (sec < 60) return `${sec} с назад`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min} мин назад`
  const h = Math.round(min / 60)
  if (h < 24) return `${h} ч назад`
  const d = Math.round(h / 24)
  return `${d} дн назад`
}
</script>

<template>
  <router-link to="/" class="back-link">← К списку фур</router-link>

  <template v-if="vehicle">
    <header class="vh-head">
      <div class="vh-head__left">
        <h2 class="vh-head__name">{{ vehicle.name }}</h2>
        <span class="vh-head__plate">{{ vehicle.licensePlate }}</span>
      </div>
      <div class="vh-head__right">
        <span class="badge" :class="vehicle.device?.isOnline ? 'online' : 'offline'">
          {{ vehicle.device?.isOnline ? 'онлайн' : 'оффлайн' }}
        </span>
        <div class="vh-head__meta">
          <span class="vh-head__meta-item">
            <span class="vh-head__meta-label">Устройство</span>
            <b class="mono">{{ vehicle.device?.serialNumber || '—' }}</b>
          </span>
          <span class="vh-head__meta-item">
            <span class="vh-head__meta-label">Ping</span>
            <b>{{ fmtTime(vehicle.device?.lastPingAt) }}</b>
          </span>
        </div>
      </div>
    </header>

    <!-- ИИ сводка -->
    <section class="ai-card" :class="{ 'ai-card--loading': aiLoading && !aiSummary }">
      <div class="ai-card__head">
        <div class="ai-card__title">
          <span class="ai-card__icon" aria-hidden="true">AI</span>
          <h3>ИИ сводка</h3>
          <span v-if="aiSummary?.cached" class="ai-card__tag">кэш</span>
          <span v-if="aiSummary?.stale" class="ai-card__tag ai-card__tag--warn">устарела</span>
        </div>
        <div class="ai-card__head-right">
          <span v-if="aiSummary?.generatedAt" class="ai-card__time" :title="fmtFull(aiSummary.generatedAt)">
            обновлено {{ fmtRelative(aiSummary.generatedAt) }}
          </span>
          <button class="ai-card__btn" :disabled="aiLoading" @click="loadAiSummary(true)">
            <span v-if="aiLoading" class="spinner" />
            <span>{{ aiLoading ? 'Генерация…' : 'Обновить' }}</span>
          </button>
        </div>
      </div>

      <div class="ai-card__body">
        <div v-if="aiError" class="ai-card__error">{{ aiError }}</div>

        <template v-if="parsedSummary?.structured">
          <div v-if="parsedSummary.verdict" class="ai-verdict">
            <span class="ai-verdict__label">Вердикт</span>
            <p class="ai-verdict__text">{{ parsedSummary.verdict }}</p>
          </div>

          <div class="ai-sections">
            <div v-if="parsedSummary.risks.length" class="ai-section ai-section--risk">
              <div class="ai-section__head">
                <span class="ai-section__dot" />
                <h4>Риски</h4>
              </div>
              <ul class="ai-section__list">
                <li v-for="(r, i) in parsedSummary.risks" :key="'r'+i">{{ r }}</li>
              </ul>
            </div>

            <div v-if="parsedSummary.actions.length" class="ai-section ai-section--action">
              <div class="ai-section__head">
                <span class="ai-section__dot" />
                <h4>Рекомендации</h4>
              </div>
              <ul class="ai-section__list">
                <li v-for="(a, i) in parsedSummary.actions" :key="'a'+i">{{ a }}</li>
              </ul>
            </div>
          </div>
        </template>

        <div v-else-if="parsedSummary && !parsedSummary.structured" class="ai-raw">
          {{ parsedSummary.raw }}
        </div>

        <div v-else-if="aiLoading" class="ai-card__loading">
          <span class="spinner" /> Анализирую телеметрию…
        </div>

        <div v-else class="muted">Нет данных для анализа.</div>

        <div v-if="aiSummary?.model" class="ai-card__foot">
          <span class="mono">{{ aiSummary.model }}</span>
        </div>
      </div>
    </section>

    <!-- Графики -->
    <section class="section">
      <div class="section__head">
        <h3>Телеметрия</h3>
        <span class="section__sub">за последние {{ (telemetry || []).length }} пакетов</span>
      </div>
      <div class="charts">
        <MiniChart label="RPM"            unit=""     color="#58a6ff" :points="rpmPoints" />
        <MiniChart label="Скорость"       unit="км/ч" color="#3fb950" :points="speedPoints" />
        <MiniChart label="Темп. ОЖ"       unit="°C"   color="#d29922" :points="tempPoints" :y-min="60" :y-max="120" />
        <MiniChart label="Давление масла" unit="бар"  color="#bc8cff" :points="oilPoints" />
        <MiniChart label="Топливо"        unit="%"    color="#db6d28" :points="fuelPoints" :y-min="0" :y-max="100" />
        <MiniChart label="Напряжение"     unit="В"    color="#f85149" :points="voltPoints" :y-min="11" :y-max="15" />
      </div>
    </section>

    <!-- Поездки -->
    <section class="section">
      <TripsTab :vehicle-id="vehicle.id" />
    </section>

    <!-- Журнал + Алерты + Заправки -->
    <section class="section">
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

        <aside class="detail-grid__side">
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
    </section>
  </template>

  <div v-else class="muted">
    <span class="spinner" /> Загрузка фуры…
  </div>
</template>

<style scoped>
/* ===== Header ===== */
.vh-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px; flex-wrap: wrap;
  margin-bottom: 20px;
}
.vh-head__left { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.vh-head__name { margin: 0; font-size: 24px; font-weight: 600; line-height: 1.2; }
.vh-head__plate {
  font-family: 'SF Mono', Consolas, monospace; font-size: 13px;
  padding: 3px 10px; border-radius: 6px;
  background: var(--surface-2); border: 1px solid var(--border);
  color: var(--text-muted);
}
.vh-head__right { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.vh-head__meta { display: flex; gap: 18px; flex-wrap: wrap; }
.vh-head__meta-item { display: flex; flex-direction: column; }
.vh-head__meta-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: .5px;
  color: var(--text-muted); margin-bottom: 2px;
}
.vh-head__meta-item b { font-size: 13px; font-weight: 500; }
.mono { font-family: 'SF Mono', Consolas, monospace; font-size: 12px; }

/* ===== Section wrapper ===== */
.section { margin-bottom: 20px; }
.section__head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px; margin-bottom: 10px;
}
.section__head h3 {
  margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: .6px;
  color: var(--text-muted); font-weight: 600;
}
.section__sub { font-size: 12px; color: var(--text-muted); }

/* ===== AI card ===== */
.ai-card {
  position: relative;
  background:
    radial-gradient(ellipse at top left, rgba(88,166,255,.08), transparent 60%),
    linear-gradient(180deg, var(--surface), var(--surface-2));
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: 24px;
  overflow: hidden;
}
.ai-card::before {
  content: '';
  position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: linear-gradient(180deg, var(--accent), var(--purple));
}
.ai-card__head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; flex-wrap: wrap;
  padding: 12px 16px 12px 18px;
  border-bottom: 1px solid var(--border-soft);
}
.ai-card__title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ai-card__icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px;
  border-radius: 7px;
  background: linear-gradient(135deg, var(--accent), var(--purple));
  color: #fff; font-size: 10px; font-weight: 700; letter-spacing: .5px;
}
.ai-card__title h3 {
  margin: 0; font-size: 14px; font-weight: 600;
  color: var(--text); text-transform: none; letter-spacing: 0;
}
.ai-card__tag {
  font-size: 10px; text-transform: uppercase; letter-spacing: .5px;
  padding: 2px 7px; border-radius: 10px;
  background: rgba(139,148,158,.15); color: var(--text-muted);
  border: 1px solid var(--border);
}
.ai-card__tag--warn {
  background: rgba(210,153,34,.12); color: var(--yellow);
  border-color: rgba(210,153,34,.3);
}
.ai-card__head-right { display: flex; align-items: center; gap: 12px; }
.ai-card__time { font-size: 12px; color: var(--text-muted); }
.ai-card__btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: rgba(88,166,255,.1); color: var(--accent);
  border: 1px solid rgba(88,166,255,.25); border-radius: 6px;
  font-size: 12px; font-weight: 500;
}
.ai-card__btn:hover:not(:disabled) {
  background: rgba(88,166,255,.18); border-color: var(--accent);
}
.ai-card__btn:disabled { opacity: .65; cursor: progress; }

.ai-card__body { padding: 14px 18px 16px; }

.ai-verdict {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 14px;
  background: rgba(88,166,255,.06);
  border: 1px solid rgba(88,166,255,.2);
  border-radius: 8px;
  margin-bottom: 14px;
}
.ai-verdict__label {
  flex-shrink: 0;
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .8px;
  color: var(--accent);
  padding-top: 3px;
}
.ai-verdict__text {
  margin: 0; font-size: 14px; line-height: 1.5; color: var(--text);
}

.ai-sections {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
@media (max-width: 720px) { .ai-sections { grid-template-columns: 1fr; } }

.ai-section {
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--surface);
}
.ai-section__head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ai-section__head h4 {
  margin: 0; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .6px;
}
.ai-section__dot { width: 8px; height: 8px; border-radius: 50%; }
.ai-section--risk   .ai-section__dot { background: var(--yellow); box-shadow: 0 0 0 3px rgba(210,153,34,.15); }
.ai-section--risk   .ai-section__head h4 { color: var(--yellow); }
.ai-section--action .ai-section__dot { background: var(--green); box-shadow: 0 0 0 3px rgba(63,185,80,.15); }
.ai-section--action .ai-section__head h4 { color: var(--green); }

.ai-section__list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.ai-section__list li {
  position: relative;
  padding-left: 14px;
  font-size: 13px; line-height: 1.5; color: var(--text);
}
.ai-section__list li::before {
  content: ''; position: absolute; left: 0; top: 9px;
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--text-muted);
}
.ai-section--risk   .ai-section__list li::before { background: var(--yellow); }
.ai-section--action .ai-section__list li::before { background: var(--green); }

.ai-raw {
  white-space: pre-wrap; font-size: 13px; line-height: 1.55; color: var(--text);
}
.ai-card__loading { color: var(--text-muted); padding: 10px 0; }
.ai-card__error {
  color: var(--red); font-size: 13px;
  background: rgba(248,81,73,.08); border: 1px solid rgba(248,81,73,.25);
  border-radius: 6px; padding: 8px 12px; margin-bottom: 12px;
}
.ai-card__foot {
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid var(--border-soft);
  font-size: 11px; color: var(--text-muted);
  display: flex; justify-content: flex-end;
}

/* ===== Detail grid (нижняя секция) ===== */
.detail-grid__side { display: flex; flex-direction: column; gap: 16px; }
</style>
