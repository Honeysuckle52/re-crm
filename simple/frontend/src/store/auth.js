import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    access: null,
    refresh: null,
  }),
  getters: {
    isAuthenticated: (s) => !!s.access,
    displayName: (s) => s.user?.email || s.user?.username || 'Гость',
    roleLabel: (s) => {
      if (!s.user) return 'Гость'
      if (s.user.is_superuser && !s.user.role_name) return 'Суперадминистратор'
      return s.user.role_name
        || (s.user.user_type === 'client' ? 'Клиент' : 'Сотрудник')
    },
    isSuperuser: (s) => !!s.user?.is_superuser,
    isEmployee: (s) => s.user?.user_type === 'employee' || !!s.user?.is_superuser,
    isStaff: (s) =>
      s.user?.user_type === 'employee' || !!s.user?.is_superuser,
    isClient: (s) =>
      s.user?.user_type === 'client',
    isAdmin: (s) =>
      !!s.user?.is_superuser || s.user?.role_code === 'admin'
      || !!s.user?.is_admin,
    isModerator: (s) =>
      !!s.user?.is_superuser
      || s.user?.role_code === 'manager'
      || s.user?.role_code === 'moderator'
      || !!s.user?.is_manager,
    isAdminOrManager: (s) =>
      !!s.user?.is_superuser
      || !!s.user?.is_admin
      || !!s.user?.is_manager
      || s.user?.role_code === 'moderator'
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager',
    isManager: (s) =>
      !!s.user?.is_superuser || !!s.user?.is_manager
      || s.user?.role_code === 'moderator'
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager',
    isAdminOrModerator: (s) =>
      !!s.user?.is_superuser
      || !!s.user?.is_admin
      || !!s.user?.is_manager
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager'
      || s.user?.role_code === 'moderator',
    canCreateDealReport: (s) =>
      !!s.user?.is_superuser
      || !!s.user?.is_admin
      || !!s.user?.is_manager
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager'
      || s.user?.role_code === 'moderator',
    canCreateRequestTaskReport: (s) =>
      !!s.user?.is_superuser
      || !!s.user?.is_admin
      || !!s.user?.is_manager
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager'
      || s.user?.role_code === 'moderator',
    canCreatePropertyReport: (s) =>
      !!s.user?.is_superuser
      || !!s.user?.is_admin
      || !!s.user?.is_manager
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager'
      || s.user?.role_code === 'moderator',
  },
  actions: {
    clearSession() {
      this.user = null
      this.access = null
      this.refresh = null
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
    },
    hydrate() {
      this.access = localStorage.getItem('access')
      this.refresh = localStorage.getItem('refresh')
      if (this.access) this.fetchMe().catch(() => this.logout())
    },
    async initialize() {
      this.access = localStorage.getItem('access')
      this.refresh = localStorage.getItem('refresh')
      if (this.access) {
        try {
          await this.fetchMe()
        } catch (_err) {
          await this.logout()
        }
      }
    },
    async login(email, password) {
      const { data } = await api.post('/auth/login/', { email, password })
      this.access = data.access
      this.refresh = data.refresh
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      await this.fetchMe()
    },
    async register(payload) {
      await api.post('/auth/register/', payload)
      await this.login(payload.email, payload.password)
    },
    async fetchMe() {
      const { data } = await api.get('/auth/me/')
      this.user = data
    },
    async logout() {
      const refresh = this.refresh || localStorage.getItem('refresh')
      try {
        if (refresh) {
          await api.post('/auth/logout/', { refresh })
        }
      } catch (_err) {
      } finally {
        this.clearSession()
      }
    },
  },
})
