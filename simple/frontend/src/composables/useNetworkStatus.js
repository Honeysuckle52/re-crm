import { onMounted, onUnmounted, ref } from 'vue'

const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
let subscribers = 0

function syncNetworkStatus() {
  if (typeof navigator === 'undefined') {
    isOnline.value = true
    return
  }
  isOnline.value = navigator.onLine
}

export function useNetworkStatus() {
  onMounted(() => {
    if (typeof window === 'undefined') return
    if (subscribers === 0) {
      window.addEventListener('online', syncNetworkStatus)
      window.addEventListener('offline', syncNetworkStatus)
    }
    subscribers += 1
    syncNetworkStatus()
  })

  onUnmounted(() => {
    if (typeof window === 'undefined') return
    subscribers = Math.max(subscribers - 1, 0)
    if (subscribers === 0) {
      window.removeEventListener('online', syncNetworkStatus)
      window.removeEventListener('offline', syncNetworkStatus)
    }
  })

  return { isOnline }
}
