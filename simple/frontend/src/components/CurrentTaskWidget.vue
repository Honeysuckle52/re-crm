<template>
  <aside v-if="auth.isStaff" class="ctw" :class="widgetClass">
    <!-- Компактная «шапка» в один ряд: индикатор + название + счётчики + свернуть.
         При collapsed показываем только шапку (FAB-подобный вид). -->
    <button class="ctw__head" :aria-expanded="!collapsed"
            @click="collapsed = !collapsed">
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
        {{ collapsed ? '▲' : '▼' }}
      </span>
    </button>

    <!-- Раскрывающееся тело. -->
    <div v-if="!collapsed" class="ctw__body">
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
          <router-link v-if="task.request"
                       :to="`/requests/${task.request}`"
                       class="ctw__btn ctw__btn--primary">
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

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import api from '../api'

const auth = useAuthStore()
const wl = useWorkloadStore()
const busy = ref(false)
// Пользователь может свернуть/развернуть карточку. По умолчанию — развёрнута.
const collapsed = ref(false)

const task = computed(() => wl.currentTask)

const dotClass = computed(() => {
  if (!task.value) return 'is-idle'
  if (task.value.is_overdue) return 'is-overdue'
  return 'is-active'
})

const widgetClass = computed(() => ({
  'is-overloaded': wl.isOverloaded,
  'is-empty': !task.value,
  'is-collapsed': collapsed.value,
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

function formatDate (s) {
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}
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

watch(() => auth.isAuthenticated, (v) => {
  if (v && auth.isStaff) wl.refresh()
  else wl.reset()
}, { immediate: false })

onMounted(() => { if (auth.isStaff) wl.refresh() })
</script>

<style scoped>
/* Плавающая карточка в правом нижнем углу. Фиксированная ширина,
   не растягивается во всю строку, не мешает футеру (который теперь
   обычный flex-child внизу документа). */
.ctw {
  position: fixed;
  right: 20px; bottom: 20px;
  width: min(360px, calc(100vw - 32px));
  z-index: 60;
  background: #ffffff;
  color: #1e2a28;
  border-radius: 14px;
  border: 1px solid #e3e9e7;
  box-shadow: 0 14px 32px rgba(16, 24, 23, .18),
              0 2px 6px rgba(16, 24, 23, .06);
  overflow: hidden;
  font-size: 13px;
}
.ctw.is-overloaded { border-color: #e7b7b1; }

/* ---- Шапка-кликабельная ---- */
.ctw__head {
  width: 100%;
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #0f3a33;      /* фирменный тёмно-зелёный */
  color: #fff;
  border: none; cursor: pointer; text-align: left;
  font: inherit;
}
.ctw__head:hover { background: #134a41; }

.ctw__dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #8aa5a0; flex-shrink: 0;
}
.ctw__dot.is-active  { background: #3ddbc7; box-shadow: 0 0 0 3px rgba(61,219,199,.25); }
.ctw__dot.is-overdue { background: #ff7a6b; box-shadow: 0 0 0 3px rgba(255,122,107,.22); }
.ctw__dot.is-idle    { background: #8aa5a0; }

.ctw__label {
  display: flex; flex-direction: column; gap: 1px;
  min-width: 0;
}
.ctw__label b { font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }
.ctw__subtle {
  font-size: 13px; font-weight: 500;
  color: rgba(255,255,255,.85);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.ctw__counters { display: inline-flex; gap: 4px; }
.ctw__pill {
  font-size: 11px; font-weight: 700;
  padding: 3px 8px; border-radius: 999px;
  background: rgba(255,255,255,.15); color: #fff;
}
.ctw.is-overloaded .ctw__pill { background: #ff7a6b; color: #fff; }

.ctw__chevron { font-size: 10px; opacity: .75; }

/* ---- Раскрывающееся тело ---- */
.ctw__body {
  padding: 12px 14px 14px;
  display: flex; flex-direction: column; gap: 10px;
  background: #ffffff;
}

.ctw__tags { display: flex; flex-wrap: wrap; gap: 6px; }
.ctw__tag {
  font-size: 11px; font-weight: 600;
  padding: 3px 9px; border-radius: 999px;
  background: #eef4f2; color: #234240;
}
.ctw__tag--accent  { background: #0f3a33; color: #fff; }
.ctw__tag--danger  { background: #fdece9; color: #9a3b32; }
.ctw__tag--muted   { background: #e6e9e8; color: #546664; }

.ctw__meta {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 10px;
  font-size: 13px;
  line-height: 1.35;
}
.ctw__meta dt { color: #6a7a77; font-weight: 500; }
.ctw__meta dd { margin: 0; font-weight: 600; color: #1e2a28; }

.ctw__actions { display: flex; flex-wrap: wrap; gap: 6px; }
.ctw__btn {
  flex: 0 0 auto;
  display: inline-flex; align-items: center; justify-content: center;
  font: inherit; font-size: 12px; font-weight: 600;
  padding: 7px 12px; border-radius: 8px; cursor: pointer;
  border: 1px solid #dce3e1;
  background: #ffffff; color: #1e2a28;
  text-decoration: none;
}
.ctw__btn:hover:not(:disabled) { background: #f3f6f5; }
.ctw__btn:disabled { opacity: .5; cursor: not-allowed; }
.ctw__btn--primary {
  background: #0f3a33; border-color: #0f3a33; color: #fff;
}
.ctw__btn--primary:hover:not(:disabled) { background: #134a41; }
.ctw__btn--accent  {
  background: #1fa39a; border-color: #1fa39a; color: #fff;
}
.ctw__btn--accent:hover:not(:disabled) { background: #188a82; }

.ctw__empty {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap;
  color: #6a7a77;
}

.ctw__warn {
  background: #fdece9; color: #9a3b32;
  padding: 6px 10px; border-radius: 8px;
  font-size: 12px; font-weight: 500;
}

/* На узких экранах — растянуть по ширине. */
@media (max-width: 520px) {
  .ctw {
    left: 12px; right: 12px; bottom: 12px;
    width: auto;
  }
}
</style>
