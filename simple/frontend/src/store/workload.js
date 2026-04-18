/**
 * Стор «Рабочая нагрузка сотрудника».
 *
 * Отражает два среза состояния, которые приходят с бэка:
 *   - workload — сколько задач/заявок в работе и каковы лимиты
 *     (эндпоинт GET /users/me/workload/);
 *   - currentTask — активная задача сотрудника в статусе `in_progress`
 *     (эндпоинт GET /tasks/current/).
 *
 * Используется виджетом CurrentTaskWidget в TopBar, экранами Tasks,
 * Requests и формой назначения задачи — чтобы единообразно показывать
 * «лимит исчерпан» и не давать превысить правила из business_rules.py.
 */
import { defineStore } from 'pinia'
import api from '../api'

const DEFAULT_WORKLOAD = {
  active_tasks: 0,
  in_progress_tasks: 0,
  active_requests: 0,
  max_active_tasks: 2,
  max_in_progress_tasks: 1,
  max_active_requests: 2,
  can_take_request: true,
  can_take_task: true,
  can_start_task: true,
}

export const useWorkloadStore = defineStore('workload', {
  state: () => ({
    workload: { ...DEFAULT_WORKLOAD },
    currentTask: null,
    loading: false,
    lastSyncAt: null,
  }),
  getters: {
    // Строка формата "1 / 2" для индикатора в TopBar
    activeTasksLabel: (s) =>
      `${s.workload.active_tasks} / ${s.workload.max_active_tasks}`,
    activeRequestsLabel: (s) =>
      `${s.workload.active_requests} / ${s.workload.max_active_requests}`,
    // true, если любой из лимитов на грани (равен или превышен)
    isOverloaded: (s) =>
      s.workload.active_tasks >= s.workload.max_active_tasks
      || s.workload.active_requests >= s.workload.max_active_requests,
    hasCurrentTask: (s) => !!s.currentTask,
  },
  actions: {
    async refresh() {
      this.loading = true
      try {
        const [wl, cur] = await Promise.all([
          api.get('/users/me/workload/'),
          api.get('/tasks/current/'),
        ])
        this.workload = { ...DEFAULT_WORKLOAD, ...(wl.data || {}) }
        this.currentTask = cur.data || null
        this.lastSyncAt = new Date()
      } catch (err) {
        // Молча — виджет не должен блокировать UI при сетевой ошибке.
        // eslint-disable-next-line no-console
        console.warn('[workload] refresh failed', err)
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.workload = { ...DEFAULT_WORKLOAD }
      this.currentTask = null
      this.lastSyncAt = null
    },
  },
})
