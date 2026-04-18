<template>
  <aside v-if="auth.isStaff" class="current-task" :class="widgetClass">
    <header class="current-task__head">
      <div class="current-task__title">
        <span class="current-task__dot" :class="dotClass"></span>
        <b>Текущая задача</b>
      </div>
      <div class="current-task__meta">
        <span class="current-task__pill" :title="`Задачи: активных ${wl.activeTasksLabel}`">
          Задачи {{ wl.activeTasksLabel }}
        </span>
        <span class="current-task__pill" :title="`Заявки: в работе ${wl.activeRequestsLabel}`">
          Заявки {{ wl.activeRequestsLabel }}
        </span>
        <button class="current-task__refresh"
                :disabled="wl.loading"
                title="Обновить"
                @click="wl.refresh()">
          <span aria-hidden="true">{{ wl.loading ? '…' : '↻' }}</span>
        </button>
      </div>
    </header>

    <div v-if="task" class="current-task__body">
      <div class="current-task__name">{{ task.title }}</div>
      <div class="current-task__tags">
        <span class="tag" :class="priorityClass(task.priority)">
          {{ priorityLabel(task.priority) }}
        </span>
        <span class="tag tag--accent">{{ task.status_name }}</span>
        <span v-if="task.is_overdue" class="tag tag--danger">просрочено</span>
      </div>
      <div v-if="task.client_username" class="current-task__row">
        <span class="muted">Клиент:</span>
        <b>{{ task.client_username }}</b>
      </div>
      <div v-if="task.property_title" class="current-task__row">
        <span class="muted">Объект:</span>
        <b>{{ task.property_title }}</b>
      </div>
      <div v-if="task.due_date" class="current-task__row">
        <span class="muted">Срок:</span>
        <b>{{ formatDate(task.due_date) }}</b>
      </div>
      <div class="current-task__actions">
        <router-link v-if="task.request"
                     :to="`/requests/${task.request}`"
                     class="btn btn--sm">
          К заявке №{{ task.request }}
        </router-link>
        <router-link to="/tasks" class="btn btn--sm btn--ghost">
          Все задачи
        </router-link>
        <button class="btn btn--sm btn--ghost" :disabled="busy"
                @click="pause">Пауза</button>
        <button class="btn btn--sm btn--accent" :disabled="busy"
                @click="complete">Завершить</button>
      </div>
    </div>

    <div v-else class="current-task__empty">
      <div class="muted">У вас нет задачи «В работе».</div>
      <router-link to="/tasks" class="btn btn--sm">
        Взять задачу
      </router-link>
    </div>

    <div v-if="limitMessage" class="current-task__warn">
      {{ limitMessage }}
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import api from '../api'

const auth = useAuthStore()
const wl = useWorkloadStore()
const busy = ref(false)

const task = computed(() => wl.currentTask)

const dotClass = computed(() => {
  if (!task.value) return 'is-idle'
  if (task.value.is_overdue) return 'is-overdue'
  return 'is-active'
})

const widgetClass = computed(() => ({
  'is-overloaded': wl.isOverloaded,
  'is-empty': !task.value,
}))

const limitMessage = computed(() => {
  const w = wl.workload
  if (w.active_requests >= w.max_active_requests
      && w.active_tasks >= w.max_active_tasks) {
    return `Лимит исчерпан: ${w.active_tasks}/${w.max_active_tasks} задач, `
      + `${w.active_requests}/${w.max_active_requests} заявок. `
      + 'Завершите текущие, чтобы брать новые.'
  }
  if (w.active_requests >= w.max_active_requests) {
    return `Заявок в работе ${w.active_requests}/${w.max_active_requests}. `
      + 'Закройте одну, чтобы взять следующую.'
  }
  if (w.active_tasks >= w.max_active_tasks) {
    return `Задач в работе ${w.active_tasks}/${w.max_active_tasks}. `
      + 'Завершите одну, чтобы добавить новую.'
  }
  return ''
})

function formatDate (s) {
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}
function priorityLabel (p) {
  return ({ low: 'Низкий', normal: 'Обычный', high: 'Высокий' })[p] || p
}
function priorityClass (p) {
  if (p === 'high') return 'tag--danger'
  if (p === 'low') return 'tag--panel'
  return ''
}

async function pause () {
  if (!task.value) return
  busy.value = true
  try {
    await api.post(`/tasks/${task.value.id}/pause/`)
    await wl.refresh()
  } finally { busy.value = false }
}
async function complete () {
  if (!task.value) return
  busy.value = true
  try {
    await api.post(`/tasks/${task.value.id}/complete/`)
    await wl.refresh()
  } finally { busy.value = false }
}

// При логине/выходе — сбрасываем либо тянем свежие данные.
watch(() => auth.isAuthenticated, (v) => {
  if (v && auth.isStaff) wl.refresh()
  else wl.reset()
}, { immediate: false })

onMounted(() => { if (auth.isStaff) wl.refresh() })
</script>

<style scoped>
.current-task {
  position: sticky; top: 12px; z-index: 30;
  margin: 12px 16px 0;
  background: var(--c-panel, #fff);
  border: 1px solid var(--c-border, #e3e9e7);
  border-left: 4px solid var(--c-accent, #1fa39a);
  border-radius: var(--r-sm, 10px);
  padding: 12px 16px;
  box-shadow: var(--shadow-1, 0 1px 2px rgba(16,24,23,.06));
  display: flex; flex-direction: column; gap: 10px;
}
.current-task.is-overloaded { border-left-color: #c2554a; }
.current-task.is-empty { border-left-color: #a0a6a4; }

.current-task__head {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px;
}
.current-task__title {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 14px;
}
.current-task__dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: #a0a6a4; display: inline-block;
}
.current-task__dot.is-active { background: #1fa39a; animation: pulse 1.6s infinite; }
.current-task__dot.is-overdue { background: #c2554a; }
.current-task__dot.is-idle { background: #a0a6a4; }

.current-task__meta {
  display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.current-task__pill {
  background: #f1f5f4; color: #234240;
  padding: 3px 10px; border-radius: 999px; font-size: 12px;
  font-weight: 600;
}
.current-task.is-overloaded .current-task__pill {
  background: #fdece9; color: #9a3b32;
}
.current-task__refresh {
  background: transparent; border: 1px solid transparent;
  border-radius: 6px; width: 26px; height: 26px;
  cursor: pointer; color: #456460;
}
.current-task__refresh:hover:not(:disabled) {
  background: #f1f5f4;
}

.current-task__body {
  display: flex; flex-direction: column; gap: 6px;
}
.current-task__name {
  font-weight: 600; font-size: 15px;
}
.current-task__tags {
  display: inline-flex; gap: 6px; flex-wrap: wrap;
}
.current-task__row { font-size: 13px; }
.current-task__actions {
  display: inline-flex; gap: 6px; flex-wrap: wrap; margin-top: 4px;
}

.current-task__empty {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap;
}
.current-task__warn {
  background: #fdece9; color: #9a3b32;
  padding: 8px 10px; border-radius: 8px; font-size: 12px;
}

@keyframes pulse {
  0%   { box-shadow: 0 0 0 0 rgba(31,163,154,.45); }
  70%  { box-shadow: 0 0 0 8px rgba(31,163,154,0);   }
  100% { box-shadow: 0 0 0 0 rgba(31,163,154,0);     }
}

.tag--danger { background: #fdece9; color: #9a3b32; }
</style>
