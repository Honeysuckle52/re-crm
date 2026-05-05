<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ЗАДАЧИ</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">Рабочие задачи</h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Поручения сотрудникам: звонки, показы, документы
          </div>
          <div
              v-if="!auth.isManager"
              class="workload-banner"
              :class="{ 'is-limit': workload.isOverloaded }">
            <span>Моя загрузка:</span>
            <b>{{ workload.activeTasksLabel }}</b> задач ·
            <b>{{ workload.activeRequestsLabel }}</b> заявок ·
            <b>{{ workload.workload.in_progress_tasks }}/{{ workload.workload.max_in_progress_tasks }}</b>
            в работе
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--accent" @click="toggleForm">
            {{ showForm ? 'Скрыть форму' : '+ Новая задача' }}
          </button>
        </div>
      </div>
    </div>


    <form v-if="showForm" class="panel panel--light stack" @submit.prevent="create">
      <div class="grid grid--3">
        <div class="field">
          <label>Заголовок</label>
          <input class="input" v-model="form.title" required />
        </div>
        <div class="field">
          <label>Исполнитель</label>
          <select class="select" v-model.number="form.assignee" required>
            <option :value="null" disabled>— выберите —</option>
            <option v-for="a in employees" :key="a.id" :value="a.id">
              {{ a.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Тип задачи</label>
          <select class="select" v-model="form.task_type">
            <option v-for="tt in taskTypes" :key="tt.code" :value="tt.code">
              {{ tt.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Приоритет</label>
          <select class="select" v-model="form.priority">
            <option value="low">Низкий</option>
            <option value="normal">Обычный</option>
            <option value="high">Высокий</option>
          </select>
        </div>
        <div class="field">
          <label>Срок</label>
          <input class="input" type="datetime-local" v-model="form.due_date" />
        </div>
        <div class="field">
          <label>Связанная заявка</label>
          <select class="select" v-model.number="form.request">
            <option :value="null">— не выбрана —</option>
            <option v-for="r in requests" :key="r.id" :value="r.id">
              №{{ r.id }} — {{ r.client_username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Клиент</label>
          <select class="select" v-model.number="form.client">
            <option :value="null">— не выбран —</option>
            <option v-for="c in clients" :key="c.id" :value="c.id">
              {{ c.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Связанный объект</label>
          <select class="select" v-model.number="form.property">
            <option :value="null">— не выбран —</option>
            <option v-for="p in properties" :key="p.id" :value="p.id">
              {{ p.title || 'Объект №' + p.id }}
            </option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>Описание</label>
        <textarea class="textarea" v-model="form.description" rows="3"></textarea>
      </div>
      <div class="row" style="justify-content: flex-end">
        <button class="btn btn--accent" type="submit">Создать задачу</button>
      </div>
    </form>

    <div class="panel panel--light">
      <div class="tabs">
        <button class="tab"
                :class="{ 'tab--active': viewMode === 'active' }"
                @click="setViewMode('active')">
          Активные <span class="tab__count">{{ activeCount }}</span>
        </button>
        <button class="tab"
                :class="{ 'tab--active': viewMode === 'history' }"
                @click="setViewMode('history')">
          История <span class="tab__count">{{ historyCount }}</span>
        </button>
      </div>

      <div v-if="viewMode === 'active'" class="filter-row">
        <div class="filter-group">
          <span class="filter-label">Статус:</span>
          <div class="row" style="gap: 6px; flex-wrap: wrap">
            <button class="btn btn--sm"
                    :class="{ 'btn--primary': statusFilter === '' }"
                    @click="statusFilter = ''">
              Все ({{ activeCount }})
            </button>
            <button v-for="s in activeStatuses" :key="s.id"
                    class="btn btn--sm"
                    :class="{ 'btn--primary': statusFilter === s.id }"
                    @click="statusFilter = s.id">
              {{ s.name }} ({{ countByStatus(s.id) }})
            </button>
          </div>
        </div>
        <div class="filter-group">
          <span class="filter-label">Тип:</span>
          <select class="select select--sm" v-model="typeFilter">
            <option value="">Все типы</option>
            <option v-for="tt in taskTypes" :key="tt.code" :value="tt.code">
              {{ tt.name }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="viewMode === 'active'" class="panel panel--light">
      <div class="surface-head task-section-head">
        <div>
          <div class="surface-head__meta">Рабочий список</div>
          <h2 class="h3">Активные задачи</h2>
        </div>
        <div class="surface-head__caption">Показано: {{ filtered.length }}</div>
      </div>
      <div class="table-wrap task-table-wrap">
        <table class="table">
        <thead>
          <tr>
            <th></th>
            <th>Заголовок</th>
            <th>Тип</th>
            <th>Исполнитель</th>
            <th>Заявка</th>
            <th>Приоритет</th>
            <th>Срок</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in filtered" :key="t.id"
              :class="{ 'row--mine': isMine(t), 'row--active': isMyActive(t) }">
            <td class="mine-cell">
              <TaskMineBadge :task="t" :user-id="auth.user?.id" mode="dot" />
            </td>
            <td>
              <b>{{ t.title }}</b>
              <div class="muted" style="font-size: 12px" v-if="t.property_title">
                Объект: {{ t.property_title }}
              </div>
            </td>
            <td>
              <span class="tag tag--type">{{ t.task_type_display || taskTypeLabel(t.task_type) }}</span>
            </td>
            <td>
              <div class="assignee-cell">
                <span>{{ t.assignee_username }}</span>
                <TaskMineBadge :task="t" :user-id="auth.user?.id" mode="full" />
              </div>
            </td>
            <td>
              <router-link v-if="t.request" :to="`/requests/${t.request}`"
                           class="link">
                №{{ t.request }}
              </router-link>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span class="tag" :class="priorityClass(t.priority)">
                {{ priorityLabel(t.priority) }}
              </span>
            </td>
            <td class="muted" style="white-space: nowrap">
              {{ t.due_date ? formatDate(t.due_date) : '—' }}
              <span v-if="t.is_overdue" class="tag overdue">просрочено</span>
            </td>
            <td>
              <span class="tag tag--accent">{{ t.status_name }}</span>
              <div v-if="t.is_auto_closed"
                   class="auto-closed-badge" title="Задача закрыта автоматически">
                авто
              </div>
            </td>
            <td class="task-actions">
              <button v-if="canOpenWorkflow(t)"
                      class="btn btn--sm btn--primary"
                      @click="openWorkflow(t)">
                Открыть
              </button>
              <button v-if="canStart(t)"
                      class="btn btn--sm btn--accent"
                      :disabled="!canStartBtn(t) || busyId === t.id"
                      :title="!canStartBtn(t) ? 'У сотрудника уже есть задача в работе' : 'Взять в работу'"
                      @click="startTask(t)">
                Старт
              </button>
              <button v-if="canPause(t)"
                      class="btn btn--sm"
                      :disabled="busyId === t.id"
                      @click="pauseTask(t)">
                Пауза
              </button>
              <button v-if="canComplete(t)"
                      class="btn btn--sm btn--ghost"
                      :disabled="busyId === t.id"
                      @click="openCompleteModal(t)">
                Завершить
              </button>
              <select class="select select--sm"
                      :value="t.status"
                      @change="changeStatus(t, $event.target.value)">
                <option disabled value="">Статус…</option>
                <option v-for="s in statuses" :key="s.id" :value="s.id">
                  {{ s.name }}
                </option>
              </select>
            </td>
          </tr>
        </tbody>
        </table>
      </div>
      <div v-if="!filtered.length" class="empty">Задач нет.</div>
    </div>

    <div v-else class="panel panel--light">
      <div class="surface-head task-section-head">
        <div>
          <div class="surface-head__meta">Архив выполнения</div>
          <h2 class="h3">История по задачам</h2>
        </div>
        <div class="surface-head__caption">Записей: {{ historyCount }}</div>
      </div>
      <div class="table-wrap task-history-wrap">
        <table class="table">
        <thead>
          <tr>
            <th>Задача</th>
            <th>Тип</th>
            <th>Исполнитель</th>
            <th>Заявка</th>
            <th>Завершена</th>
            <th>Длительность</th>
            <th>Результат</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in history" :key="t.id">
            <td>
              <b>{{ t.title }}</b>
              <div class="muted" style="font-size: 12px" v-if="t.property_title">
                Объект: {{ t.property_title }}
              </div>
            </td>
            <td>
              <span class="tag tag--type">{{ t.task_type_display || taskTypeLabel(t.task_type) }}</span>
            </td>
            <td>{{ t.assignee_username }}</td>
            <td>
              <router-link v-if="t.request" :to="`/requests/${t.request}`" class="link">
                №{{ t.request }}
              </router-link>
              <span v-else class="muted">—</span>
            </td>
            <td class="muted" style="white-space: nowrap">
              {{ t.completed_at ? formatDate(t.completed_at) : '—' }}
            </td>
            <td class="muted" style="white-space: nowrap">
              {{ humanDuration(t) }}
            </td>
            <td class="history-result">
              <div class="tag tag--accent" v-if="t.status_code === 'done'">выполнена</div>
              <div class="tag" v-else-if="t.status_code === 'cancelled'" style="background:#fde7e4;color:#c2554a">отменена</div>
              <div class="muted" style="font-size: 12px; margin-top: 4px" v-if="resultSummary(t)">
                {{ resultSummary(t) }}
              </div>
            </td>
          </tr>
        </tbody>
        </table>
      </div>
      <div v-if="!history.length" class="empty">Выполненных задач пока нет.</div>
    </div>

    <Teleport to="body">
      <div v-if="completeModal.show" class="modal-overlay" @click.self="closeCompleteModal">
        <div class="modal">
          <h3 class="h3">Завершение задачи</h3>
          <p class="muted" style="margin-top: 8px">
            {{ completeModal.task?.title }}
          </p>
          <div class="field" style="margin-top: 16px">
            <label>Результат выполнения (опционально)</label>
            <textarea class="textarea" v-model="completeModal.result"
                      rows="4" placeholder="Опишите результат..."></textarea>
          </div>
          <div class="row" style="gap: 10px; justify-content: flex-end; margin-top: 20px">
            <button class="btn" @click="closeCompleteModal">Отмена</button>
            <button class="btn btn--accent" @click="confirmComplete"
                    :disabled="busyId === completeModal.task?.id">
              Завершить
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import * as tasksApi from '../api/tasks'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import TaskMineBadge from '../components/TaskMineBadge.vue'
import { formatDateShort as formatDate } from '@/utils/formatters'

const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()
const router = useRouter()

const tasks = ref([])
const history = ref([])
const statuses = ref([])
const employees = ref([])
const clients = ref([])
const requests = ref([])
const properties = ref([])

const statusFilter = ref('')
const typeFilter = ref('')
const showForm = ref(false)
const busyId = ref(null)
const viewMode = ref('active')

const taskTypes = [
  { code: 'contact_client', name: 'Связаться с клиентом' },
  { code: 'property_search', name: 'Подбор объектов' },
  { code: 'showing', name: 'Показ объекта' },
  { code: 'documents', name: 'Подготовка документов' },
  { code: 'call', name: 'Звонок' },
  { code: 'other', name: 'Прочее' },
]

const completeModal = reactive({ show: false, task: null, result: '' })
function openCompleteModal(task) {
  completeModal.task = task
  completeModal.result = ''
  completeModal.show = true
}
function closeCompleteModal() {
  completeModal.show = false
  completeModal.task = null
}

const form = reactive(defaultForm())

function defaultForm () {
  return {
    title: '', description: '',
    assignee: null, priority: 'normal', task_type: 'other',
    due_date: '', request: null, client: null, property: null,
  }
}

const TERMINAL_CODES = ['done', 'cancelled']
const activeTasks = computed(() => (
  tasks.value.filter(t => !TERMINAL_CODES.includes(t.status_code))
))
const activeStatuses = computed(() => (
  statuses.value.filter(s => !TERMINAL_CODES.includes(s.code))
))

const filtered = computed(() => {
  let result = activeTasks.value
  if (statusFilter.value) {
    result = result.filter((t) => t.status === statusFilter.value)
  }
  if (typeFilter.value) {
    result = result.filter((t) => t.task_type === typeFilter.value)
  }
  return result
})

const activeCount = computed(() => activeTasks.value.length)
const historyCount = computed(() => history.value.length)
const inProgressCount = computed(() => (
  activeTasks.value.filter((t) => t.status_code === 'in_progress').length
))
const overdueCount = computed(() => (
  activeTasks.value.filter((t) => t.is_overdue).length
))
const newCount = computed(() => (
  activeTasks.value.filter((t) => t.status_code === 'new').length
))

function countByStatus (id) {
  return activeTasks.value.filter((t) => t.status === id).length
}

function taskTypeLabel (code) {
  return taskTypes.find(t => t.code === code)?.name || code
}

function priorityLabel (p) {
  return ({ low: 'Низкий', normal: 'Обычный', high: 'Высокий' })[p] || p
}
function priorityClass (p) {
  if (p === 'high') return 'tag--accent'
  if (p === 'low') return 'tag--panel'
  return ''
}

function humanDuration (t) {
  if (!t.created_at || !t.completed_at) return '—'
  const ms = new Date(t.completed_at) - new Date(t.created_at)
  if (!Number.isFinite(ms) || ms < 0) return '—'
  const min = Math.round(ms / 60000)
  if (min < 60) return `${min} мин`
  const hours = Math.floor(min / 60)
  const rest = min % 60
  if (hours < 24) return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
  const days = Math.floor(hours / 24)
  return `${days} дн ${hours % 24} ч`
}

function resultSummary (t) {
  if (!t.result) return ''
  if (typeof t.result === 'string') return t.result
  return t.result.summary || ''
}

function toggleForm () {
  showForm.value = !showForm.value
  if (showForm.value) Object.assign(form, defaultForm())
}

function isMine (t) { return t.assignee === auth.user?.id }
function isMyActive (t) {
  return isMine(t) && t.status_code === 'in_progress'
}

async function load () {
  const [t, s, e, c, r, p] = await Promise.all([
    api.get('/tasks/'),
    api.get('/task-statuses/'),
    api.get('/users/', { params: { user_type: 'employee' } }),
    api.get('/users/', { params: { user_type: 'client' } }),
    api.get('/requests/'),
    api.get('/properties/'),
  ])
  tasks.value = t.data.results || t.data
  statuses.value = s.data.results || s.data
  employees.value = e.data.results || e.data
  clients.value = c.data.results || c.data
  requests.value = r.data.results || r.data
  properties.value = p.data.results || p.data
}

async function loadHistory () {
  const params = {
    status_code: 'done,cancelled',
    ordering: '-completed_at',
    page_size: 100,
  }
  if (!auth.isManager) params.assignee = 'me'
  const { data } = await api.get('/tasks/', { params })
  history.value = data.results || data
}

function setViewMode (mode) {
  viewMode.value = mode
  if (mode === 'history') loadHistory()
}

async function create () {
  const payload = { ...form }
  if (!payload.due_date) delete payload.due_date
  if (!payload.request) delete payload.request
  if (!payload.client) delete payload.client
  if (!payload.property) delete payload.property
  try {
    await api.post('/tasks/', payload)
    showForm.value = false
    Object.assign(form, defaultForm())
    toasts.success('Задача создана')
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось создать задачу'))
  }
}

async function changeStatus (task, statusId) {
  if (!statusId) return
  const { ok, data, error } = await tasksApi.changeTaskStatus(task.id, statusId)
  if (ok) {
    applyTaskPatch(data)
    toasts.success('Статус изменён')
  } else {
    toasts.error(error || 'Не удалось изменить статус')
  }
}

function isOwnOrManaged (task) {
  return auth.isManager || task.assignee === auth.user?.id
}
function canStart (task) {
  return isOwnOrManaged(task)
    && ['new', 'waiting'].includes(task.status_code)
}
function canPause (task) {
  return isOwnOrManaged(task) && task.status_code === 'in_progress'
}
function canComplete (task) {
  return isOwnOrManaged(task)
    && ['new', 'in_progress', 'waiting'].includes(task.status_code)
}
function canOpenWorkflow (task) {
  return task.assignee === auth.user?.id
    && !TERMINAL_CODES.includes(task.status_code)
}
function canStartBtn (task) {
  if (auth.isManager) return true
  if (task.assignee !== auth.user?.id) return false
  return workload.workload.in_progress_tasks
      < workload.workload.max_in_progress_tasks
}

function applyTaskPatch (task) {
  if (!task || !task.id) return
  const idx = tasks.value.findIndex(t => t.id === task.id)
  if (idx >= 0) tasks.value.splice(idx, 1, task)
  else tasks.value.push(task)
}

async function startTask (task) {
  busyId.value = task.id
  const prevStatusCode = task.status_code
  const prevStatus = task.status
  const inProgress = statuses.value.find(s => s.code === 'in_progress')
  if (inProgress) {
    applyTaskPatch({
      ...task,
      status_code: 'in_progress',
      status: inProgress.id,
      status_name: inProgress.name,
    })
  }
  workload.optimisticStartTask({ ...task, status_code: 'in_progress' })

  const { ok, data, error } = await tasksApi.startTask(task.id)
  if (ok) {
    applyTaskPatch(data)
    toasts.success('Задача взята в работу')
  } else {
    applyTaskPatch({
      ...task,
      status_code: prevStatusCode,
      status: prevStatus,
    })
    workload.refresh()
    toasts.error(error || 'Нельзя стартовать задачу: превышен лимит')
  }
  busyId.value = null
}

async function pauseTask (task) {
  busyId.value = task.id
  const { ok, data, error } = await tasksApi.pauseTask(task.id)
  if (ok) {
    applyTaskPatch(data)
    toasts.success('Задача приостановлена')
  } else {
    toasts.error(error || 'Не удалось приостановить задачу')
  }
  busyId.value = null
}

async function confirmComplete () {
  const task = completeModal.task
  if (!task) return
  busyId.value = task.id

  workload.optimisticCompleteTask(task.id)

  const payload = completeModal.result
    ? { summary: completeModal.result }
    : {}
  const { ok, data, error } = await tasksApi.completeTask(task.id, payload)
  if (ok) {
    applyTaskPatch(data)
    if (viewMode.value === 'history') loadHistory()
    toasts.success('Задача завершена')
    closeCompleteModal()
  } else {
    workload.refresh()
    toasts.error(error || 'Не удалось завершить задачу')
  }
  busyId.value = null
}

function openWorkflow (task) {
  router.push({ name: 'task-workflow', params: { id: task.id } })
}

onMounted(async () => {
  await load()
  if (auth.isStaff) workload.refresh()
})
</script>

<style scoped>
.link {
  color: var(--c-accent);
  font-weight: 600;
}

.link:hover {
  color: var(--c-accent-2);
  text-decoration: underline;
  text-decoration-color: rgba(99, 208, 197, 0.36);
}

.overdue {
  margin-left: 6px;
  background: rgba(255, 111, 134, 0.14);
  color: #ffd4dc;
  border-color: rgba(255, 111, 134, 0.2);
}

.select--sm {
  padding: 10px 42px 10px 14px;
  font-size: 13px;
}

.task-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.task-section-head {
  margin-bottom: 14px;
}

.task-table-wrap .table {
  min-width: 1120px;
}

.task-history-wrap .table {
  min-width: 780px;
}

.workload-banner {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid rgba(99, 208, 197, 0.24);
  background: rgba(99, 208, 197, 0.12);
  color: #effffd;
  font-size: 13px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.workload-banner.is-limit {
  border-color: rgba(255, 111, 134, 0.24);
  background: rgba(255, 111, 134, 0.14);
  color: #ffd5de;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 5px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 999px;
  border: 1px solid var(--c-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  margin-bottom: 16px;
  width: fit-content;
}
.tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: transparent;
  border: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-muted);
  border-radius: 999px;
  cursor: pointer;
  transition: color 0.3s ease, background 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;
}
.tab:hover {
  color: var(--c-text);
}

.tab--active {
  background: var(--grad-accent);
  color: #143634;
  box-shadow: 0 12px 24px rgba(46, 159, 152, 0.14);
}
.tab__count {
  background: rgba(255, 255, 255, 0.08);
  color: var(--c-text-muted);
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.tab--active .tab__count {
  background: rgba(4, 21, 32, 0.12);
  color: #143634;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}
.filter-group {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.filter-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-text-muted);
}

.tag--type {
  background: rgba(99, 208, 197, 0.14);
  color: #effffd;
  font-size: 11px;
  border-color: rgba(99, 208, 197, 0.2);
}

.auto-closed-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  background: rgba(99, 208, 197, 0.16);
  color: #effffd;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(99, 208, 197, 0.2);
  margin-left: 6px;
}

.tag[style*='background:#fde7e4'][style*='color:#c2554a'] {
  background: rgba(255, 111, 134, 0.14) !important;
  color: #ffd4dc !important;
  border-color: rgba(255, 111, 134, 0.22) !important;
}

.mine-cell {
  width: 18px;
  padding-left: 14px !important;
}

.row--mine > td:first-child {
  box-shadow: inset 3px 0 0 rgba(31, 163, 154, 0.32);
}
.row--active > td:first-child {
  box-shadow: inset 3px 0 0 rgba(99, 208, 197, 0.55);
}
.row--active {
  background: rgba(99, 208, 197, 0.06);
}

.assignee-cell {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.history-result {
  min-width: 160px;
}

.modal-overlay {
  z-index: 100;
}
.modal {
  position: relative;
  inset: auto;
  z-index: 1;
  display: block;
  width: min(100%, 480px);
  max-height: calc(100vh - 32px);
  overflow: auto;
  background: var(--grad-panel);
  border-radius: 24px;
  border: 1px solid var(--c-border-strong);
  padding: 24px 28px;
  max-width: 480px;
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-glow);
}

@media (max-width: 960px) {
  .tabs {
    width: 100%;
    flex-wrap: wrap;
  }

  .task-actions {
    justify-content: flex-end;
  }
}

@media (max-width: 720px) {
  .filter-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .assignee-cell {
    align-items: flex-start;
  }
}
</style>
