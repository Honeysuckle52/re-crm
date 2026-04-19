/**
 * Стор «Рабочая нагрузка сотрудника».
 *
 * Отражает три среза состояния, которые приходят с бэка:
 *   - workload       — сколько задач/заявок в работе и каковы лимиты
 *                      (эндпоинт GET /users/me/workload/);
 *   - currentTask    — активная задача сотрудника в статусе `in_progress`
 *                      (эндпоинт GET /tasks/current/);
 *   - upNext         — очередь из 5 приоритетных задач сотрудника
 *                      (эндпоинт GET /tasks/next_up/).
 *
 * Дополнительно стор:
 *   - держит polling с учётом видимости вкладки (Page Visibility API)
 *     и экспоненциальным backoff при сетевых ошибках;
 *   - экспортирует bumpAfterAction() — вызывается из всех мест, где
 *     мы мутируем задачи (Tasks.vue, RequestDetail.vue, CurrentTaskWidget
 *     и т. д.), чтобы моментально обновить виджет и счётчики;
 *   - инкрементирует `mutationId` — компоненты, подписанные на него,
 *     могут делать повторную загрузку собственных данных.
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
  today: {
    completed_today: 0,
    auto_closed_today: 0,
    overdue_today: 0,
    avg_duration_sec: 0,
  },
}

const POLL_INTERVAL_MS      = 30_000   // штатный интервал
const POLL_MIN_BACKOFF_MS   = 5_000
const POLL_MAX_BACKOFF_MS   = 120_000
const BUMP_DELAYED_REFRESH  = 1_500    // повторный refresh после мутации

// Таймеры — вне реактивного состояния, чтобы Vue не отслеживал их.
let pollTimer = null
let delayedTimer = null
let visibilityHandler = null

export const useWorkloadStore = defineStore('workload', {
  state: () => ({
    workload: { ...DEFAULT_WORKLOAD },
    currentTask: null,
    upNext: [],
    loading: false,
    lastSyncAt: null,
    lastError: null,
    // Счётчики для внешних подписчиков.
    mutationId: 0,
    // Текущая величина backoff (растёт при ошибках, сбрасывается при
    // успехе). Начинаем со штатного интервала.
    _backoff: POLL_INTERVAL_MS,
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
    completedToday: (s) => s.workload.today?.completed_today || 0,
  },
  actions: {
    async refresh () {
      this.loading = true
      try {
        const [wl, cur, up] = await Promise.all([
          api.get('/users/me/workload/'),
          api.get('/tasks/current/'),
          api.get('/tasks/next_up/').catch(() => ({ data: [] })),
        ])
        this.workload = { ...DEFAULT_WORKLOAD, ...(wl.data || {}) }
        if (wl.data?.today) {
          this.workload.today = { ...DEFAULT_WORKLOAD.today, ...wl.data.today }
        }
        this.currentTask = cur.data || null
        this.upNext = Array.isArray(up.data) ? up.data
                     : (up.data?.results || [])
        this.lastSyncAt = new Date()
        this.lastError = null
        // Успех — возвращаем backoff к штатному значению.
        this._backoff = POLL_INTERVAL_MS
      } catch (err) {
        this.lastError = err?.message || 'network error'
        // Экспоненциальный backoff при ошибке.
        this._backoff = Math.min(
          Math.max(this._backoff * 2, POLL_MIN_BACKOFF_MS),
          POLL_MAX_BACKOFF_MS,
        )
        // eslint-disable-next-line no-console
        console.warn('[workload] refresh failed', err)
      } finally {
        this.loading = false
      }
    },

    /**
     * Вызывать после любой мутации задач / заявок. Делает немедленный
     * refresh и ещё один через 1,5 секунды — страховка от гонок с
     * сигналами и фоновой отправкой писем.
     */
    async bumpAfterAction () {
      this.mutationId += 1
      await this.refresh()
      if (delayedTimer) clearTimeout(delayedTimer)
      delayedTimer = setTimeout(() => {
        this.refresh().catch(() => {})
        delayedTimer = null
      }, BUMP_DELAYED_REFRESH)
    },

    // --- Polling lifecycle ------------------------------------------------

    startPolling () {
      if (pollTimer) return
      const schedule = () => {
        if (pollTimer) clearTimeout(pollTimer)
        pollTimer = setTimeout(async () => {
          // Не дёргать API во вкладке-в-фоне.
          if (document.visibilityState === 'visible') {
            await this.refresh()
          }
          schedule()
        }, this._backoff)
      }
      schedule()

      visibilityHandler = () => {
        if (document.visibilityState === 'visible') {
          // Вкладка снова активна — синхронизируемся сразу.
          this.refresh().catch(() => {})
        }
      }
      document.addEventListener('visibilitychange', visibilityHandler)
    },

    stopPolling () {
      if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
      if (delayedTimer) { clearTimeout(delayedTimer); delayedTimer = null }
      if (visibilityHandler) {
        document.removeEventListener('visibilitychange', visibilityHandler)
        visibilityHandler = null
      }
    },

    reset () {
      this.stopPolling()
      this.workload = { ...DEFAULT_WORKLOAD }
      this.currentTask = null
      this.upNext = []
      this.lastSyncAt = null
      this.lastError = null
      this._backoff = POLL_INTERVAL_MS
    },
  },
})
