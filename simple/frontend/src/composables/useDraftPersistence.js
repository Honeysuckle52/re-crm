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
  function resolveKey() {
    return typeof key === 'function' ? key() : key
  }

  function isEnabled() {
    return typeof enabled === 'function' ? !!enabled() : !!enabled
  }

  function restoreDraft() {
    const resolvedKey = resolveKey()
    if (!resolvedKey || !isEnabled()) return false
    const storage = getStorage()
    if (!storage) return false
    const parsed = parseDraft(storage.getItem(resolvedKey))
    if (!parsed) return false
    applyData(parsed)
    if (typeof onRestored === 'function') {
      onRestored(parsed)
    }
    return true
  }

  function clearDraft() {
    const resolvedKey = resolveKey()
    const storage = getStorage()
    if (!storage || !resolvedKey) return
    storage.removeItem(resolvedKey)
  }

  // Auto-save watcher: writes to sessionStorage whenever form data changes
  watch(
    () => {
      const resolvedKey = resolveKey()
      if (!resolvedKey || !isEnabled()) return ''
      const data = getData()
      if (!data || isEmpty(data)) return ''
      return JSON.stringify(data)
    },
    (serialized) => {
      const resolvedKey = resolveKey()
      const storage = getStorage()
      if (!storage || !resolvedKey) return
      if (!serialized) {
        storage.removeItem(resolvedKey)
        return
      }
      storage.setItem(resolvedKey, serialized)
    },
  )

  return {
    clearDraft,
    restoreDraft,
  }
}
