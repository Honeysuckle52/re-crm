import axios from 'axios'
import { useAuthStore } from '../store/auth'

const api = axios.create({
  baseURL: '/api',
  withCredentials: false,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshing = null
const AUTH_REFRESH_SKIP_PATHS = [
  '/auth/login/',
  '/auth/refresh/',
  '/auth/register/',
  '/auth/verify-email/',
  '/auth/resend-email-code/',
  '/auth/logout/',
  '/auth/verify/',
]

function isAuthEndpoint(config) {
  const url = config?.url || ''
  return AUTH_REFRESH_SKIP_PATHS.some((path) => url.includes(path))
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && original && !original._retry && !isAuthEndpoint(original)) {
      const refresh = localStorage.getItem('refresh')
      if (!refresh) throw error
      original._retry = true
      try {
        refreshing = refreshing || axios.post('/api/auth/refresh/', { refresh })
        const { data } = await refreshing
        refreshing = null
        const auth = useAuthStore()
        localStorage.setItem('access', data.access)
        auth.access = data.access
        if (data.refresh) {
          localStorage.setItem('refresh', data.refresh)
          auth.refresh = data.refresh
        }
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch (e) {
        refreshing = null
        const auth = useAuthStore()
        auth.clearSession()
        window.dispatchEvent(new Event('auth:expired'))
        throw e
      }
    }
    throw error
  }
)

export default api
