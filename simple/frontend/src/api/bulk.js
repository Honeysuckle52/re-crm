import api from '@/api'

function extractBulkError(error, fallback) {
  return error?.response?.data?.detail
    || error?.response?.data?.non_field_errors?.[0]
    || error?.message
    || fallback
}

async function call(fn, fallback) {
  try {
    const response = await fn()
    return { ok: true, data: response.data, error: null }
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: extractBulkError(error, fallback),
      raw: error,
    }
  }
}

export function bulkArchiveProperties(ids) {
  return call(
    () => api.post('/properties/bulk-archive/', { ids }),
    'Не удалось архивировать объекты',
  )
}

export function bulkCloseRequests(ids, outcome) {
  return call(
    () => api.post('/requests/bulk-close/', { ids, outcome }),
    'Не удалось закрыть выбранные заявки',
  )
}

export function bulkTaskAction(ids, action, result = '') {
  const payload = { ids, action }
  if (typeof result === 'string' && result.trim()) {
    payload.result = result.trim()
  }
  return call(
    () => api.post('/tasks/bulk-action/', payload),
    'Не удалось выполнить массовое действие по задачам',
  )
}
