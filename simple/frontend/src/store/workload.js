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
        this.workload = { ...DEFAULT_WORKLOAD, ...(wl.data || {}) }
        this.currentTask = cur.data || null
        this.lastSyncAt = new Date()
      } catch (err) {
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
      this.workload = {
        ...this.workload,
        in_progress_tasks: Math.max(
          0, (this.workload.in_progress_tasks || 0) - 1,
        ),
        active_tasks: Math.max(
          0, (this.workload.active_tasks || 0) - 1,
        ),
        can_start_task: true,
      }
    },
    optimisticStartTask(task) {
      if (task) this.currentTask = task
      this.workload = {
        ...this.workload,
        in_progress_tasks: (this.workload.in_progress_tasks || 0) + 1,
        can_start_task: false,
      }
    },
  },
})
