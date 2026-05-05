import api from '@/api'
import { useWorkloadStore } from '@/store/workload'

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
    const detail = error?.response?.data?.detail
      || error?.response?.data?.non_field_errors?.[0]
      || error?.message
      || 'Не удалось выполнить запрос'
    return { ok: false, data: null, error: detail, raw: error }
  }
}

export function listTasks(params = {}) {
  return call(() => api.get('/tasks/', { params }), { bump: false })
}

export function getTask(id) {
  return call(() => api.get(`/tasks/${id}/`), { bump: false })
}

export function createTask(payload) {
  return call(() => api.post('/tasks/', payload))
}

export function patchTask(id, payload) {
  return call(() => api.patch(`/tasks/${id}/`, payload))
}

export function deleteTask(id) {
  return call(() => api.delete(`/tasks/${id}/`))
}

export function startTask(id) {
  return call(() => api.post(`/tasks/${id}/start/`))
}

export function pauseTask(id) {
  return call(() => api.post(`/tasks/${id}/pause/`))
}

export function changeTaskStatus(id, statusId) {
  return call(() => api.post(`/tasks/${id}/change_status/`, {
    status_id: Number(statusId),
  }))
}

export function completeTask(id, result = {}) {
  return call(() => api.post(`/tasks/${id}/complete/`, { result }))
}

export function recordTaskStep(id, payload) {
  return call(() => api.post(`/tasks/${id}/record_step/`, payload), {
    bump: false,
  })
}

export function takeRequest(id) {
  return call(() => api.post(`/requests/${id}/take/`))
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
