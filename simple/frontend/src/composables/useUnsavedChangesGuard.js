import { onBeforeUnmount, onMounted, unref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useConfirmStore } from '../store/confirm'

function resolveFlag(value) {
  if (typeof value === 'function') return !!value()
  return !!unref(value)
}

export function useUnsavedChangesGuard({
  enabled = true,
  isDirty = false,
  message = 'Есть несохранённые изменения. Покинуть страницу?',
  title = 'Несохранённые изменения',
  confirmLabel = 'Покинуть',
  cancelLabel = 'Остаться',
} = {}) {
  function shouldBlock() {
    return resolveFlag(enabled) && resolveFlag(isDirty)
  }

  async function confirmLeave() {
    if (!shouldBlock()) return true
    const confirm = useConfirmStore()
    return confirm.ask({
      title,
      message,
      confirmLabel,
      cancelLabel,
      danger: false,
    })
  }

  function handleBeforeUnload(event) {
    if (!shouldBlock()) return
    event.preventDefault()
    event.returnValue = message
  }

  onMounted(() => {
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', handleBeforeUnload)
    }
  })

  onBeforeUnmount(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  })

  onBeforeRouteLeave(async () => {
    if (!shouldBlock()) return true
    return confirmLeave()
  })

  return {
    confirmLeave,
  }
}
