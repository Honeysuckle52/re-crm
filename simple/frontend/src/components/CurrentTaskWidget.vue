<template>
  <template v-if="auth.isStaff">
    <div class="ctw-shell" :class="{ 'is-embedded': embedded }">
      <button
        v-if="embedded || mode === 'hidden'"
        class="ctw-trigger"
        :class="triggerClass"
        :title="triggerTitle"
        aria-label="Открыть виджет текущей задачи"
        :aria-expanded="embedded ? String(mode !== 'hidden') : undefined"
        @click="toggleTrigger"
      >
        <span class="ctw-trigger__dot" :class="dotClass" aria-hidden="true"></span>
        <span class="ctw-trigger__label">Текущая задача</span>
        <span class="ctw-trigger__count">{{ inProgressTasksLabel }}</span>
      </button>

      <Teleport to="body" :disabled="!shouldTeleport">
        <Transition name="ctw-pop">
          <aside
            v-if="mode !== 'hidden'"
            class="ctw"
            :class="widgetClass"
            aria-label="Текущая задача сотрудника"
          >
            <div class="ctw__head">
              <button
                class="ctw__head-main"
                :aria-expanded="mode === 'expanded'"
                @click="toggleExpanded"
              >
                <span class="ctw__dot" :class="dotClass" aria-hidden="true"></span>
                <span class="ctw__label">
                  <b>Текущая задача</b>
                  <span v-if="task" class="ctw__subtle">{{ task.title }}</span>
                  <span v-else-if="hasCurrentTaskMismatch" class="ctw__subtle">
                    идет обновление карточки
                  </span>
                  <span v-else class="ctw__subtle">не выбрана</span>
                </span>
                <span class="ctw__counters" :title="countersTooltip">
                  <span class="ctw__pill">{{ inProgressTasksLabel }}</span>
                  <span class="ctw__pill">{{ wl.activeRequestsLabel }}</span>
                </span>
                <span class="ctw__chevron" aria-hidden="true">
                  {{ mode === 'expanded' ? '▾' : '▴' }}
                </span>
              </button>
              <button
                class="ctw__close"
                aria-label="Скрыть виджет"
                title="Скрыть"
                @click.stop="setMode('hidden')"
              >×</button>
            </div>

            <Transition name="ctw-body">
              <div v-if="mode === 'expanded'" class="ctw__body">
                <template v-if="task">
                  <div class="ctw__tags">
                    <span class="ctw__tag" :class="priorityClass(task.priority)">
                      {{ priorityLabel(task.priority) }}
                    </span>
                    <span class="ctw__tag ctw__tag--accent">{{ task.status_name }}</span>
                    <span v-if="task.is_overdue" class="ctw__tag ctw__tag--danger">
                      просрочено
                    </span>
                  </div>

                  <dl class="ctw__meta">
                    <template v-if="task.client_username">
                      <dt>Клиент</dt>
                      <dd>{{ task.client_username }}</dd>
                    </template>
                    <template v-if="task.property_title">
                      <dt>Объект</dt>
                      <dd>{{ task.property_title }}</dd>
                    </template>
                    <template v-if="task.due_date">
                      <dt>Срок</dt>
                      <dd>{{ formatDate(task.due_date) }}</dd>
                    </template>
                  </dl>

                  <div class="ctw__actions">
                    <router-link
                      :to="{ name: 'task-workflow', params: { id: task.id } }"
                      class="ctw__btn ctw__btn--primary"
                    >
                      Открыть задачу
                    </router-link>
                    <router-link
                      v-if="task.request"
                      :to="`/requests/${task.request}`"
                      class="ctw__btn"
                    >
                      Заявка №{{ task.request }}
                    </router-link>
                    <button class="ctw__btn" :disabled="busy" @click="pause">
                      Пауза
                    </button>
                    <button
                      class="ctw__btn ctw__btn--accent"
                      :disabled="busy"
                      @click="complete"
                    >
                      Завершить
                    </button>
                  </div>
                </template>

                <div v-else-if="hasCurrentTaskMismatch" class="ctw__empty">
                  <span>Есть задача в работе. Обновите виджет.</span>
                  <button
                    class="ctw__btn ctw__btn--primary"
                    :disabled="busy || wl.loading"
                    @click="refreshWidget"
                  >
                    Обновить
                  </button>
                </div>

                <div v-else class="ctw__empty">
                  <span>У вас нет задачи «В работе».</span>
                  <router-link to="/tasks" class="ctw__btn ctw__btn--primary">
                    Взять задачу
                  </router-link>
                </div>

                <div v-if="workloadLimitMessage" class="ctw__warn">
                  {{ workloadLimitMessage }}
                </div>
              </div>
            </Transition>
          </aside>
        </Transition>
      </Teleport>
    </div>
  </template>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { useToastsStore } from '../store/toasts'
import { pauseTask, completeTask } from '../api/tasks'
import { formatDateShort as formatDate } from '@/utils/formatters'
import { useVisibilityRefresh } from '@/composables/useVisibilityRefresh'

const props = defineProps({
  embedded: {
    type: Boolean,
    default: false,
  },
})

const auth = useAuthStore()
const wl = useWorkloadStore()
const toasts = useToastsStore()
const busy = ref(false)

useVisibilityRefresh({
  enabled: () => auth.isStaff,
  interval: 30_000,
  onRefresh: () => wl.refresh(),
})

const STORAGE_KEY = 'ctw.mode'
const mode = ref(loadMode())

function loadMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'hidden' || saved === 'summary' || saved === 'expanded') {
      return saved
    }
  } catch (_err) {}
  return props.embedded ? 'hidden' : 'expanded'
}

function setMode(next) {
  mode.value = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch (_err) {}
}

function toggleExpanded() {
  setMode(mode.value === 'expanded' ? 'summary' : 'expanded')
}

function toggleTrigger() {
  if (mode.value === 'hidden') {
    setMode('expanded')
    return
  }
  setMode('hidden')
}

const task = computed(() => wl.currentTask)
const isOverdue = computed(() => !!task.value?.is_overdue)
const hasCurrentTaskMismatch = computed(
  () => !task.value && (wl.workload.in_progress_tasks || 0) > 0,
)
const shouldTeleport = computed(
  () => props.embedded,
)

const dotClass = computed(() => {
  if (!task.value && hasCurrentTaskMismatch.value) return 'is-syncing'
  if (!task.value) return 'is-idle'
  if (isOverdue.value) return 'is-overdue'
  return 'is-active'
})

const triggerClass = computed(() => ({
  'is-overloaded': wl.isOverloaded,
  'is-overdue': isOverdue.value,
  'is-open': props.embedded && mode.value !== 'hidden',
}))

const widgetClass = computed(() => ({
  'is-overloaded': wl.isOverloaded,
  'is-empty': !task.value,
  'is-summary': mode.value === 'summary',
  'is-expanded': mode.value === 'expanded',
  'is-embedded': props.embedded,
  'is-floating': shouldTeleport.value,
}))

const inProgressTasksLabel = computed(
  () => `${wl.workload.in_progress_tasks} / ${wl.workload.max_in_progress_tasks}`,
)

const countersTooltip = computed(
  () => `В работе: ${inProgressTasksLabel.value}, `
    + `активные задачи: ${wl.activeTasksLabel}, `
    + `заявки: ${wl.activeRequestsLabel}`,
)

const workloadLimitMessage = computed(() => {
  const workload = wl.workload
  if (workload.in_progress_tasks >= workload.max_in_progress_tasks) {
    return `В работе ${workload.in_progress_tasks}/${workload.max_in_progress_tasks}. `
      + 'Сначала завершите текущую задачу или поставьте ее на паузу.'
  }
  if (
    workload.active_requests >= workload.max_active_requests
    && workload.active_tasks >= workload.max_active_tasks
  ) {
    return 'Исчерпаны лимиты по задачам и заявкам.'
  }
  if (workload.active_requests >= workload.max_active_requests) {
    return `Заявок ${workload.active_requests}/${workload.max_active_requests} — лимит.`
  }
  if (workload.active_tasks >= workload.max_active_tasks) {
    return `Активных задач ${workload.active_tasks}/${workload.max_active_tasks} — лимит.`
  }
  return ''
})

const triggerTitle = computed(() => {
  if (task.value) return `Текущая задача: ${task.value.title}`
  if (hasCurrentTaskMismatch.value) return 'Есть задача в работе, идет обновление'
  return 'Нет задачи в работе'
})

function priorityLabel(priority) {
  return ({ low: 'Низкий', normal: 'Обычный', high: 'Высокий' })[priority] || priority
}

function priorityClass(priority) {
  if (priority === 'high') return 'ctw__tag--danger'
  if (priority === 'low') return 'ctw__tag--muted'
  return ''
}

async function refreshWidget() {
  await wl.refresh()
}

async function pause() {
  if (!task.value) return
  const id = task.value.id
  const previousTask = wl.currentTask ? { ...wl.currentTask } : null
  const previousWorkload = { ...wl.workload }
  busy.value = true
  wl.optimisticPauseTask(id)
  const { ok, error } = await pauseTask(id, { bump: false })
  if (!ok) {
    wl.$patch({
      currentTask: previousTask,
      workload: previousWorkload,
    })
  }
  await wl.refresh()
  if (!ok) {
    toasts.error(error || 'Не удалось приостановить задачу')
  }
  busy.value = false
}

async function complete() {
  if (!task.value) return
  const id = task.value.id
  const previousTask = wl.currentTask ? { ...wl.currentTask } : null
  const previousWorkload = { ...wl.workload }
  busy.value = true
  wl.optimisticCompleteTask(id)
  const { ok, error } = await completeTask(id, {}, { bump: false })
  if (!ok) {
    wl.$patch({
      currentTask: previousTask,
      workload: previousWorkload,
    })
  }
  await wl.refresh()
  if (!ok) {
    toasts.error(error || 'Не удалось завершить задачу')
  }
  busy.value = false
}

watch(
  () => auth.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated && auth.isStaff) {
      wl.refresh()
    } else {
      wl.reset()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.ctw-shell {
  display: flex;
  justify-content: flex-end;
  width: min(420px, 100%);
  min-width: 0;
  margin-left: auto;
  overflow: visible;
}

.ctw-shell.is-embedded {
  width: 100%;
  flex: 0 0 auto;
  min-height: 42px;
}

.ctw,
.ctw-trigger {
  position: static;
  width: auto;
}

.ctw-trigger {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  color: var(--c-text);
  font: inherit;
  cursor: pointer;
  box-shadow: var(--shadow-1);
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease,
    background 0.25s ease;
}

.ctw-shell.is-embedded .ctw-trigger {
  width: 100%;
  min-height: 42px;
  justify-content: space-between;
}

.ctw-trigger:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 26px rgba(10, 34, 33, 0.16);
}

.ctw-trigger.is-open {
  border-color: rgba(120, 216, 206, 0.34);
  box-shadow: 0 16px 30px rgba(4, 24, 22, 0.18);
}

.ctw-trigger.is-overloaded,
.ctw-trigger.is-overdue {
  border-color: rgba(255, 111, 134, 0.3);
}

.ctw-trigger__dot,
.ctw__dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--c-text-muted);
}

.ctw-trigger__dot.is-active,
.ctw__dot.is-active {
  background: var(--c-accent-2);
  box-shadow: 0 0 0 3px rgba(120, 216, 206, 0.16);
}

.ctw-trigger__dot.is-overdue,
.ctw__dot.is-overdue {
  background: var(--c-danger);
  box-shadow: 0 0 0 3px rgba(255, 111, 134, 0.18);
}

.ctw-trigger__dot.is-syncing,
.ctw__dot.is-syncing {
  background: #f5d26c;
  box-shadow: 0 0 0 3px rgba(245, 210, 108, 0.18);
}

.ctw-trigger__label {
  min-width: 0;
  font-weight: 700;
  white-space: nowrap;
}

.ctw-trigger__count {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(7, 52, 52, 0.82);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
}

.ctw {
  width: min(420px, 100%);
  margin-left: auto;
  color: var(--c-text);
  border-radius: 24px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-1);
  overflow: hidden;
  transform-origin: right bottom;
}

.ctw.is-summary {
  width: min(320px, 100%);
}

.ctw.is-floating {
  position: fixed;
  right: clamp(16px, 2vw, 28px);
  bottom: 24px;
  width: min(380px, calc(100vw - 32px));
  margin-left: 0;
  z-index: 70;
  box-shadow: 0 22px 44px rgba(4, 24, 22, 0.28);
  will-change: transform, opacity;
  transition: box-shadow 0.32s ease, transform 0.32s ease;
}

.ctw.is-floating.is-summary {
  width: min(380px, calc(100vw - 32px));
}

.ctw.is-overloaded {
  border-color: rgba(255, 111, 134, 0.3);
}

.ctw__head {
  display: flex;
  align-items: stretch;
  background: linear-gradient(135deg, rgba(15, 67, 70, 0.98), rgba(9, 53, 52, 0.92));
}

.ctw__head-main {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: transparent;
  color: inherit;
  border: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.ctw__head-main:hover {
  background: rgba(120, 216, 206, 0.08);
}

.ctw__close {
  width: 34px;
  border: none;
  background: transparent;
  color: var(--c-text-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.ctw__close:hover {
  color: var(--c-accent-2);
  background: rgba(120, 216, 206, 0.12);
}

.ctw__label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ctw__label b {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.ctw__subtle {
  overflow: hidden;
  color: var(--c-ink-soft);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.ctw__counters {
  display: inline-flex;
  gap: 4px;
}

.ctw__pill {
  padding: 4px 9px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: rgba(7, 52, 52, 0.88);
  color: var(--c-text);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
}

.ctw__chevron {
  font-size: 10px;
  opacity: 0.75;
}

.ctw__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px 14px;
}

.ctw__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ctw__tag {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(7, 52, 52, 0.88);
  color: var(--c-ink-soft);
  font-size: 12px;
  font-weight: 600;
}

.ctw__tag--accent {
  border-color: rgba(120, 216, 206, 0.2);
  background: rgba(120, 216, 206, 0.12);
  color: #efffff;
}

.ctw__tag--danger {
  border-color: rgba(255, 111, 134, 0.26);
  background: rgba(255, 111, 134, 0.14);
  color: #ffd4dc;
}

.ctw__tag--muted {
  color: var(--c-text-muted);
}

.ctw__meta {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 10px;
  font-size: 14px;
  line-height: 1.35;
}

.ctw__meta dt {
  color: var(--c-text-muted);
  font-weight: 500;
}

.ctw__meta dd {
  margin: 0;
  font-weight: 700;
  color: var(--c-text);
}

.ctw__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ctw__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: linear-gradient(135deg, rgba(27, 77, 62, 0.98), rgba(46, 139, 87, 0.82));
  color: var(--c-text);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}

.ctw__btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.ctw__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ctw__btn--primary,
.ctw__btn--accent {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.12);
}

.ctw__btn--primary {
  background: linear-gradient(135deg, rgba(57, 128, 122, 0.9), rgba(39, 98, 93, 0.88));
}

.ctw__btn--accent {
  background: var(--grad-accent);
}

.ctw__empty {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--c-ink-soft);
}

.ctw__warn {
  padding: 8px 12px;
  border-radius: 16px;
  border: 1px solid rgba(255, 111, 134, 0.22);
  background: rgba(255, 111, 134, 0.12);
  color: #ffd6de;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
}

.ctw-pop-enter-active,
.ctw-pop-leave-active {
  transition:
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.ctw-pop-enter-from,
.ctw-pop-leave-to {
  opacity: 0;
  transform: translate3d(0, 12px, 0) scale(0.985);
}

.ctw-body-enter-active,
.ctw-body-leave-active {
  overflow: hidden;
  transition:
    opacity 0.24s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.ctw-body-enter-from,
.ctw-body-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 900px) {
  .ctw-shell {
    width: min(360px, 100%);
  }
}

@media (max-width: 720px) {
  .ctw-shell:not(.is-embedded),
  .ctw:not(.is-floating),
  .ctw:not(.is-floating).is-summary {
    width: 100%;
  }

  .ctw-shell.is-embedded {
    width: 100%;
  }

  .ctw.is-floating,
  .ctw.is-floating.is-summary {
    right: 10px;
    bottom: 16px;
    width: min(360px, calc(100vw - 20px));
  }

  .ctw__head-main {
    grid-template-columns: auto 1fr;
  }

  .ctw__counters,
  .ctw__chevron {
    grid-column: 2;
    justify-self: start;
  }
}
</style>
