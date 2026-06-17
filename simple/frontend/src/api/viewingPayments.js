import api from '@/api'

async function call(fn) {
  try {
    const response = await fn()
    return { ok: true, data: response.data, error: null }
  } catch (error) {
    const response = error?.response
    const detail = response?.data?.detail
      || response?.data?.non_field_errors?.[0]
      || error?.message
      || 'Не удалось выполнить запрос'
    return {
      ok: false,
      data: response?.data ?? null,
      error: detail,
      status: response?.status ?? null,
      raw: error,
    }
  }
}

export function initiateViewingPayment(viewingId) {
  return call(() => api.post('/viewing-payments/initiate/', { viewing_id: viewingId }))
}

export function syncViewingPayment(paymentId) {
  return call(() => api.get('/viewing-payments/success/', { params: { payment_id: paymentId } }))
}
