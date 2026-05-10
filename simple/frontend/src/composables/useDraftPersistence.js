import { watch } from 'vue'

function getStorage() {
  if (typeof window === 'undefined') return null
  return window.sessionStorage
}

function parseDraft(raw) {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function useDraftPersistence({
  key,
  enabled = () => true,
  getData,
  applyData,
  isEmpty = () => false,
  onRestored = null,
} = {}) {
  let restoredForSession = false

  function isEnabled() {
    return typeof enabled === 'function' ? !!enabled() : !!enabled
  }

  function restoreDraft() {
    if (!key || !isEnabled()) return false
    const storage = getStorage()
    if (!storage) return false
    const parsed = parseDraft(storage.getItem(key))
    if (!parsed) return false
    applyData(parsed)
    restoredForSession = true
    if (typeof onRestored === 'function') {
      onRestored(parsed)
    }
    return true
  }

  function clearDraft() {
    const storage = getStorage()
    if (!storage || !key) return
    storage.removeItem(key)
    restoredForSession = false
  }

  watch(
    () => isEnabled(),
    (active) => {
      if (!active || restoredForSession) return
      restoreDraft()
    },
    { immediate: true },
  )

  watch(
    () => {
      if (!key || !isEnabled()) return ''
      const data = getData()
      if (!data || isEmpty(data)) return ''
      return JSON.stringify(data)
    },
    (serialized) => {
      const storage = getStorage()
      if (!storage || !key) return
      if (!serialized) {
        storage.removeItem(key)
        return
      }
      storage.setItem(key, serialized)
    },
  )

  return {
    clearDraft,
    restoreDraft,
  }
}
