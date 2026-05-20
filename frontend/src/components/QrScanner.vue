<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Html5Qrcode } from 'html5-qrcode'

const emit = defineEmits(['decode', 'error'])
const elId = 'qr-scanner-' + Math.random().toString(36).slice(2, 8)
const status = ref('Запуск камеры…')
let scanner = null

onMounted(async () => {
  scanner = new Html5Qrcode(elId)
  try {
    const cameras = await Html5Qrcode.getCameras()
    if (!cameras?.length) throw new Error('Камера не найдена')
    await scanner.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 240, height: 240 } },
      (text) => emit('decode', text),
      () => { /* ignore intermediate scan errors */ }
    )
    status.value = 'Наведите на QR'
  } catch (e) {
    status.value = ''
    emit('error', e?.message || 'Не удалось открыть камеру')
  }
})

onBeforeUnmount(async () => {
  if (scanner) {
    try { await scanner.stop() } catch {}
    try { await scanner.clear() } catch {}
  }
})
</script>

<template>
  <div class="qr">
    <div :id="elId" class="qr__viewport" />
    <div v-if="status" class="qr__hint">{{ status }}</div>
  </div>
</template>

<style scoped>
.qr { position: relative; }
.qr__viewport { width: 100%; max-width: 320px; aspect-ratio: 1; border-radius: 8px; overflow: hidden; background: #000; margin: 0 auto; }
.qr__hint { font-size: 12px; color: var(--text-muted); text-align: center; margin-top: 8px; }
.qr__viewport :deep(video) { width: 100%; height: 100%; object-fit: cover; }
</style>
