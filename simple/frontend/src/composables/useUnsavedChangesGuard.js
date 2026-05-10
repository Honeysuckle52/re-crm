import { onBeforeUnmount, onMounted, unref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

function resolveFlag(value) {
  if (typeof value === 'function') return !!value()
  return !!unref(value)
}

export function useUnsavedChangesGuard({
  enabled = true,
  isDirty = false,
  message = 'Есть несохранённые изменения. Покинуть страницу?',
} = {}) {
  function shouldBlock() {
    return resolveFlag(enabled) && resolveFlag(isDirty)
  }

  function confirmLeave() {
    if (!shouldBlock()) return true
    return window.confirm(message)
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

  onBeforeRouteLeave(() => confirmLeave())

  return {
    confirmLeave,
  }
}
