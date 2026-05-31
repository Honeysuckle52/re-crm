import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: false,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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
        window.dispatchEvent(new Event('auth:expired'))
        throw e
      }
    }
    throw error
  }
)

export default api
