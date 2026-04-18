import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: false,
})

// Интерсептор: подставляем JWT access-токен
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Автоматическое обновление access по refresh при 401
let refreshing = null
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      const refresh = localStorage.getItem('refresh')
      if (!refresh) throw error
      original._retry = true
      try {
        refreshing = refreshing || axios.post('/api/auth/refresh/', { refresh })
        const { data } = await refreshing
        refreshing = null
        localStorage.setItem('access', data.access)
        if (data.refresh) localStorage.setItem('refresh', data.refresh)
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch (e) {
        localStorage.removeItem('access')
        localStorage.removeItem('refresh')
        window.location.href = '/login'
        throw e
      }
    }
    throw error
  }
)

export default api
