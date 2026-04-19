<template>
  <!--
    Плавающий виджет текущей задачи. Три режима:
      - hidden   — свёрнут в FAB-иконку (по умолчанию восстанавливается
                   из localStorage);
      - summary  — тонкая шапка с индикатором, заголовком и счётчиками;
      - expanded — полная карточка с метаданными и действиями.
    Подъём над футером — через IntersectionObserver на `.footer`:
    когда футер попадает в область видимости, виджет поднимается
    ровно на его видимую часть, чтобы никогда не перекрывать.
  -->
  <template v-if="auth.isStaff">
    <!-- Свёрнут полностью: круглый FAB в правом нижнем углу. -->
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
      <!-- Шапка-кликабельная: сворачивает в summary/expanded. -->
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
        <!-- Отдельная кнопка «закрыть в FAB», чтобы клик по ней не триггерил
             toggleExpanded. -->
        <button
          class="ctw__close"
          aria-label="Скрыть виджет"
          title="Скрыть"
          @click.stop="setMode('hidden')"
        >×</button>
      </div>

      <!-- Полное тело только в режиме expanded. -->
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
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { pauseTask, completeTask } from '../api/tasks'

const auth = useAuthStore()
const wl = useWorkloadStore()
const busy = ref(false)

// ---------------------------------------------------------------------------
// Режим отображения
// ---------------------------------------------------------------------------
// 'expanded' — полная карточка, 'summary' — тонкая шапка, 'hidden' — FAB.
// Сохраняем между сессиями, но при появлении срочных поводов
// (просрочено / перегрузка) принудительно разворачиваем один раз.
const STORAGE_KEY = 'ctw.mode'
const mode = ref(loadMode())

function loadMode () {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'hidden' || v === 'summary' || v === 'expanded') return v
  } catch (_e) { /* SSR / private mode — ignore */ }
  return 'expanded'
}
function setMode (next) {
  mode.value = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch (_e) { /* ignore */ }
}
function toggleExpanded () {
  setMode(mode.value === 'expanded' ? 'summary' : 'expanded')
}

// ---------------------------------------------------------------------------
// Данные из стора
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Форматирование
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Действия: проходят через api/tasks.js, который сам дёргает
// wl.bumpAfterAction() — виджет синхронно обновится и на других страницах.
// ---------------------------------------------------------------------------
async function pause () {
  if (!task.value) return
  busy.value = true
  try { await pauseTask(task.value.id) }
  finally { busy.value = false }
}
async function complete () {
  if (!task.value) return
  busy.value = true
  try { await completeTask(task.value.id) }
  finally { busy.value = false }
}

// ---------------------------------------------------------------------------
// Поддержание актуальности
// ---------------------------------------------------------------------------
// 1) Авто-refresh при логине/логауте.
// 2) Лёгкий polling каждые 30s на случай, если изменения пришли
//    с другой вкладки или сервера (чат, бот, админка).
// 3) Refresh при возврате вкладки в фокус — мгновенная синхронизация
//    после действий в соседней вкладке.
let pollTimer = null
function startPolling () {
  stopPolling()
  pollTimer = window.setInterval(() => {
    if (!document.hidden && auth.isStaff) wl.refresh()
  }, 30_000)
}
function stopPolling () {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}
function onVisibility () {
  if (!document.hidden && auth.isStaff) wl.refresh()
}

// ---------------------------------------------------------------------------
// Поднятие виджета над футером
// ---------------------------------------------------------------------------
// Следим за `.footer` через IntersectionObserver: как только его верхняя
// граница заходит в viewport, пересчитываем, насколько он перекрывает
// нижний край окна, и сдвигаем виджет ровно на эту высоту + зазор 12px.
// Дополнительно — ResizeObserver, чтобы отрабатывать смену размера футера
// (например, появление плашки «Сессия истекает»).
const footerOverlap = ref(0) // px
const BASE_GAP = 20           // px — базовый отступ от низа
let io = null
let ro = null
let footerEl = null

function measureFooter () {
  if (!footerEl) { footerOverlap.value = 0; return }
  const rect = footerEl.getBoundingClientRect()
  const viewport = window.innerHeight || document.documentElement.clientHeight
  // Насколько низ футера «залез» в нижнюю часть экрана.
  const overlap = Math.max(0, viewport - rect.top)
  footerOverlap.value = Math.min(overlap, rect.height)
}
function attachFooterObservers () {
  footerEl = document.querySelector('.footer, .app-footer, footer')
  if (!footerEl) return
  measureFooter()
  if ('IntersectionObserver' in window) {
    io = new IntersectionObserver(() => measureFooter(), {
      threshold: [0, 0.01, 0.1, 0.25, 0.5, 0.75, 1],
    })
    io.observe(footerEl)
  }
  if ('ResizeObserver' in window) {
    ro = new ResizeObserver(() => measureFooter())
    ro.observe(footerEl)
  }
  window.addEventListener('scroll', measureFooter, { passive: true })
  window.addEventListener('resize', measureFooter)
}
function detachFooterObservers () {
  if (io) { io.disconnect(); io = null }
  if (ro) { ro.disconnect(); ro = null }
  window.removeEventListener('scroll', measureFooter)
  window.removeEventListener('resize', measureFooter)
  footerEl = null
}

const floatStyle = computed(() => ({
  bottom: `${BASE_GAP + footerOverlap.value}px`,
}))

// ---------------------------------------------------------------------------
// Жизненный цикл
// ---------------------------------------------------------------------------
watch(() => auth.isAuthenticated, (v) => {
  if (v && auth.isStaff) wl.refresh()
  else wl.reset()
})

onMounted(() => {
  if (auth.isStaff) wl.refresh()
  startPolling()
  document.addEventListener('visibilitychange', onVisibility)
  // Футер рендерится рядом, но на всякий случай ждём кадр —
  // IntersectionObserver устойчив к тому, что элемент появится позже.
  requestAnimationFrame(attachFooterObservers)
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibility)
  detachFooterObservers()
})
</script>

<style scoped>
/* ---------- Общие плавающие координаты ---------- */
.ctw,
.ctw-fab {
  position: fixed;
  right: 20px;
  z-index: 60;
  /* bottom задаётся инлайново через :style — он подстраивается под футер. */
}

/* ---------- FAB (полностью скрытый режим) ---------- */
.ctw-fab {
  width: 48px; height: 48px; border-radius: 50%;
  border: none; cursor: pointer;
  background: #0f3a33; color: #fff;
  box-shadow: 0 10px 24px rgba(16, 24, 23, .25),
              0 2px 6px rgba(16, 24, 23, .12);
  display: inline-flex; align-items: center; justify-content: center;
  transition: transform .15s ease, background .15s ease;
}
.ctw-fab:hover { background: #134a41; transform: translateY(-1px); }
.ctw-fab.is-overloaded,
.ctw-fab.is-overdue { background: #c34a3d; }
.ctw-fab__icon { display: inline-flex; }
.ctw-fab__badge {
  position: absolute;
  top: 4px; right: 4px;
  min-width: 14px; height: 14px; padding: 0 4px;
  border-radius: 999px;
  background: #ff7a6b; color: #fff;
  font-size: 10px; font-weight: 700; line-height: 14px;
  text-align: center;
  box-shadow: 0 0 0 2px #0f3a33;
}
.ctw-fab.is-overloaded .ctw-fab__badge,
.ctw-fab.is-overdue   .ctw-fab__badge { box-shadow: 0 0 0 2px #c34a3d; }

/* ---------- Карточка (summary + expanded) ---------- */
.ctw {
  width: min(360px, calc(100vw - 32px));
  background: #ffffff;
  color: #1e2a28;
  border-radius: 14px;
  border: 1px solid #e3e9e7;
  box-shadow: 0 14px 32px rgba(16, 24, 23, .18),
              0 2px 6px rgba(16, 24, 23, .06);
  overflow: hidden;
  font-size: 13px;
  transition: bottom .18s ease;
}
.ctw.is-overloaded { border-color: #e7b7b1; }

/* Шапка: основная кнопка + close рядом. */
.ctw__head {
  display: flex; align-items: stretch;
  background: #0f3a33;
  color: #fff;
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
  border: none; cursor: pointer; text-align: left;
  font: inherit;
}
.ctw__head-main:hover { background: rgba(255,255,255,.06); }

.ctw__close {
  flex: 0 0 auto;
  width: 34px;
  border: none;
  background: transparent;
  color: rgba(255,255,255,.75);
  font-size: 20px; line-height: 1; cursor: pointer;
}
.ctw__close:hover { color: #fff; background: rgba(255,255,255,.1); }

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

/* ---------- Тело (только expanded) ---------- */
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
    left: 12px; right: 12px;
    width: auto;
  }
  .ctw-fab { right: 16px; }
}
</style>
