import { onMounted, onBeforeUnmount, ref } from 'vue'

/**
 * Запускает fn() сразу и затем каждые intervalMs миллисекунд.
 * Возвращает { data, error, loading, refresh, stop, lastUpdated }.
 * Если fn() вернёт массив значений — раскладывает в data как массив.
 */
export function usePolling(fn, intervalMs = 5000) {
  const data = ref(null)
  const error = ref(null)
  const loading = ref(true)
  const lastUpdated = ref(null)

  let timerId = null
  let aborted = false

  async function refresh() {
    try {
      const r = await fn()
      if (aborted) return
      data.value = r
      error.value = null
      lastUpdated.value = new Date()
    } catch (e) {
      if (aborted) return
      error.value = e
    } finally {
      if (!aborted) loading.value = false
    }
  }

  function tick() { refresh().finally(() => {
    if (!aborted) timerId = setTimeout(tick, intervalMs)
  })}

  function stop() {
    aborted = true
    if (timerId) clearTimeout(timerId)
  }

  onMounted(() => tick())
  onBeforeUnmount(stop)

  return { data, error, loading, refresh, stop, lastUpdated }
}
