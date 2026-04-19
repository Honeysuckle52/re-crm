<!--
  Виджет «Текущая задача» в правом нижнем углу.

  Три режима, сохраняемые в localStorage (ключ `ctw.mode`):
    - expanded  — полноценная карточка (~440 px) с задачей, связанными
                  сущностями, прогресс-барами лимитов и KPI «сегодня»;
    - collapsed — компактная полоска 360 × 56 px: индикатор, заголовок,
                  счётчики T x/y · З x/y, быстрые Пауза/Завершить;
    - mini      — FAB 56 × 56 px в углу (статус-точка + бейдж-счётчик).

  Правила:
    * на десктопе по умолчанию `collapsed`, на мобильном — `mini`;
    * переключение между вкладками синхронизируется через событие
      `storage`;
    * в `expanded` виджет резервирует нижний отступ документа через
      CSS-переменную `--ctw-reserved-space`, чтобы не перекрывать
      футер и таблицы (основная жалоба «кривое отображение» была
      именно из-за этого);
    * все действия идут через модуль `api/tasks.js` — он сам обновляет
      workload-стор через `bumpAfterAction()`, поэтому данные в
      виджете и на остальных экранах больше не рассинхронизируются.
-->
<template>
  <!-- FAB-режим: маленькая круглая кнопка -->
  <button
    v-if="mode === 'mini'"
    type="button"
    class="ctw-fab"
    :class="statusClass"
    :aria-label="miniAria"
    :title="miniAria"
    @click="setMode('expanded')"
  >
    <span class="ctw-fab__icon" aria-hidden="true">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 11l3 3L22 4"></path>
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
      </svg>
    </span>
    <span v-if="badgeCount > 0" class="ctw-fab__badge">{{ badgeCount }}</span>
  </button>

  <!-- collapsed / expanded: карточка -->
  <section
    v-else
    class="ctw-card"
    :class="[modeClass, statusClass, { 'is-overloaded': wl.isOverloaded }]"
    role="region"
    aria-label="Текущая задача и загрузка"
  >
    <header class="ctw-head" @click="toggleCollapsed">
      <span class="ctw-dot" aria-hidden="true"></span>
      <span class="ctw-head__title" :title="headTitle">{{ headTitle }}</span>
      <span v-if="limitsLabel"
            class="ctw-head__limits"
            :title="`Задачи ${wl.activeTasksLabel}, заявки ${wl.activeRequestsLabel}`">
        {{ limitsLabel }}
      </span>
      <div class="ctw-head__controls" @click.stop>
        <button
          class="ctw-icon-btn"
          type="button"
          :aria-label="mode === 'expanded' ? 'Свернуть' : 'Развернуть'"
          :title="mode === 'expanded' ? 'Свернуть' : 'Развернуть'"
          @click="toggleCollapsed"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <path v-if="mode === 'expanded'" d="M6 9l6 6 6-6"></path>
            <path v-else d="M18 15l-6-6-6 6"></path>
          </svg>
        </button>
        <button
          class="ctw-icon-btn"
          type="button"
          aria-label="Свернуть в мини-кнопку"
          title="Свернуть в мини-кнопку"
          @click="setMode('mini')"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 14h-6v6"></path>
            <path d="M4 10h6V4"></path>
            <path d="M14 14l7 7"></path>
            <path d="M10 10L3 3"></path>
          </svg>
        </button>
      </div>
    </header>

    <div v-if="mode === 'expanded'" class="ctw-body">
      <!-- 1. Сейчас в работе -->
      <div v-if="task" class="ctw-section">
        <h4 class="ctw-section__title">Сейчас в работе</h4>
        <div class="ctw-task__title">{{ task.title }}</div>

        <div class="ctw-tags">
          <span v-if="task.kind_display" class="ctw-tag">
            {{ task.kind_display }}
          </span>
          <span class="ctw-tag ctw-tag--priority" :class="priorityClass(task.priority)">
            {{ priorityLabel(task.priority) }}
          </span>
          <span v-if="task.is_overdue" class="ctw-tag ctw-tag--danger">
            просрочено
          </span>
          <span v-if="task.is_auto_closed" class="ctw-tag ctw-tag--muted"
                title="Закрывается автоматически по событию">
            авто-закрытие
          </span>
        </div>

        <p v-if="task.description" class="ctw-desc">{{ task.description }}</p>

        <dl class="ctw-meta">
          <template v-if="task.due_date">
            <dt>Срок</dt>
            <dd :class="{ 'is-overdue': task.is_overdue }">
              {{ formatDate(task.due_date) }}
            </dd>
          </template>
          <template v-if="task.client_username">
            <dt>Клиент</dt><dd>{{ task.client_username }}</dd>
          </template>
          <template v-if="task.property_title">
            <dt>Объект</dt><dd>{{ task.property_title }}</dd>
          </template>
        </dl>

        <div v-if="relatedLinks.length" class="ctw-links">
          <router-link
            v-for="link in relatedLinks" :key="link.key"
            :to="link.to"
            class="ctw-link"
          >{{ link.label }}</router-link>
        </div>

        <div class="ctw-actions">
          <button class="ctw-btn" :disabled="busy" type="button" @click="onPause">
            Пауза
          </button>
          <button class="ctw-btn ctw-btn--primary" :disabled="busy"
                  type="button" @click="onComplete">
            Завершить
          </button>
        </div>
      </div>

      <div v-else class="ctw-section">
        <h4 class="ctw-section__title">Сейчас</h4>
        <p class="ctw-empty">{{ emptyHint }}</p>
        <div v-if="wl.upNext.length" class="ctw-next">
          <button
            v-for="t in wl.upNext.slice(0, 3)"
            :key="t.id"
            type="button"
            class="ctw-next__row"
            :disabled="busy || !canStart"
            :title="canStart ? 'Начать выполнение задачи' : 'Лимит задач в работе исчерпан'"
            @click="onStart(t.id)"
          >
            <span class="ctw-next__title">{{ t.title }}</span>
            <span v-if="t.kind_display" class="ctw-next__kind">
              {{ t.kind_display }}
            </span>
          </button>
        </div>
      </div>

      <!-- 2. Лимиты -->
      <div class="ctw-section">
        <h4 class="ctw-section__title">Нагрузка</h4>
        <div class="ctw-bars">
          <div class="ctw-bar">
            <div class="ctw-bar__label">
              <span>Задачи</span>
              <span>{{ wl.workload.active_tasks }} / {{ wl.workload.max_active_tasks }}</span>
            </div>
            <div class="ctw-bar__track">
              <div class="ctw-bar__fill"
                   :style="{ width: pct(wl.workload.active_tasks, wl.workload.max_active_tasks) }"
                   :class="barClass(wl.workload.active_tasks, wl.workload.max_active_tasks)"></div>
            </div>
          </div>
          <div class="ctw-bar">
            <div class="ctw-bar__label">
              <span>В работе</span>
              <span>{{ wl.workload.in_progress_tasks }} / {{ wl.workload.max_in_progress_tasks }}</span>
            </div>
            <div class="ctw-bar__track">
              <div class="ctw-bar__fill"
                   :style="{ width: pct(wl.workload.in_progress_tasks, wl.workload.max_in_progress_tasks) }"
                   :class="barClass(wl.workload.in_progress_tasks, wl.workload.max_in_progress_tasks)"></div>
            </div>
          </div>
          <div class="ctw-bar">
            <div class="ctw-bar__label">
              <span>Заявки</span>
              <span>{{ wl.workload.active_requests }} / {{ wl.workload.max_active_requests }}</span>
            </div>
            <div class="ctw-bar__track">
              <div class="ctw-bar__fill"
                   :style="{ width: pct(wl.workload.active_requests, wl.workload.max_active_requests) }"
                   :class="barClass(wl.workload.active_requests, wl.workload.max_active_requests)"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. KPI «сегодня» -->
      <div v-if="hasTodayStats" class="ctw-section">
        <h4 class="ctw-section__title">Сегодня</h4>
        <ul class="ctw-kpi">
          <li>
            <strong>{{ today.completed_today || 0 }}</strong>
            <span>выполнено</span>
          </li>
          <li v-if="today.auto_closed_today">
            <strong>{{ today.auto_closed_today }}</strong>
            <span>автоматически</span>
          </li>
          <li v-if="today.overdue_today">
            <strong>{{ today.overdue_today }}</strong>
            <span>просрочено</span>
          </li>
          <li v-if="today.avg_duration_sec">
            <strong>{{ formatDuration(today.avg_duration_sec) }}</strong>
            <span>среднее время</span>
          </li>
        </ul>
      </div>

      <div v-if="limitMessage" class="ctw-warn" role="status">
        {{ limitMessage }}
      </div>
      <div v-if="errorMessage" class="ctw-error" role="alert">
        {{ errorMessage }}
      </div>
    </div>

    <!-- collapsed-режим: быстрые действия одной строкой -->
    <footer v-else-if="task" class="ctw-quick" @click.stop>
      <button class="ctw-btn ctw-btn--sm" :disabled="busy" type="button"
              @click="onPause">Пауза</button>
      <button class="ctw-btn ctw-btn--sm ctw-btn--primary" :disabled="busy"
              type="button" @click="onComplete">Завершить</button>
    </footer>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { useToasts } from '../store/toasts'
import { pauseTask, startTask, completeTask } from '../api/tasks'

const auth = useAuthStore()
const wl = useWorkloadStore()
const toasts = useToasts()

const task = computed(() => wl.currentTask)
const today = computed(() => wl.workload.today || {})
const hasTodayStats = computed(() =>
  today.value
  && (today.value.completed_today
      || today.value.auto_closed_today
      || today.value.overdue_today
      || today.value.avg_duration_sec),
)

const busy = ref(false)
const errorMessage = ref('')

// --- persist режима --------------------------------------------------------
const STORAGE_KEY = 'ctw.mode'

const isMobileViewport = () =>
  typeof window !== 'undefined'
  && window.matchMedia?.('(max-width: 720px)').matches

function loadPersistedMode() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'mini' || saved === 'collapsed' || saved === 'expanded') {
      return saved
    }
  } catch (_) { /* ignore */ }
  return isMobileViewport() ? 'mini' : 'collapsed'
}

const mode = ref(loadPersistedMode())

watch(mode, (value) => {
  try { window.localStorage.setItem(STORAGE_KEY, value) } catch (_) {}
  applyReservedSpace()
})

function setMode(next) { mode.value = next }
function toggleCollapsed() {
  mode.value = mode.value === 'expanded' ? 'collapsed' : 'expanded'
}

function onStorage(event) {
  if (event.key !== STORAGE_KEY || !event.newValue) return
  if (event.newValue !== mode.value) mode.value = event.newValue
}

function applyReservedSpace() {
  if (typeof document === 'undefined') return
  // В expanded-режиме резервируем нижний отступ у документа, чтобы футер
  // и таблицы не перекрывались карточкой виджета.
  const px = mode.value === 'expanded' ? '120px' : '0px'
  document.documentElement.style.setProperty('--ctw-reserved-space', px)
}

// --- derived UI ------------------------------------------------------------
const statusClass = computed(() => {
  if (task.value) return 'is-busy'
  if (!canStart.value) return 'is-blocked'
  return 'is-idle'
})
const modeClass = computed(() => `is-${mode.value}`)

const canStart = computed(() => Boolean(wl.workload.can_start_task))
const canTakeTask = computed(() => Boolean(wl.workload.can_take_task))

const badgeCount = computed(() =>
  (wl.workload.active_tasks || 0) + (wl.workload.active_requests || 0),
)

const headTitle = computed(() => {
  if (task.value) return task.value.title
  if (wl.upNext.length) return 'Следующая задача готова к старту'
  return 'Нет задачи в работе'
})

const limitsLabel = computed(() => {
  const w = wl.workload
  if (!w) return ''
  return `T ${w.active_tasks}/${w.max_active_tasks} · З ${w.active_requests}/${w.max_active_requests}`
})

const miniAria = computed(() =>
  task.value
    ? `Текущая задача: ${task.value.title}`
    : `Нагрузка: задач ${wl.activeTasksLabel}, заявок ${wl.activeRequestsLabel}`,
)

const emptyHint = computed(() => {
  if (!canStart.value) return 'Лимит задач «В работе» исчерпан — завершите текущую.'
  if (wl.upNext.length) return 'Выберите задачу, чтобы начать выполнение:'
  if (!canTakeTask.value) return 'Нет активных задач, взять новые пока нельзя.'
  return 'Активных задач нет. Загляните в список задач, чтобы взять новую.'
})

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

const relatedLinks = computed(() => {
  if (!task.value) return []
  const out = []
  if (task.value.request) {
    out.push({
      key: 'req',
      label: `Заявка №${task.value.request}`,
      to: `/requests/${task.value.request}`,
    })
  }
  if (task.value.property) {
    out.push({
      key: 'prop',
      label: task.value.property_title || `Объект #${task.value.property}`,
      to: `/properties/${task.value.property}`,
    })
  }
  return out
})

// --- форматтеры ------------------------------------------------------------
function formatDate(value) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch (_) { return value }
}
function formatDuration(sec) {
  const s = Number(sec) || 0
  if (s < 60) return `${s} с`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} мин`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `${h} ч ${rest} м` : `${h} ч`
}
function priorityLabel(p) {
  return { low: 'Низкий', normal: 'Обычный', high: 'Высокий' }[p] || p
}
function priorityClass(p) {
  if (p === 'high') return 'ctw-tag--danger'
  if (p === 'low') return 'ctw-tag--muted'
  return ''
}
function pct(used, max) {
  const u = Number(used) || 0
  const m = Number(max) || 0
  if (m <= 0) return '0%'
  return `${Math.min(100, Math.round((u / m) * 100))}%`
}
function barClass(used, max) {
  const u = Number(used) || 0
  const m = Number(max) || 0
  if (m > 0 && u >= m) return 'is-full'
  if (m > 0 && u / m >= 0.7) return 'is-high'
  return ''
}

// --- действия --------------------------------------------------------------
async function onStart(id) {
  if (busy.value) return
  busy.value = true
  errorMessage.value = ''
  const res = await startTask(id)
  busy.value = false
  if (!res.ok) {
    errorMessage.value = res.error
    toasts.error(res.error)
  } else {
    toasts.success('Задача запущена')
  }
}
async function onPause() {
  if (!task.value || busy.value) return
  busy.value = true
  errorMessage.value = ''
  const res = await pauseTask(task.value.id)
  busy.value = false
  if (!res.ok) {
    errorMessage.value = res.error
    toasts.error(res.error)
  } else {
    toasts.info('Задача поставлена на паузу')
  }
}
async function onComplete() {
  if (!task.value || busy.value) return
  busy.value = true
  errorMessage.value = ''
  const res = await completeTask(task.value.id, { source: 'current_task_widget' })
  busy.value = false
  if (!res.ok) {
    errorMessage.value = res.error
    toasts.error(res.error)
  } else {
    toasts.success('Задача завершена')
  }
}

// --- жизненный цикл --------------------------------------------------------
onMounted(() => {
  applyReservedSpace()
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', onStorage)
  }
  if (auth.isAuthenticated && auth.isStaff) {
    wl.refresh()
    wl.startPolling()
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('storage', onStorage)
  }
  if (typeof document !== 'undefined') {
    document.documentElement.style.setProperty('--ctw-reserved-space', '0px')
  }
  wl.stopPolling()
})

watch(() => auth.isAuthenticated, (authed) => {
  if (authed && auth.isStaff) {
    wl.refresh()
    wl.startPolling()
  } else {
    wl.stopPolling()
    wl.reset()
  }
})
</script>

<style scoped>
/* Палитра и общие переменные */
.ctw-card,
.ctw-fab {
  --ctw-bg: #ffffff;
  --ctw-text: #1e2a28;
  --ctw-muted: #6a7a77;
  --ctw-border: #e3e9e7;
  --ctw-shadow: 0 14px 32px rgba(16, 24, 23, .18),
                0 2px 6px rgba(16, 24, 23, .06);
  --ctw-accent: #0f3a33;
  --ctw-accent-hover: #134a41;
  --ctw-action: #1fa39a;
  --ctw-action-hover: #188a82;
  --ctw-danger: #c04236;
  --ctw-warn-bg: #fdece9;
  --ctw-warn-text: #9a3b32;
  --ctw-ok: #1fa39a;
  color: var(--ctw-text);
  font-family: inherit;
  z-index: 80;
  box-sizing: border-box;
}
.ctw-card *,
.ctw-fab * { box-sizing: border-box; }

.is-idle    { --ctw-status: #1fa39a; }
.is-busy    { --ctw-status: #3ddbc7; }
.is-blocked { --ctw-status: #c04236; }

/* ============= FAB ===================================================== */
.ctw-fab {
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 56px; height: 56px;
  border-radius: 999px;
  border: 1px solid var(--ctw-border);
  background: var(--ctw-bg);
  color: var(--ctw-accent);
  box-shadow: var(--ctw-shadow);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: transform .15s ease, background .15s ease;
}
.ctw-fab:hover  { transform: translateY(-1px); }
.ctw-fab:active { transform: translateY(0); }
.ctw-fab::after {
  content: '';
  position: absolute;
  top: 8px; right: 8px;
  width: 10px; height: 10px;
  border-radius: 999px;
  background: var(--ctw-status);
  box-shadow: 0 0 0 2px var(--ctw-bg);
}
.ctw-fab__icon { display: inline-flex; }
.ctw-fab__badge {
  position: absolute;
  bottom: 4px; right: 4px;
  min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 999px;
  background: var(--ctw-accent);
  color: #fff;
  font-size: 11px; line-height: 18px; font-weight: 600;
  text-align: center;
}

/* ============= Карточка ================================================ */
.ctw-card {
  position: fixed;
  right: 20px;
  bottom: 20px;
  background: var(--ctw-bg);
  border: 1px solid var(--ctw-border);
  border-radius: 14px;
  box-shadow: var(--ctw-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-height: calc(100vh - 40px);
}
.ctw-card.is-collapsed { width: min(360px, calc(100vw - 32px)); }
.ctw-card.is-expanded  { width: min(440px, calc(100vw - 32px)); }
.ctw-card.is-overloaded { border-color: #e7b7b1; }

.ctw-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--ctw-accent);
  color: #fff;
  cursor: pointer;
  user-select: none;
}
.ctw-head:hover { background: var(--ctw-accent-hover); }

.ctw-dot {
  width: 10px; height: 10px; border-radius: 999px;
  background: var(--ctw-status);
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(255,255,255,.15);
}
.ctw-head__title {
  font-weight: 600;
  font-size: 14px;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #fff;
}
.ctw-head__limits {
  font-size: 11px;
  color: rgba(255,255,255,.9);
  white-space: nowrap;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255,255,255,.15);
  font-weight: 600;
}
.ctw-head__controls {
  display: flex; gap: 2px; align-items: center;
}
.ctw-icon-btn {
  width: 26px; height: 26px;
  border: none; background: transparent;
  color: rgba(255,255,255,.8);
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
}
.ctw-icon-btn:hover { background: rgba(255,255,255,.15); color: #fff; }

.ctw-body {
  display: flex; flex-direction: column; gap: 14px;
  padding: 12px 14px 14px;
  overflow: auto;
  background: var(--ctw-bg);
}

.ctw-section__title {
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--ctw-muted);
  font-weight: 600;
}

.ctw-task__title {
  font-weight: 600;
  font-size: 15px;
  line-height: 1.3;
  word-break: break-word;
}
.ctw-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--ctw-muted);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ctw-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.ctw-tag {
  font-size: 11px; font-weight: 600;
  padding: 3px 9px; border-radius: 999px;
  background: #eef4f2; color: #234240;
}
.ctw-tag--danger  { background: #fdece9; color: var(--ctw-warn-text); }
.ctw-tag--muted   { background: #e6e9e8; color: #546664; }

.ctw-meta {
  margin: 10px 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 3px 10px;
  font-size: 12.5px;
}
.ctw-meta dt { color: var(--ctw-muted); font-weight: 500; }
.ctw-meta dd { margin: 0; font-weight: 600; color: var(--ctw-text); min-width: 0; word-break: break-word; }
.ctw-meta dd.is-overdue { color: var(--ctw-danger); }

.ctw-links { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.ctw-link {
  font-size: 12px;
  color: var(--ctw-accent);
  text-decoration: none;
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(15,58,51,.08);
  font-weight: 500;
}
.ctw-link:hover { text-decoration: underline; }

.ctw-actions { display: flex; gap: 6px; justify-content: flex-end; margin-top: 10px; }

.ctw-empty { margin: 0; color: var(--ctw-muted); font-size: 13px; }
.ctw-next  { display: grid; gap: 6px; margin-top: 8px; }
.ctw-next__row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px; text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--ctw-border);
  background: #fafdfc;
  cursor: pointer;
  font: inherit; font-size: 13px;
  color: var(--ctw-text);
}
.ctw-next__row:hover:not(:disabled) { background: #eef4f2; }
.ctw-next__row:disabled { opacity: .55; cursor: not-allowed; }
.ctw-next__title {
  font-weight: 500;
  min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ctw-next__kind { font-size: 11px; color: var(--ctw-muted); white-space: nowrap; }

.ctw-bars { display: grid; gap: 8px; }
.ctw-bar__label {
  display: flex; justify-content: space-between;
  font-size: 12px; color: var(--ctw-muted);
  margin-bottom: 4px;
}
.ctw-bar__track {
  height: 6px;
  background: #eef4f2;
  border-radius: 999px;
  overflow: hidden;
}
.ctw-bar__fill {
  height: 100%;
  background: var(--ctw-ok);
  transition: width .25s ease;
}
.ctw-bar__fill.is-high { background: #d97706; }
.ctw-bar__fill.is-full { background: var(--ctw-danger); }

.ctw-kpi {
  list-style: none; padding: 0; margin: 0;
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px;
}
.ctw-kpi li {
  display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f3f6f5;
}
.ctw-kpi strong { font-size: 16px; font-weight: 600; color: var(--ctw-text); }
.ctw-kpi span   { font-size: 11px; color: var(--ctw-muted); }

.ctw-warn {
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--ctw-warn-bg);
  color: var(--ctw-warn-text);
  font-size: 12.5px;
  font-weight: 500;
}
.ctw-error {
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(192, 66, 54, .1);
  color: var(--ctw-danger);
  font-size: 12.5px;
}

.ctw-quick {
  display: flex; gap: 6px; justify-content: flex-end;
  padding: 8px 12px 10px;
  border-top: 1px solid var(--ctw-border);
  background: var(--ctw-bg);
}

/* Кнопки (переиспользуем внутри виджета) */
.ctw-btn {
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  padding: 7px 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid var(--ctw-border);
  background: #ffffff;
  color: var(--ctw-text);
  transition: background .15s ease;
}
.ctw-btn:hover:not(:disabled) { background: #f3f6f5; }
.ctw-btn:disabled { opacity: .5; cursor: not-allowed; }
.ctw-btn--sm { padding: 5px 10px; font-size: 11.5px; }
.ctw-btn--primary {
  background: var(--ctw-action);
  border-color: var(--ctw-action);
  color: #fff;
}
.ctw-btn--primary:hover:not(:disabled) { background: var(--ctw-action-hover); }

/* Мобильная адаптация */
@media (max-width: 720px) {
  .ctw-card.is-expanded {
    right: 12px; left: 12px; bottom: 12px;
    width: auto;
    max-height: calc(100vh - 24px);
  }
  .ctw-card.is-collapsed {
    right: 12px; bottom: 12px;
    width: min(320px, calc(100vw - 24px));
  }
  .ctw-fab { right: 16px; bottom: 16px; }
}
</style>
