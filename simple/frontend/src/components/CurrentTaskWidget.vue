<template>
  <template v-if="auth.isStaff">
    <button
      v-if="mode === 'hidden'"
      class="ctw-fab"
      :class="{ 'is-overloaded': wl.isOverloaded, 'is-overdue': isOverdue }"
      :style="floatStyle"
      :title="fabTitle"
      aria-label="Открыть виджет текущей задачи"
      @click="setMode('expanded')"
    >
      <span class="ctw-fab__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round"
             stroke-linejoin="round">
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      </span>
      <span v-if="fabBadge" class="ctw-fab__badge">{{ fabBadge }}</span>
    </button>

    <aside
      v-else
      class="ctw"
      :class="widgetClass"
      :style="floatStyle"
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
            <span v-else class="ctw__subtle">не выбрана</span>
          </span>
          <span class="ctw__counters" :title="countersTitle">
            <span class="ctw__pill">T {{ wl.activeTasksLabel }}</span>
            <span class="ctw__pill">З {{ wl.activeRequestsLabel }}</span>
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
              <dt>Клиент</dt><dd>{{ task.client_username }}</dd>
            </template>
            <template v-if="task.property_title">
              <dt>Объект</dt><dd>{{ task.property_title }}</dd>
            </template>
            <template v-if="task.due_date">
              <dt>Срок</dt><dd>{{ formatDate(task.due_date) }}</dd>
            </template>
          </dl>

          <div class="ctw__actions">
            <router-link :to="{ name: 'task-workflow', params: { id: task.id } }"
                         class="ctw__btn ctw__btn--primary">
              Открыть задачу
            </router-link>
            <router-link v-if="task.request"
                         :to="`/requests/${task.request}`"
                         class="ctw__btn">
              Заявка №{{ task.request }}
            </router-link>
            <button class="ctw__btn" :disabled="busy" @click="pause">
              Пауза
            </button>
            <button class="ctw__btn ctw__btn--accent" :disabled="busy"
                    @click="complete">
              Завершить
            </button>
          </div>
        </template>

        <div v-else class="ctw__empty">
          <span>У вас нет задачи «В работе».</span>
          <router-link to="/tasks" class="ctw__btn ctw__btn--primary">
            Взять задачу
          </router-link>
        </div>

        <div v-if="limitMessage" class="ctw__warn">{{ limitMessage }}</div>
      </div>
    </aside>
  </template>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { pauseTask, completeTask } from '../api/tasks'
import { formatDateShort as formatDate } from '@/utils/formatters'
import { useFloatingFooterOffset } from '@/composables/useFloatingFooterOffset'
import { useVisibilityRefresh } from '@/composables/useVisibilityRefresh'

const auth = useAuthStore()
const wl = useWorkloadStore()
const busy = ref(false)
const { floatStyle } = useFloatingFooterOffset({ baseGap: 20 })

useVisibilityRefresh({
  enabled: () => auth.isStaff,
  interval: 30_000,
  onRefresh: () => wl.refresh(),
})

const STORAGE_KEY = 'ctw.mode'
const mode = ref(loadMode())

function loadMode () {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'hidden' || v === 'summary' || v === 'expanded') return v
  } catch (_e) {}
  return 'expanded'
}
function setMode (next) {
  mode.value = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch (_e) {}
}
function toggleExpanded () {
  setMode(mode.value === 'expanded' ? 'summary' : 'expanded')
}

const task = computed(() => wl.currentTask)
const isOverdue = computed(() => !!task.value?.is_overdue)

const dotClass = computed(() => {
  if (!task.value) return 'is-idle'
  if (isOverdue.value) return 'is-overdue'
  return 'is-active'
})

const widgetClass = computed(() => ({
  'is-overloaded': wl.isOverloaded,
  'is-empty': !task.value,
  'is-summary': mode.value === 'summary',
  'is-expanded': mode.value === 'expanded',
}))

const countersTitle = computed(
  () => `Задачи: ${wl.activeTasksLabel}, заявки: ${wl.activeRequestsLabel}`,
)

const limitMessage = computed(() => {
  const w = wl.workload
  if (w.active_requests >= w.max_active_requests
      && w.active_tasks >= w.max_active_tasks) {
    return 'Лимит исчерпан. Завершите текущие задачи/заявки.'
  }
  if (w.active_requests >= w.max_active_requests) {
    return `Заявок ${w.active_requests}/${w.max_active_requests} — лимит.`
  }
  if (w.active_tasks >= w.max_active_tasks) {
    return `Задач ${w.active_tasks}/${w.max_active_tasks} — лимит.`
  }
  return ''
})

const fabBadge = computed(() => {
  if (isOverdue.value) return '!'
  if (task.value) return '•'
  if (wl.isOverloaded) return '!'
  return ''
})

const fabTitle = computed(() => {
  if (task.value) return `Текущая задача: ${task.value.title}`
  return 'Нет активной задачи'
})

function priorityLabel (p) {
  return ({ low: 'Низкий', normal: 'Обычный', high: 'Высокий' })[p] || p
}
function priorityClass (p) {
  if (p === 'high') return 'ctw__tag--danger'
  if (p === 'low') return 'ctw__tag--muted'
  return ''
}

async function pause () {
  if (!task.value) return
  busy.value = true
  try { await pauseTask(task.value.id) }
  finally { busy.value = false }
}
async function complete () {
  if (!task.value) return
  const id = task.value.id
  busy.value = true
  wl.optimisticCompleteTask(id)
  try { await completeTask(id) }
  finally { busy.value = false }
}
watch(() => auth.isAuthenticated, (v) => {
  if (v && auth.isStaff) wl.refresh()
  else wl.reset()
}, { immediate: true })
</script>

<style scoped>
.ctw,
.ctw-fab {
  position: fixed;
  right: 20px;
  z-index: 60;
}

.ctw-fab {
  width: 56px;
  height: 56px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.16);
  cursor: pointer;
  color: #fff;
  background: var(--grad-accent);
  box-shadow: 0 12px 28px rgba(46, 159, 152, 0.18);
  transition: transform 0.3s ease, box-shadow 0.3s ease, filter 0.3s ease;
}

.ctw-fab:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 30px rgba(46, 159, 152, 0.2);
  filter: saturate(1.08);
}

.ctw-fab.is-overloaded,
.ctw-fab.is-overdue {
  background: linear-gradient(135deg, var(--c-danger), var(--c-danger-2));
  color: #fff;
}

.ctw-fab__icon { display: inline-flex; }

.ctw-fab__badge {
  position: absolute;
  top: 4px;
  right: 2px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(36, 74, 71, 0.94);
  color: var(--c-accent-2);
  border: 1px solid rgba(120, 216, 206, 0.18);
  font-size: 10px;
  font-weight: 800;
  line-height: 16px;
  text-align: center;
  box-shadow: 0 0 0 2px rgba(120, 216, 206, 0.12);
}

.ctw-fab.is-overloaded .ctw-fab__badge,
.ctw-fab.is-overdue .ctw-fab__badge {
  box-shadow: 0 0 0 2px rgba(255, 111, 134, 0.22);
}

.ctw {
  width: min(360px, calc(100vw - 32px));
  color: var(--c-text);
  border-radius: 24px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-glow);
  overflow: hidden;
  font-size: 14px;
  transition: bottom 0.18s ease, box-shadow 0.3s ease;
}

.ctw.is-overloaded {
  border-color: rgba(255, 111, 134, 0.28);
  box-shadow: 0 0 0 1px rgba(255, 111, 134, 0.24),
    0 20px 48px rgba(20, 48, 46, 0.18);
}

.ctw__head {
  display: flex;
  align-items: stretch;
  color: var(--c-text);
  background: linear-gradient(135deg, rgba(15, 67, 70, 0.98), rgba(9, 53, 52, 0.92));
  border-bottom: 1px solid rgba(120, 216, 206, 0.14);
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
  flex: 0 0 auto;
  width: 34px;
  border: none;
  background: transparent;
  color: var(--c-text-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.3s ease, background 0.3s ease;
}

.ctw__close:hover {
  color: var(--c-accent-2);
  background: rgba(120, 216, 206, 0.12);
}

.ctw__dot {
  width: 9px;
  height: 9px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--c-text-muted);
}

.ctw__dot.is-active {
  background: var(--c-accent-2);
  box-shadow: 0 0 0 3px rgba(120, 216, 206, 0.16);
}

.ctw__dot.is-overdue {
  background: var(--c-danger);
  box-shadow: 0 0 0 3px rgba(255, 111, 134, 0.16);
}

.ctw__dot.is-idle {
  background: var(--c-text-muted);
}

.ctw__label {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.ctw__label b {
  font-size: 13px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
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

.ctw.is-overloaded .ctw__pill {
  border-color: rgba(255, 111, 134, 0.2);
  background: rgba(255, 111, 134, 0.14);
  color: #ffd8df;
}

.ctw__chevron {
  font-size: 10px;
  opacity: 0.75;
}

.ctw__body {
  padding: 12px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: transparent;
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
  line-height: 1.25;
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
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: linear-gradient(135deg, rgba(27, 77, 62, 0.98), rgba(46, 139, 87, 0.82));
  color: var(--c-text);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
  white-space: normal;
  text-align: center;
  text-decoration: none;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;
}

.ctw__btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--c-border-strong);
  box-shadow: 0 10px 20px rgba(9, 30, 29, 0.16);
}

.ctw__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ctw__btn--primary {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.12);
  background: linear-gradient(135deg, rgba(57, 128, 122, 0.9), rgba(39, 98, 93, 0.88));
}

.ctw__btn--accent {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.12);
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

@media (max-width: 520px) {
  .ctw {
    left: 12px; right: 12px;
    width: auto;
  }
  .ctw-fab { right: 16px; }
}
</style>
