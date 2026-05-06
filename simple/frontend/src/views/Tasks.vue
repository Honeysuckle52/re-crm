<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Задачи</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">Рабочие задачи</h1>
          <div
            v-if="!auth.isManager"
            class="workload-banner"
            :class="{ 'is-limit': workload.isOverloaded }"
          >
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
          <input v-model="form.title" class="input" required />
        </div>
        <RemoteLookupField
          v-model="form.assignee"
          label="Исполнитель"
          placeholder="Найти сотрудника по логину, почте или имени"
          endpoint="/users/"
          :params="{ user_type: 'employee' }"
          :map-option="mapAssigneeOption"
          :clearable="false"
        />
        <div class="field">
          <label>Тип задачи</label>
          <select v-model="form.task_type" class="select">
            <option v-for="taskType in taskTypes" :key="taskType.code" :value="taskType.code">
              {{ taskType.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Приоритет</label>
          <select v-model="form.priority" class="select">
            <option value="low">Низкий</option>
            <option value="normal">Обычный</option>
            <option value="high">Высокий</option>
          </select>
        </div>
        <div class="field">
          <label>Срок</label>
          <input v-model="form.due_date" class="input" type="datetime-local" />
        </div>
        <RemoteLookupField
          v-model="form.request"
          label="Связанная заявка"
          placeholder="Найти заявку по номеру, клиенту или объекту"
          endpoint="/requests/"
          :params="{ ordering: '-updated_at' }"
          :map-option="mapRequestOption"
          no-results-text="Заявки не найдены."
        />
        <RemoteLookupField
          v-model="form.client"
          label="Клиент"
          placeholder="Найти клиента по логину, почте или телефону"
          endpoint="/users/"
          :params="{ user_type: 'client' }"
          :map-option="mapClientOption"
        />
        <RemoteLookupField
          v-model="form.property"
          label="Связанный объект"
          placeholder="Найти объект по номеру или названию"
          endpoint="/properties/"
          :params="{ ordering: '-created_at' }"
          :map-option="mapPropertyOption"
          no-results-text="Объекты не найдены."
        />
      </div>

      <div class="field">
        <label>Описание</label>
        <textarea v-model="form.description" class="textarea" rows="3"></textarea>
      </div>

      <div class="row" style="justify-content: flex-end">
        <button class="btn btn--accent" type="submit">Создать задачу</button>
      </div>
    </form>

    <div class="panel panel--light">
      <div class="tabs">
        <button
          class="tab"
          :class="{ 'tab--active': viewMode === 'active' }"
          @click="setViewMode('active')"
        >
          Активные <span class="tab__count">{{ activeCount }}</span>
        </button>
        <button
          class="tab"
          :class="{ 'tab--active': viewMode === 'history' }"
          @click="setViewMode('history')"
        >
          История <span class="tab__count">{{ historyCount }}</span>
        </button>
      </div>

      <div v-if="viewMode === 'active'" class="filter-row">
        <div class="filter-group">
          <span class="filter-label">Статус:</span>
          <div class="row" style="gap: 6px; flex-wrap: wrap">
            <button
              class="btn btn--sm"
              :class="{ 'btn--primary': statusFilter === '' }"
              @click="statusFilter = ''"
            >
              Все ({{ activeCount }})
            </button>
            <button
              v-for="status in activeStatuses"
              :key="status.id"
              class="btn btn--sm"
              :class="{ 'btn--primary': statusFilter === String(status.id) }"
              @click="statusFilter = String(status.id)"
            >
              {{ status.name }} ({{ countByStatus(status.id) }})
            </button>
          </div>
        </div>
        <div class="filter-group">
          <span class="filter-label">Тип:</span>
          <select v-model="typeFilter" class="select select--sm">
            <option value="">Все типы</option>
            <option v-for="taskType in taskTypes" :key="taskType.code" :value="taskType.code">
              {{ taskType.name }}
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
        <div class="surface-head__caption">
          Показано: {{ filtered.length }} из {{ activeFilteredCount }}
        </div>
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
            <tr
              v-for="task in filtered"
              :key="task.id"
              :class="{ 'row--mine': isMine(task), 'row--active': isMyActive(task) }"
            >
              <td class="mine-cell">
                <TaskMineBadge :task="task" :user-id="auth.user?.id" mode="dot" />
              </td>
              <td>
                <b>{{ task.title }}</b>
                <div v-if="task.property_title" class="muted" style="font-size: 12px">
                  Объект: {{ task.property_title }}
                </div>
              </td>
              <td>
                <span class="tag tag--type">
                  {{ task.task_type_display || taskTypeLabel(task.task_type) }}
                </span>
              </td>
              <td>
                <div class="assignee-cell">
                  <span>{{ task.assignee_username }}</span>
                  <TaskMineBadge :task="task" :user-id="auth.user?.id" mode="full" />
                </div>
              </td>
              <td>
                <router-link v-if="task.request" :to="`/requests/${task.request}`" class="link">
                  №{{ task.request }}
                </router-link>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <span class="tag" :class="priorityClass(task.priority)">
                  {{ priorityLabel(task.priority) }}
                </span>
              </td>
              <td class="muted" style="white-space: nowrap">
                {{ task.due_date ? formatDate(task.due_date) : '—' }}
                <span v-if="task.is_overdue" class="tag overdue">просрочено</span>
              </td>
              <td>
                <span class="tag tag--accent">{{ task.status_name }}</span>
                <div
                  v-if="task.is_auto_closed"
                  class="auto-closed-badge"
                  title="Задача закрыта автоматически"
                >
                  авто
                </div>
              </td>
              <td class="task-actions">
                <button
                  v-if="canOpenWorkflow(task)"
                  class="btn btn--sm btn--primary"
                  @click="openWorkflow(task)"
                >
                  Открыть
                </button>
                <button
                  v-if="canStart(task)"
                  class="btn btn--sm btn--accent"
                  :disabled="!canStartBtn(task) || busyId === task.id"
                  :title="!canStartBtn(task) ? 'У сотрудника уже есть задача в работе' : 'Взять в работу'"
                  @click="startTask(task)"
                >
                  Старт
                </button>
                <button
                  v-if="canPause(task)"
                  class="btn btn--sm"
                  :disabled="busyId === task.id"
                  @click="pauseTask(task)"
                >
                  Пауза
                </button>
                <button
                  v-if="canComplete(task)"
                  class="btn btn--sm btn--ghost"
                  :disabled="busyId === task.id"
                  @click="openCompleteModal(task)"
                >
                  Завершить
                </button>
                <select
                  class="select select--sm"
                  :value="task.status"
                  @change="changeStatus(task, $event.target.value)"
                >
                  <option disabled value="">Статус…</option>
                  <option v-for="status in statuses" :key="status.id" :value="status.id">
                    {{ status.name }}
                  </option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!filtered.length" class="empty">Задач нет.</div>

      <ListPagination
        v-if="activeFilteredCount > filtered.length"
        :count="activeFilteredCount"
        :page="activePage"
        :visible-count="filtered.length"
        label="задач"
        @change="setActivePage"
      />
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
            <tr v-for="task in history" :key="task.id">
              <td>
                <b>{{ task.title }}</b>
                <div v-if="task.property_title" class="muted" style="font-size: 12px">
                  Объект: {{ task.property_title }}
                </div>
              </td>
              <td>
                <span class="tag tag--type">
                  {{ task.task_type_display || taskTypeLabel(task.task_type) }}
                </span>
              </td>
              <td>{{ task.assignee_username }}</td>
              <td>
                <router-link v-if="task.request" :to="`/requests/${task.request}`" class="link">
                  №{{ task.request }}
                </router-link>
                <span v-else class="muted">—</span>
              </td>
              <td class="muted" style="white-space: nowrap">
                {{ task.completed_at ? formatDate(task.completed_at) : '—' }}
              </td>
              <td class="muted" style="white-space: nowrap">
                {{ humanDuration(task) }}
              </td>
              <td class="history-result">
                <div v-if="task.status_code === 'done'" class="tag tag--accent">выполнена</div>
                <div
                  v-else-if="task.status_code === 'cancelled'"
                  class="tag tag--cancelled"
                >
                  отменена
                </div>
                <div v-if="resultSummary(task)" class="muted" style="font-size: 12px; margin-top: 4px">
                  {{ resultSummary(task) }}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!history.length" class="empty">Выполненных задач пока нет.</div>

      <ListPagination
        v-if="historyCount > history.length"
        :count="historyCount"
        :page="historyPage"
        :visible-count="history.length"
        label="записей"
        @change="setHistoryPage"
      />
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
            <textarea
              v-model="completeModal.result"
              class="textarea"
              rows="4"
              placeholder="Опишите результат..."
            ></textarea>
          </div>
          <div class="row" style="gap: 10px; justify-content: flex-end; margin-top: 20px">
            <button class="btn" @click="closeCompleteModal">Отмена</button>
            <button
              class="btn btn--accent"
              :disabled="busyId === completeModal.task?.id"
              @click="confirmComplete"
            >
              Завершить
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import * as tasksApi from '../api/tasks'
import ListPagination from '../components/ListPagination.vue'
import RemoteLookupField from '../components/RemoteLookupField.vue'
import TaskMineBadge from '../components/TaskMineBadge.vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { formatDateShort as formatDate, formatMoney } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()
const router = useRouter()

const tasks = ref([])
const history = ref([])
const statuses = ref([])

const statusFilter = ref('')
const typeFilter = ref('')
const showForm = ref(false)
const busyId = ref(null)
const viewMode = ref('active')
const activePage = ref(1)
const historyPage = ref(1)
const activeTotalCount = ref(0)
const activeFilteredCount = ref(0)
const historyTotalCount = ref(0)
const statusCounts = ref({})

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

function defaultForm() {
  return {
    title: '',
    description: '',
    assignee: null,
    priority: 'normal',
    task_type: 'other',
    due_date: '',
    request: null,
    client: null,
    property: null,
  }
}

const TERMINAL_CODES = ['done', 'cancelled']

const activeTasks = computed(() => tasks.value)
const activeStatuses = computed(() => (
  statuses.value.filter((status) => !TERMINAL_CODES.includes(status.code))
))
const filtered = computed(() => activeTasks.value)
const activeCount = computed(() => activeTotalCount.value)
const historyCount = computed(() => historyTotalCount.value)

function countByStatus(id) {
  return statusCounts.value[String(id)] || 0
}

function mapAssigneeOption(user) {
  return {
    id: user.id,
    label: user.username,
    hint: [user.role_name, user.email].filter(Boolean).join(' · ') || 'Сотрудник',
  }
}

function mapClientOption(user) {
  return {
    id: user.id,
    label: user.username,
    hint: [user.email, user.phone].filter(Boolean).join(' · ') || 'Клиент',
  }
}

function mapRequestOption(request) {
  return {
    id: request.id,
    label: `Заявка №${request.id}`,
    hint: [
      request.client_username,
      request.property_title,
      request.status_name,
    ].filter(Boolean).join(' · ') || 'Заявка',
  }
}

function mapPropertyOption(property) {
  const title = property.title || `Объект №${property.id}`
  const price = property.price ? `${formatMoney(property.price)} ₽` : ''
  return {
    id: property.id,
    label: title,
    hint: [property.operation_type_name, price].filter(Boolean).join(' · ') || 'Объект',
  }
}

function taskTypeLabel(code) {
  return taskTypes.find((taskType) => taskType.code === code)?.name || code
}

function priorityLabel(priority) {
  return ({
    low: 'Низкий',
    normal: 'Обычный',
    high: 'Высокий',
  })[priority] || priority
}

function priorityClass(priority) {
  if (priority === 'high') return 'tag--accent'
  if (priority === 'low') return 'tag--panel'
  return ''
}

function humanDuration(task) {
  if (!task.created_at || !task.completed_at) return '—'
  const ms = new Date(task.completed_at) - new Date(task.created_at)
  if (!Number.isFinite(ms) || ms < 0) return '—'
  const minutes = Math.round(ms / 60000)
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours < 24) return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
  const days = Math.floor(hours / 24)
  return `${days} дн ${hours % 24} ч`
}

function resultSummary(task) {
  if (!task.result) return ''
  if (typeof task.result === 'string') return task.result
  return task.result.summary || JSON.stringify(task.result)
}

function toggleForm() {
  showForm.value = !showForm.value
  if (showForm.value) {
    Object.assign(form, defaultForm())
  }
}

function activeListParams({ includeStatusFilter = true, page = activePage.value } = {}) {
  const params = {
    status_code: 'new,in_progress,waiting',
    page,
  }
  if (includeStatusFilter && statusFilter.value) {
    params.status = Number(statusFilter.value)
  }
  if (typeFilter.value) {
    params.task_type = typeFilter.value
  }
  return params
}

function historyListParams({ page = historyPage.value } = {}) {
  const params = {
    status_code: 'done,cancelled',
    ordering: '-completed_at',
    page,
  }
  if (!auth.isManager) {
    params.assignee = 'me'
  }
  return params
}

async function load() {
  const { data } = await api.get('/tasks/', { params: activeListParams() })
  const payload = unpackPaginated(data)
  tasks.value = payload.items
  activeFilteredCount.value = payload.count
}

async function loadLookups() {
  const { data } = await api.get('/task-statuses/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  statuses.value = unpackPaginated(data).items
}

async function loadHistory() {
  const { data } = await api.get('/tasks/', { params: historyListParams() })
  const payload = unpackPaginated(data)
  history.value = payload.items
  historyTotalCount.value = payload.count
}

function setViewMode(mode) {
  viewMode.value = mode
  if (mode === 'history') {
    loadHistory()
  }
}

async function fetchTaskCount(params = {}) {
  const { data } = await api.get('/tasks/', {
    params: { page: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadTaskCounts() {
  const baseActiveParams = activeListParams({
    includeStatusFilter: false,
    page: 1,
  })
  const requests = [
    fetchTaskCount(baseActiveParams),
    fetchTaskCount(historyListParams({ page: 1 })),
    ...activeStatuses.value.map((status) => fetchTaskCount({
      ...baseActiveParams,
      status: status.id,
    })),
  ]

  const [activeTotal, historyTotal, ...perStatus] = await Promise.all(requests)
  activeTotalCount.value = activeTotal
  historyTotalCount.value = historyTotal

  const nextCounts = {}
  activeStatuses.value.forEach((status, index) => {
    nextCounts[String(status.id)] = perStatus[index]
  })
  statusCounts.value = nextCounts
}

function setActivePage(page) {
  if (page < 1 || page === activePage.value) return
  activePage.value = page
}

function setHistoryPage(page) {
  if (page < 1 || page === historyPage.value) return
  historyPage.value = page
}

async function create() {
  if (!form.assignee) {
    toasts.error('Выберите исполнителя задачи')
    return
  }

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
    activePage.value = 1
    await Promise.all([load(), loadTaskCounts(), workload.refresh()])
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось создать задачу'))
  }
}

async function changeStatus(task, statusId) {
  if (!statusId) return
  const { ok, data, error } = await tasksApi.changeTaskStatus(task.id, statusId)
  if (ok) {
    applyTaskPatch(data)
    await Promise.all([load(), loadTaskCounts(), workload.refresh()])
    toasts.success('Статус изменён')
  } else {
    toasts.error(error || 'Не удалось изменить статус')
  }
}

function isMine(task) {
  return task.assignee === auth.user?.id
}

function isMyActive(task) {
  return isMine(task) && task.status_code === 'in_progress'
}

function isOwnOrManaged(task) {
  return auth.isManager || task.assignee === auth.user?.id
}

function canStart(task) {
  return isOwnOrManaged(task) && ['new', 'waiting'].includes(task.status_code)
}

function canPause(task) {
  return isOwnOrManaged(task) && task.status_code === 'in_progress'
}

function canComplete(task) {
  return isOwnOrManaged(task) && ['new', 'in_progress', 'waiting'].includes(task.status_code)
}

function canOpenWorkflow(task) {
  return task.assignee === auth.user?.id && !TERMINAL_CODES.includes(task.status_code)
}

function canStartBtn(task) {
  if (auth.isManager) return true
  if (task.assignee !== auth.user?.id) return false
  return workload.workload.in_progress_tasks < workload.workload.max_in_progress_tasks
}

function applyTaskPatch(task) {
  if (!task || !task.id) return
  const index = tasks.value.findIndex((item) => item.id === task.id)
  if (index >= 0) {
    tasks.value.splice(index, 1, task)
  } else {
    tasks.value.push(task)
  }
}

async function startTask(task) {
  busyId.value = task.id
  const prevStatusCode = task.status_code
  const prevStatus = task.status
  const inProgress = statuses.value.find((status) => status.code === 'in_progress')
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
    await Promise.all([load(), loadTaskCounts(), workload.refresh()])
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

async function pauseTask(task) {
  busyId.value = task.id
  const { ok, data, error } = await tasksApi.pauseTask(task.id)
  if (ok) {
    applyTaskPatch(data)
    await Promise.all([load(), loadTaskCounts(), workload.refresh()])
    toasts.success('Задача приостановлена')
  } else {
    toasts.error(error || 'Не удалось приостановить задачу')
  }
  busyId.value = null
}

async function confirmComplete() {
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
    await Promise.all([
      load(),
      loadTaskCounts(),
      viewMode.value === 'history' ? loadHistory() : Promise.resolve(),
      workload.refresh(),
    ])
    toasts.success('Задача завершена')
    closeCompleteModal()
  } else {
    workload.refresh()
    toasts.error(error || 'Не удалось завершить задачу')
  }
  busyId.value = null
}

function openWorkflow(task) {
  router.push({ name: 'task-workflow', params: { id: task.id } })
}

watch([statusFilter, typeFilter], async () => {
  activePage.value = 1
  await Promise.all([load(), loadTaskCounts()])
})

watch(activePage, async () => {
  await load()
})

watch(historyPage, async () => {
  if (viewMode.value === 'history') {
    await loadHistory()
  }
})

onMounted(async () => {
  await Promise.all([loadLookups(), load()])
  await loadTaskCounts()
  if (auth.isStaff) {
    workload.refresh()
  }
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

.tag--cancelled {
  background: rgba(255, 111, 134, 0.14);
  color: #ffd4dc;
  border-color: rgba(255, 111, 134, 0.22);
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
