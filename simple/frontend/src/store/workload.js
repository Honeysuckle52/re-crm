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

function withDerivedWorkloadFlags(payload = {}) {
  const next = { ...DEFAULT_WORKLOAD, ...(payload || {}) }
  return {
    ...next,
    can_take_request: next.active_requests < next.max_active_requests,
    can_take_task: next.active_tasks < next.max_active_tasks,
    can_start_task: next.in_progress_tasks < next.max_in_progress_tasks,
  }
}

let _bumpTimer = null

export const useWorkloadStore = defineStore('workload', {
  state: () => ({
    workload: { ...DEFAULT_WORKLOAD },
    currentTask: null,
    loading: false,
    lastSyncAt: null,
  }),
  getters: {
    activeTasksLabel: (s) =>
      `${s.workload.active_tasks} / ${s.workload.max_active_tasks}`,
    activeRequestsLabel: (s) =>
      `${s.workload.active_requests} / ${s.workload.max_active_requests}`,
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
        const nextWorkload = withDerivedWorkloadFlags(wl.data)
        let currentTask = cur.data || null

        if (!currentTask && nextWorkload.in_progress_tasks > 0) {
          try {
            const fallback = await api.get('/tasks/', {
              params: {
                assignee: 'me',
                status_code: 'in_progress',
                ordering: '-updated_at',
                page: 1,
                page_size: 1,
              },
            })
            currentTask = fallback.data?.results?.[0] || null
          } catch (_fallbackError) {}
        }

        this.workload = nextWorkload
        this.currentTask = currentTask
        this.lastSyncAt = new Date()
      } catch (err) {
        console.warn('[workload] refresh failed', err)
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.workload = withDerivedWorkloadFlags()
      this.currentTask = null
      this.lastSyncAt = null
    },
    bumpAfterAction({ delayMs = 400 } = {}) {
      if (_bumpTimer) clearTimeout(_bumpTimer)
      _bumpTimer = setTimeout(() => {
        _bumpTimer = null
        this.refresh()
      }, Math.max(0, delayMs))
    },
    optimisticCompleteTask(taskId) {
      if (this.currentTask && this.currentTask.id === taskId) {
        this.currentTask = null
      }
      this.workload = withDerivedWorkloadFlags({
        ...this.workload,
        in_progress_tasks: Math.max(
          0, (this.workload.in_progress_tasks || 0) - 1,
        ),
        active_tasks: Math.max(
          0, (this.workload.active_tasks || 0) - 1,
        ),
      })
    },
    optimisticPauseTask(taskId) {
      if (this.currentTask && this.currentTask.id === taskId) {
        this.currentTask = null
      }
      this.workload = withDerivedWorkloadFlags({
        ...this.workload,
        in_progress_tasks: Math.max(
          0, (this.workload.in_progress_tasks || 0) - 1,
        ),
      })
    },
    optimisticStartTask(task) {
      if (task) this.currentTask = task
      this.workload = withDerivedWorkloadFlags({
        ...this.workload,
        in_progress_tasks: (this.workload.in_progress_tasks || 0) + 1,
      })
    },
  },
})
