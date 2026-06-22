import api from '@/api'
import { extractError } from '@/store/toasts'
import { useWorkloadStore } from '@/store/workload'

function isHtmlErrorResponse(value) {
  if (typeof value !== 'string') return false
  const normalized = value.trim().toLowerCase()
  return normalized.startsWith('<!doctype html') || normalized.startsWith('<html')
}

function taskRequestFallback(status) {
  if (status === 400) {
    return 'Сервер отклонил запрос до создания задачи. Проверьте адрес CRM и попробуйте ещё раз.'
  }
  if (status && status >= 500) {
    return 'Не удалось обработать задачу из-за ошибки сервера. Попробуйте ещё раз.'
  }
  return 'Не удалось выполнить запрос'
}

function validateShowingPayload(payload) {
  if (payload?.task_type !== 'showing') return ''
  if (!payload?.client) return 'Для задачи на показ нужно выбрать клиента.'
  if (!payload?.property) return 'Для задачи на показ нужно выбрать объект.'
  return ''
}

async function call(fn, opts = {}) {
  const { bump = true, bumpDelayMs = 1500 } = opts
  try {
    const response = await fn()
    if (bump) {
      try {
        const workload = useWorkloadStore()
        workload.bumpAfterAction({ delayMs: bumpDelayMs })
      } catch (_err) {}
    }
    return { ok: true, data: response.data, error: null }
  } catch (error) {
    const response = error?.response
    const responseData = response?.data
    const fallback = taskRequestFallback(response?.status ?? null)
    const detail = isHtmlErrorResponse(responseData)
      ? fallback
      : extractError(error, fallback)
    return {
      ok: false,
      data: responseData ?? null,
      error: detail,
      status: response?.status ?? null,
      code: responseData?.code ?? null,
      raw: error,
    }
  }
}

export function normalizeTaskError(errorText, payload) {
  if (payload?.code === 'max_in_progress_tasks') {
    return payload.detail || 'Нельзя стартовать задачу: превышен лимит задач в работе'
  }
  if (payload?.code === 'max_active_tasks') {
    return payload.detail || 'Нельзя стартовать задачу: превышен лимит активных задач'
  }
  if (payload?.detail) return payload.detail
  return errorText
}

export function listTasks(params = {}) {
  return call(() => api.get('/tasks/', { params }), { bump: false })
}

export function getTask(id) {
  return call(() => api.get(`/tasks/${id}/`), { bump: false })
}

export function createTask(payload) {
  const validationError = validateShowingPayload(payload)
  if (validationError) {
    return Promise.resolve({
      ok: false,
      data: null,
      error: validationError,
      status: 400,
      code: 'showing_validation',
      raw: null,
    })
  }
  return call(() => api.post('/tasks/', payload))
}

export function patchTask(id, payload) {
  const validationError = validateShowingPayload(payload)
  if (validationError) {
    return Promise.resolve({
      ok: false,
      data: null,
      error: validationError,
      status: 400,
      code: 'showing_validation',
      raw: null,
    })
  }
  return call(() => api.patch(`/tasks/${id}/`, payload))
}

export function deleteTask(id) {
  return call(() => api.delete(`/tasks/${id}/`))
}

export function startTask(id, opts = {}) {
  return call(() => api.post(`/tasks/${id}/start/`), opts)
}

export function pauseTask(id, opts = {}) {
  return call(() => api.post(`/tasks/${id}/pause/`), opts)
}

export function changeTaskStatus(id, statusId) {
  return call(() => api.post(`/tasks/${id}/change_status/`, {
    status_id: Number(statusId),
  }))
}

export function completeTask(id, result = {}, opts = {}) {
  return call(() => api.post(`/tasks/${id}/complete/`, { result }), opts)
}

export function recordTaskStep(id, payload) {
  return call(() => api.post(`/tasks/${id}/record_step/`, payload), {
    bump: false,
  })
}

export function scheduleTaskViewing(id, payload) {
  return call(() => api.post(`/tasks/${id}/schedule_viewing/`, payload), {
    bump: false,
  })
}

export function initiateTaskViewingPayment(id) {
  return call(() => api.post(`/tasks/${id}/initiate_viewing_payment/`), {
    bump: false,
  })
}

export function initiateViewingPayment(id) {
  return initiateTaskViewingPayment(id)
}

export function takeRequest(id) {
  return call(() => api.post(`/requests/${id}/take/`))
}

export function closeRequest(id, outcome) {
  return call(() => api.post(`/requests/${id}/close/`, { outcome }))
}

export function acceptRequestMatch(requestId, matchId) {
  return call(() => api.post(`/requests/${requestId}/accept_match/`, {
    match_id: matchId,
  }))
}

export function listOutgoingEmails(params = {}) {
  return call(() => api.get('/outgoing-emails/', { params }), { bump: false })
}

export function retryOutgoingEmail(id) {
  return call(() => api.post(`/outgoing-emails/${id}/retry/`), { bump: false })
}
