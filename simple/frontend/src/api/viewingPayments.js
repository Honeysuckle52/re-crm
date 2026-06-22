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
  return api.get('/viewing-payments/success/', { params: { payment_id: paymentId } })
    .then((response) => ({
      ok: true,
      data: response.data,
      error: null,
      status: response.status,
    }))
    .catch((error) => {
      const response = error?.response
      if (response?.data?.payment) {
        return {
          ok: true,
          data: response.data,
          error: null,
          status: response.status ?? null,
        }
      }
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
    })
}
