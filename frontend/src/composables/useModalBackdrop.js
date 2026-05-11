import { ref } from 'vue'

/**
 * Корректное закрытие модалки по клику на бэкдроп:
 * - mousedown и mouseup должны произойти на самом бэкдропе (не на детях),
 *   чтобы выделение текста с отпусканием за модалкой не закрывало её.
 * - Опциональный guard `lock()` — если возвращает true, бэкдроп не закрывает модалку
 *   (используется когда показаны одноразовые секреты — пароль/код/секрет устройства).
 *
 * Использование:
 *   const { onBackdropMouseDown, onBackdropMouseUp } = useModalBackdrop(close, () => !!created.value)
 *
 *   <div class="modal-backdrop" @mousedown="onBackdropMouseDown" @mouseup="onBackdropMouseUp">
 *     <div class="modal" @mousedown.stop @mouseup.stop>...</div>
 *   </div>
 */
export function useModalBackdrop(close, lock = () => false) {
  const downTarget = ref(null)
  function onBackdropMouseDown(e) { downTarget.value = e.target }
  function onBackdropMouseUp(e) {
    const startedOnBackdrop = downTarget.value === e.currentTarget
    const endedOnBackdrop   = e.target === e.currentTarget
    downTarget.value = null
    if (startedOnBackdrop && endedOnBackdrop && !lock()) close()
  }
  return { onBackdropMouseDown, onBackdropMouseUp }
}

/**
 * Унифицированное копирование в буфер с fallback через временный textarea.
 */
export async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {}
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'; ta.style.opacity = '0'; ta.style.left = '-9999px'
  document.body.appendChild(ta)
  ta.select()
  let ok = false
  try { ok = document.execCommand('copy') } catch {}
  document.body.removeChild(ta)
  return ok
}
