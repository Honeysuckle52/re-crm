import { defineStore } from 'pinia'
import api from '../api'
import { useWorkloadStore } from './workload'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    access: null,
    refresh: null,
  }),
  getters: {
    isAuthenticated: (s) => !!s.access,
    displayName: (s) => s.user?.username || 'Гость',
    roleLabel: (s) => {
      if (!s.user) return 'Гость'
      if (s.user.is_superuser && !s.user.role_name) return 'Суперадминистратор'
      return s.user.role_name
        || (s.user.user_type === 'client' ? 'Клиент' : 'Сотрудник')
    },
    // Суперпользователь Django — полный доступ ко всему, включая назначение
    // других администраторов, независимо от role_code и user_type.
    isSuperuser: (s) => !!s.user?.is_superuser,
    // Сотрудник агентства. Суперюзер автоматически считается сотрудником —
    // иначе его бы не пускало к /tasks, /clients, /deals.
    isStaff: (s) =>
      s.user?.user_type === 'employee' || !!s.user?.is_superuser,
    // Администратор: либо is_superuser, либо role.code === 'admin'.
    isAdmin: (s) =>
      !!s.user?.is_superuser || s.user?.role_code === 'admin'
      || !!s.user?.is_admin,
    // Руководитель: администратор или менеджер. Используем серверный флаг
    // is_manager (= is_admin_or_manager в модели), чтобы не копировать
    // логику прав в клиент.
    isManager: (s) =>
      !!s.user?.is_superuser || !!s.user?.is_manager
      || s.user?.role_code === 'admin'
      || s.user?.role_code === 'manager',
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
      // Дополнительно сбрасываем виджет текущей задачи, чтобы после
      // смены аккаунта не оставались счётчики/задача предыдущего юзера.
      // Оборачиваем в try — на самом раннем этапе (до createPinia/мounting)
      // стор может быть недоступен, и это нормально.
      try { useWorkloadStore().reset() } catch (_e) { /* no-op */ }
    },
  },
})
