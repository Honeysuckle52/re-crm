import { defineStore } from 'pinia'
import api from '../api'

// Служебные роли сотрудников
const MANAGER_ROLES = ['администратор', 'менеджер']

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    access: null,
    refresh: null,
  }),
  getters: {
    isAuthenticated: (s) => !!s.access,
    displayName: (s) => s.user?.username || 'Гость',
    roleLabel: (s) => s.user?.role_name
      || (s.user?.user_type === 'client' ? 'Клиент' : 'Сотрудник'),
    // Сотрудник (любой)
    isStaff: (s) => s.user?.user_type === 'employee',
    // Руководящая роль: администратор или менеджер
    isManager: (s) => {
      if (!s.user) return false
      if (s.user.is_superuser) return true
      const role = (s.user.role_name || '').toLowerCase()
      return MANAGER_ROLES.some((r) => role.includes(r))
    },
  },
  actions: {
    hydrate() {
      this.access = localStorage.getItem('access')
      this.refresh = localStorage.getItem('refresh')
      if (this.access) this.fetchMe().catch(() => this.logout())
    },
    async login(username, password) {
      const { data } = await api.post('/auth/login/', { username, password })
      this.access = data.access
      this.refresh = data.refresh
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      await this.fetchMe()
    },
    async register(payload) {
      await api.post('/auth/register/', payload)
      await this.login(payload.username, payload.password)
    },
    async fetchMe() {
      const { data } = await api.get('/auth/me/')
      this.user = data
    },
    logout() {
      this.user = null
      this.access = null
      this.refresh = null
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
    },
  },
})
