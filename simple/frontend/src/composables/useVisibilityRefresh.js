import { onBeforeUnmount, onMounted } from 'vue'

export function useVisibilityRefresh(options) {
  const {
    enabled,
    onRefresh,
    interval = 30_000,
  } = options

  let pollTimer = null

  function refreshIfVisible() {
    if (!document.hidden && enabled()) {
      onRefresh()
    }
  }

  function startPolling() {
    stopPolling()
    pollTimer = window.setInterval(refreshIfVisible, interval)
  }

  function stopPolling() {
    if (pollTimer) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
  }

  onMounted(() => {
    startPolling()
    document.addEventListener('visibilitychange', refreshIfVisible)
  })

  onBeforeUnmount(() => {
    stopPolling()
    document.removeEventListener('visibilitychange', refreshIfVisible)
  })

  return {
    startPolling,
    stopPolling,
    refreshIfVisible,
  }
}
