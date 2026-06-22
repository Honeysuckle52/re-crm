<template>
  <section class="stack">
    <div class="hero task-hero">
      <div class="task-hero__row">
        <div class="task-hero__intro">
          <div class="hero__eyebrow">Задачи</div>
          <h1 class="h2 task-hero__title">Рабочие задачи</h1>
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
        <button class="btn btn--accent" @click="toggleForm">
          {{ showForm ? 'Скрыть форму' : '+ Новая задача' }}
        </button>
      </div>
    </div>

    <form v-if="showForm" class="panel panel--light stack" @submit.prevent="submitTaskForm">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">
            {{ isEditingTask ? `Редактирование задачи #${editingTaskId}` : 'Создание задачи' }}
          </h2>
          <div class="muted">
            {{ isEditingTask
              ? 'Измените заголовок, исполнителя, сроки и связанные сущности, затем сохраните карточку задачи.'
              : 'Создайте новую рабочую задачу и сразу привяжите её к клиенту, заявке или объекту при необходимости.' }}
          </div>
        </div>
      </div>

      <div class="grid grid--3 task-form__grid">
        <div class="field">
          <label>Заголовок</label>
          <input v-model="form.title" class="input" required />
        </div>

        <RemoteLookupField
          v-model="form.assignee"
          label="Исполнитель"
          placeholder="Найти сотрудника по ФИО"
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
          placeholder="Найти заявку по клиенту или объекту"
          endpoint="/requests/"
          :params="{ ordering: '-updated_at' }"
          :map-option="mapRequestOption"
          no-results-text="Заявки не найдены."
        />

        <RemoteLookupField
          v-model="form.client"
          label="Клиент"
          placeholder="Найти клиента по ФИО"
          endpoint="/users/"
          :params="{ user_type: 'client' }"
          :map-option="mapClientOption"
        />

        <div class="field task-form__property">
          <label>Связанный объект</label>
          <div class="row task-form__property-actions">
            <button class="btn btn--sm btn--accent" type="button" @click="propertyPickerOpen = true">
              {{ form.property ? 'Изменить объект' : 'Выбрать объект' }}
            </button>
            <button v-if="form.property" class="btn btn--sm" type="button" @click="clearSelectedProperty">
              Сбросить
            </button>
          </div>
          <div class="muted task-form__property-label">
            {{ form.property ? selectedPropertyLabel : 'Объект ещё не выбран.' }}
          </div>
        </div>
      </div>

      <div class="field">
        <label>Описание</label>
        <textarea v-model="form.description" class="textarea" rows="3"></textarea>
      </div>

      <div class="row task-form__actions" style="gap: 10px; flex-wrap: wrap">
        <button
          v-if="isEditingTask && editingTaskItem && canDeleteTask(editingTaskItem)"
          class="btn btn--danger"
          type="button"
          @click="removeTask(editingTaskItem)"
        >
          Удалить
        </button>
        <button v-if="isEditingTask" class="btn" type="button" @click="cancelTaskForm">
          Отмена
        </button>
        <button class="btn btn--accent" type="submit">
          {{ isEditingTask ? 'Сохранить задачу' : 'Создать задачу' }}
        </button>
      </div>
    </form>


    <div class="panel panel--light">
      <div class="surface-head tasks-head">
        <div class="surface-head__meta">
          <h2 class="h3">Фильтры</h2>
          <div class="muted">
            Поиск по ФИО, заявке, объекту, типу, статусу и дате создания.
          </div>
        </div>
        <button class="btn btn--sm btn--ghost" type="button" @click="resetFilters">
          Сбросить
        </button>
      </div>

      <div class="grid grid--4 task-filters-grid">
        <div class="field task-filters-grid__search">
          <label>Поиск</label>
          <input
            v-model.trim="searchFilter"
            class="input"
            type="search"
            placeholder="ФИО клиента, исполнителя или объект"
          />
        </div>

        <div class="field">
          <label>Статус</label>
          <select v-model="statusFilter" class="select">
            <option value="">Все статусы</option>
            <option v-for="status in visibleStatuses" :key="status.id" :value="String(status.id)">
              {{ status.name }}
            </option>
          </select>
        </div>

        <div class="field">
          <label>Тип</label>
          <select v-model="typeFilter" class="select">
            <option value="">Все типы</option>
            <option v-for="taskType in taskTypes" :key="taskType.code" :value="taskType.code">
              {{ taskType.name }}
            </option>
          </select>
        </div>

        <div class="field">
          <label>Операция</label>
          <select v-model="operationFilter" class="select">
            <option value="">Все операции</option>
            <option v-for="operation in operations" :key="operation.id" :value="String(operation.id)">
              {{ operation.name }}
            </option>
          </select>
        </div>

        <div class="field">
          <label>Создана от</label>
          <input v-model="dateFromFilter" class="input" type="date" />
        </div>

        <div class="field">
          <label>Создана до</label>
          <input v-model="dateToFilter" class="input" type="date" />
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Активные задачи</h2>
          <div class="muted">
            Показано {{ filtered.length }} из {{ activeFilteredCount }} задач.
          </div>
        </div>
      </div>

      <BulkActionBar
        :count="selectedTaskCount"
        label="задач"
        @clear="clearTaskSelection"
      >
        <select v-model="bulkTaskActionCode" class="select select--sm">
          <option value="pause">Пауза</option>
          <option value="complete">Завершить</option>
          <option value="delete">Удалить</option>
        </select>
        <button
          class="btn btn--sm btn--primary"
          type="button"
          @click="runBulkTaskAction"
        >
          Применить
        </button>
      </BulkActionBar>

      <DataFetchPanel
        v-if="tasksLoadError && filtered.length"
        class="table-state"
        compact
        :error="tasksLoadError"
        error-title="Список активных задач обновлён не полностью"
        @retry="reloadTaskBoard"
      />

      <DataFetchPanel
        v-else-if="loadingTasks && filtered.length"
        class="table-state"
        compact
        loading
        loading-title="Обновление задач"
        loading-text="Подтягиваем свежие данные по активным задачам."
      />

      <DataFetchPanel
        v-if="loadingTasks && !filtered.length"
        loading
        loading-title="Загрузка задач"
        loading-text="Подтягиваем активные задачи и их статусы."
      />

      <DataFetchPanel
        v-else-if="tasksLoadError && !filtered.length"
        :error="tasksLoadError"
        error-title="Не удалось загрузить активные задачи"
        @retry="reloadTaskBoard"
      />

      <div v-else class="table-wrap task-table-wrap">
        <table class="table tasks-table table--responsive-cards">
          <colgroup>
            <col class="tasks-table__col tasks-table__col--check" />
            <col class="tasks-table__col tasks-table__col--title" />
            <col class="tasks-table__col tasks-table__col--type" />
            <col class="tasks-table__col tasks-table__col--assignee" />
            <col class="tasks-table__col tasks-table__col--request" />
            <col class="tasks-table__col tasks-table__col--priority" />
            <col class="tasks-table__col tasks-table__col--due" />
            <col class="tasks-table__col tasks-table__col--status" />
            <col class="tasks-table__col tasks-table__col--actions" />
          </colgroup>
          <thead>
            <tr>
              <th class="table-check-cell">
                <input
                  type="checkbox"
                  :checked="allTasksOnPageSelected"
                  @change="toggleTasksPageSelection($event.target.checked)"
                />
              </th>
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
              <td class="table-check-cell" data-label="Выбор">
                <input
                  type="checkbox"
                  :checked="isTaskSelected(task)"
                  @change="toggleTaskSelection(task, $event.target.checked)"
                />
              </td>
              <td data-label="Заголовок">
                <b>{{ task.title }}</b>
                <div v-if="task.client_name || task.request_client_name" class="muted task-subline">
                  Клиент: {{ task.client_name !== '—' ? task.client_name : task.request_client_name }}
                </div>
                <div v-if="task.property_title" class="muted task-subline">
                  Объект: {{ task.property_title }}
                </div>
                <div
                  v-if="task.task_type === 'showing'"
                  class="payment-pill"
                  :class="task.showing_payment_status === 'paid' ? 'is-paid' : 'is-pending'"
                >
                  <span>
                    {{ task.showing_payment_status === 'paid' ? 'Предоплата подтверждена' : 'Ожидается предоплата' }}
                  </span>
                  <span v-if="task.showing_payment_amount">
                    {{ formatMoney(task.showing_payment_amount) }} ₽
                  </span>
                </div>
              </td>
              <td data-label="Тип">
                <span class="tag tag--type task-badge task-badge--type-full">
                  {{ task.task_type_display || taskTypeLabel(task.task_type) }}
                </span>
              </td>
              <td data-label="Исполнитель">
                <div class="assignee-cell">
                  <span class="assignee-name">{{ task.assignee_name || '—' }}</span>
                  <TaskMineBadge :task="task" :user-id="auth.user?.id" mode="full" />
                </div>
              </td>
              <td class="task-request-cell" data-label="Заявка">
                <router-link
                  v-if="task.request"
                  :to="`/requests/${task.request}`"
                  class="task-request-link"
                >
                  №{{ task.request }}
                </router-link>
                <span v-else class="muted">—</span>
              </td>
              <td data-label="Приоритет">
                <span class="tag task-badge" :class="priorityClass(task.priority)">
                  {{ priorityLabel(task.priority) }}
                </span>
              </td>
              <td class="muted" data-label="Срок">
                <div class="task-due-cell">
                  <span class="task-due-date">{{ task.due_date ? formatDate(task.due_date) : '—' }}</span>
                  <span v-if="task.is_overdue" class="tag overdue">просрочено</span>
                </div>
              </td>
              <td data-label="Статус">
                <div class="task-status-cell">
                  <span class="tag tag--accent task-badge task-badge--truncate">{{ task.status_name }}</span>
                  <div
                    v-if="task.is_auto_closed"
                    class="auto-closed-badge"
                    title="Задача закрыта автоматически"
                  >
                    авто
                  </div>
                </div>
              </td>
              <td class="table-actions-cell" data-label="Действия">
                <div class="task-actions">
                  <div class="task-actions__primary">
                    <button
                      v-if="canViewTask(task)"
                      class="btn btn--sm btn--primary task-actions__wide"
                      @click="openWorkflow(task)"
                    >
                      Открыть
                    </button>
                    <button
                      v-else-if="canStart(task)"
                      class="btn btn--sm btn--accent task-actions__wide"
                      :disabled="!canStartBtn(task) || busyId === task.id"
                      :title="!canStartBtn(task) ? 'У сотрудника уже есть задача в работе' : 'Взять в работу'"
                      @click="startTask(task)"
                    >
                      Старт
                    </button>
                    <div
                      v-else-if="task.task_type === 'showing' && !canComplete(task) && isOwnOrManaged(task)"
                      class="task-actions__info"
                    >
                      Нужна оплата
                    </div>
                  </div>

                  <select
                    class="select select--sm task-actions__status"
                    :value="task.status"
                    @change="changeStatus(task, $event.target.value)"
                  >
                    <option disabled value="">Статус...</option>
                    <option v-for="status in statuses" :key="status.id" :value="status.id">
                      {{ status.name }}
                    </option>
                  </select>

                  <div
                    v-if="hasTaskMenu(task)"
                    class="task-more"
                    :class="{ 'is-open': moreMenuId === task.id }"
                  >
                    <button
                      class="btn btn--sm task-more__trigger"
                      :disabled="busyId === task.id"
                      @click.stop="moreMenuId = moreMenuId === task.id ? null : task.id"
                      aria-label="Еще действия"
                    >
                      ...
                    </button>
                    <div class="task-more__menu" @click.stop>
                      <button
                        v-if="canEditTask(task)"
                        class="task-more__item"
                        :disabled="busyId === task.id"
                        @click="startEditTask(task); moreMenuId = null"
                      >
                        Редактировать
                      </button>
                      <button
                        v-if="canPause(task)"
                        class="task-more__item"
                        :disabled="busyId === task.id"
                        @click="pauseTask(task); moreMenuId = null"
                      >
                        Пауза
                      </button>
                      <button
                        v-if="canComplete(task)"
                        class="task-more__item"
                        :disabled="busyId === task.id"
                        @click="openCompleteModal(task); moreMenuId = null"
                      >
                        Завершить
                      </button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!filtered.length" class="empty">Активных задач нет.</div>

      <ListPagination
        v-if="activeFilteredCount > filtered.length"
        :count="activeFilteredCount"
        :page="activePage"
        :visible-count="filtered.length"
        :page-size="taskPageSize"
        label="задач"
        @change="setActivePage"
        @change-page-size="setTaskPageSize"
      />
    </div>

    <PropertyPickerModal
      v-if="propertyPickerOpen"
      title="Выбор объекта для задачи"
      :selected-id="form.property"
      :params="{ ordering: '-created_at' }"
      @close="propertyPickerOpen = false"
      @select="selectProperty"
    />



    <Teleport to="body">
      <div v-if="completeModal.show" class="modal-overlay" @click.self="closeCompleteModal">
        <div class="modal">
          <h3 class="h3">Завершение задачи</h3>
          <p class="muted" style="margin-top: 8px">
            {{ completeModal.task?.title }}
          </p>
          <div
            v-if="completeModal.task?.task_type === 'showing' && completeModal.task?.showing_payment_status !== 'paid'"
            class="payment-modal-warning"
          >
            Завершение показа заблокировано, пока предоплата просмотра не подтверждена.
          </div>
          <div class="field" style="margin-top: 16px">
            <label>Результат выполнения</label>
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
              :disabled="busyId === completeModal.task?.id || (completeModal.task?.task_type === 'showing' && completeModal.task?.showing_payment_status !== 'paid')"
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
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { bulkTaskAction } from '../api/bulk'
import * as tasksApi from '../api/tasks'
import BulkActionBar from '../components/BulkActionBar.vue'
import DataFetchPanel from '../components/DataFetchPanel.vue'
import ListPagination from '../components/ListPagination.vue'
import PropertyPickerModal from '../components/PropertyPickerModal.vue'
import RemoteLookupField from '../components/RemoteLookupField.vue'
import TaskMineBadge from '../components/TaskMineBadge.vue'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { useBulkSelection } from '../composables/useBulkSelection'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { formatDateShort as formatDate, formatMoney } from '@/utils/formatters'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const confirm = useConfirmStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()
const route = useRoute()
const router = useRouter()

const tasks = ref([])
const history = ref([])
const statuses = ref([])
const operations = ref([])

const searchFilter = ref('')
const statusFilter = ref('')
const typeFilter = ref('')
const operationFilter = ref('')
const dateFromFilter = ref('')
const dateToFilter = ref('')
const showForm = ref(false)
const busyId = ref(null)
const viewMode = ref('active')
const activePage = ref(1)
const historyPage = ref(1)
const taskPageSize = ref(DEFAULT_PAGE_SIZE)
const loadingTasks = ref(false)
const loadingHistory = ref(false)
const editingTaskId = ref(null)
const propertyPickerOpen = ref(false)
const selectedPropertyLabel = ref('')
const activeTotalCount = ref(0)
const activeFilteredCount = ref(0)
const historyTotalCount = ref(0)
const tasksLoadError = ref('')
const historyLoadError = ref('')
const bulkTaskActionCode = ref('pause')
const taskFormBaseline = ref('')
const taskDraftRestored = ref(false)
const moreMenuId = ref(null)

const taskTypes = [
  { code: 'contact_client', name: 'Связаться с клиентом' },
  { code: 'property_search', name: 'Подбор объектов' },
  { code: 'showing', name: 'Показ объекта' },
  { code: 'documents', name: 'Подготовка документов' },
  { code: 'call', name: 'Звонок' },
  { code: 'other', name: 'Прочее' },
]

const completeModal = reactive({ show: false, task: null, result: '' })

function closeMoreMenu() {
  moreMenuId.value = null
}

onMounted(() => {
  document.addEventListener('click', closeMoreMenu)
})
onUnmounted(() => {
  document.removeEventListener('click', closeMoreMenu)
})

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
const isEditingTask = computed(() => editingTaskId.value !== null)
const editingTaskItem = computed(() => tasks.value.find((item) => item.id === editingTaskId.value) || null)
const taskFormSnapshot = computed(() => JSON.stringify({ ...form }))
const isTaskFormDirty = computed(() => (
  showForm.value && taskFormSnapshot.value !== taskFormBaseline.value
))

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

function toDatetimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offsetMs = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

function syncTaskFormBaseline() {
  taskFormBaseline.value = taskFormSnapshot.value
}

function isTaskDraftEmpty(draft) {
  const formData = draft?.form || {}
  return !Object.entries(formData)
    .filter(([key]) => !['priority', 'task_type'].includes(key))
    .some(([, value]) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== '' && value !== null && value !== undefined
    })
}

const { clearDraft: clearTaskDraft } = useDraftPersistence({
  key: 'tasks:create',
  enabled: () => showForm.value && !isEditingTask.value,
  getData: () => ({ form: { ...form } }),
  applyData: (draft) => {
    taskDraftRestored.value = true
    Object.assign(form, defaultForm(), draft?.form || {})
    toasts.info('Черновик задачи восстановлен')
  },
  isEmpty: isTaskDraftEmpty,
})

const { confirmLeave: confirmTaskFormLeave } = useUnsavedChangesGuard({
  enabled: () => showForm.value,
  isDirty: () => isTaskFormDirty.value,
  message: 'Есть несохранённые изменения в форме задачи. Покинуть страницу?',
})

function resetTaskForm() {
  editingTaskId.value = null
  Object.assign(form, defaultForm())
  selectedPropertyLabel.value = ''
}

function cancelTaskForm() {
  if (!confirmTaskFormLeave()) return
  showForm.value = false
  clearTaskDraft()
  resetTaskForm()
  syncTaskFormBaseline()
}

function fillTaskForm(task) {
  editingTaskId.value = task.id
  Object.assign(form, {
    title: task.title || '',
    description: task.description || '',
    assignee: task.assignee ?? null,
    priority: task.priority || 'normal',
    task_type: task.task_type || 'other',
    due_date: toDatetimeLocal(task.due_date),
    request: task.request ?? null,
    client: task.client ?? null,
    property: task.property ?? null,
  })
  selectedPropertyLabel.value = task.property ? (task.property_title || `Объект #${task.property}`) : ''
}

const TERMINAL_CODES = ['done', 'cancelled']

const activeTasks = computed(() => tasks.value)
const activeStatuses = computed(() => (
  statuses.value.filter((status) => !TERMINAL_CODES.includes(status.code))
))
const historyStatuses = computed(() => (
  statuses.value.filter((status) => TERMINAL_CODES.includes(status.code))
))
const visibleStatuses = computed(() => (
  viewMode.value === 'history' ? historyStatuses.value : activeStatuses.value
))
const filtered = computed(() => activeTasks.value)
const activeCount = computed(() => activeTotalCount.value)
const historyCount = computed(() => historyTotalCount.value)
const {
  selectedIds: selectedTaskIds,
  selectedCount: selectedTaskCount,
  allOnPageSelected: allTasksOnPageSelected,
  isSelected: isTaskSelected,
  toggleSelection: toggleTaskSelection,
  togglePageSelection: toggleTasksPageSelection,
  clearSelection: clearTaskSelection,
} = useBulkSelection(filtered)

function displayName(user) {
  return user.full_name && user.full_name !== '—'
    ? user.full_name
    : (user.email || `Пользователь #${user.id}`)
}

function mapAssigneeOption(user) {
  return {
    id: user.id,
    label: displayName(user),
    hint: assigneeRoleLabel(user),
  }
}

function assigneeRoleLabel(user) {
  if (user.role_name) {
    const normalized = String(user.role_name).trim().toLowerCase()
    if (normalized.includes('админ')) return 'Админ'
    if (normalized.includes('менедж')) return 'Менеджер'
    if (normalized.includes('агент')) return 'Агент'
  }
  if (user.is_admin) return 'Админ'
  if (user.is_manager) return 'Менеджер'
  return 'Агент'
}

function mapClientOption(user) {
  return {
    id: user.id,
    label: displayName(user),
    hint: '',
  }
}

function mapRequestOption(request) {
  return {
    id: request.id,
    label: `Заявка #${request.id}`,
    hint: [
      request.client_full_name || request.client_username,
      request.property_title,
    ].filter(Boolean).join(' · '),
  }
}

function selectProperty(property) {
  form.property = property.id
  selectedPropertyLabel.value = `${property.title || `Объект #${property.id}`}${property.full_address ? ` · ${property.full_address}` : ''}`
  propertyPickerOpen.value = false
}

function clearSelectedProperty() {
  form.property = null
  selectedPropertyLabel.value = ''
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
  if (showForm.value) {
    cancelTaskForm()
    return
  }
  taskDraftRestored.value = false
  resetTaskForm()
  showForm.value = true
  syncTaskFormBaseline()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function baseTaskFilterParams() {
  const params = {}
  if (searchFilter.value) params.search = searchFilter.value
  if (typeFilter.value) params.task_type = typeFilter.value
  if (operationFilter.value) params.operation_type = Number(operationFilter.value)
  if (dateFromFilter.value) params.date_from = dateFromFilter.value
  if (dateToFilter.value) params.date_to = dateToFilter.value
  return params
}

function activeListParams({ includeStatusFilter = true, page = activePage.value } = {}) {
  const params = {
    ...baseTaskFilterParams(),
    status_code: 'new,in_progress,waiting',
    page,
    page_size: taskPageSize.value,
  }
  if (includeStatusFilter && statusFilter.value) {
    params.status = Number(statusFilter.value)
  }
  return params
}

function historyListParams({ includeStatusFilter = true, page = historyPage.value } = {}) {
  const params = {
    ...baseTaskFilterParams(),
    status_code: 'done,cancelled',
    ordering: '-completed_at',
    page,
    page_size: taskPageSize.value,
  }
  if (includeStatusFilter && statusFilter.value) {
    params.status = Number(statusFilter.value)
  }
  if (!auth.isManager) {
    params.assignee = 'me'
  }
  return params
}

async function load() {
  loadingTasks.value = true
  tasksLoadError.value = ''
  try {
    const { data } = await api.get('/tasks/', { params: activeListParams() })
    const payload = unpackPaginated(data)
    tasks.value = payload.items
    activeFilteredCount.value = payload.count
  } catch (err) {
    tasksLoadError.value = extractError(err, 'Не удалось загрузить задачи')
    toasts.error(tasksLoadError.value)
  } finally {
    loadingTasks.value = false
  }
}

async function loadLookups() {
  try {
    const [statusesResponse, operationsResponse] = await Promise.all([
      api.get('/task-statuses/', {
        params: { page_size: LOOKUP_PAGE_SIZE },
      }),
      api.get('/operation-types/', {
        params: { page_size: LOOKUP_PAGE_SIZE },
      }),
    ])
    statuses.value = unpackPaginated(statusesResponse.data).items
    operations.value = unpackPaginated(operationsResponse.data).items
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить справочники задач'))
  }
}

async function loadHistory() {
  loadingHistory.value = true
  historyLoadError.value = ''
  try {
    const { data } = await api.get('/tasks/', { params: historyListParams() })
    const payload = unpackPaginated(data)
    history.value = payload.items
    historyTotalCount.value = payload.count
  } catch (err) {
    historyLoadError.value = extractError(err, 'Не удалось загрузить историю задач')
    toasts.error(historyLoadError.value)
  } finally {
    loadingHistory.value = false
  }
}

function setViewMode(mode) {
  viewMode.value = mode
  statusFilter.value = ''
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
  try {
    const baseActiveParams = activeListParams({
      includeStatusFilter: false,
      page: 1,
    })
    const baseHistoryParams = historyListParams({
      includeStatusFilter: false,
      page: 1,
    })

    const [activeTotal, historyTotal] = await Promise.all([
      fetchTaskCount(baseActiveParams),
      fetchTaskCount(baseHistoryParams),
    ])

    activeTotalCount.value = activeTotal
    historyTotalCount.value = historyTotal
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось обновить счётчики задач'))
  }
}

function setActivePage(page) {
  if (page < 1 || page === activePage.value) return
  activePage.value = page
}

function setHistoryPage(page) {
  if (page < 1 || page === historyPage.value) return
  historyPage.value = page
}

function setTaskPageSize(size) {
  if (!size || size === taskPageSize.value) return
  taskPageSize.value = size
}

function resetFilters() {
  searchFilter.value = ''
  statusFilter.value = ''
  typeFilter.value = ''
  operationFilter.value = ''
  dateFromFilter.value = ''
  dateToFilter.value = ''
}

async function submitTaskForm() {
  if (!form.assignee) {
    toasts.error('Выберите исполнителя задачи')
    return
  }

  const wasEditing = isEditingTask.value
  const payload = { ...form }
  if (wasEditing) {
    if (!payload.due_date) payload.due_date = null
  } else if (!payload.due_date) {
    delete payload.due_date
  }
  if (!wasEditing && !payload.request) delete payload.request
  if (!wasEditing && !payload.client) delete payload.client
  if (!wasEditing && !payload.property) delete payload.property

  try {
    const result = wasEditing
      ? await tasksApi.patchTask(editingTaskId.value, payload)
      : await tasksApi.createTask(payload)
    if (!result.ok) {
      toasts.error(
        result.error || (wasEditing ? 'Не удалось обновить задачу' : 'Не удалось создать задачу'),
      )
      return
    }
    showForm.value = false
    clearTaskDraft()
    resetTaskForm()
    syncTaskFormBaseline()
    toasts.success(wasEditing ? 'Задача обновлена' : 'Задача создана')
    activePage.value = 1
    await Promise.all([load(), loadTaskCounts(), workload.refresh()])
  } catch (err) {
    toasts.error(extractError(err, wasEditing ? 'Не удалось обновить задачу' : 'Не удалось создать задачу'))
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

function canViewTask(task) {
  return isOwnOrManaged(task)
}

function canEditTask(task) {
  return isOwnOrManaged(task) && !TERMINAL_CODES.includes(task.status_code)
}

function canDeleteTask(task) {
  return isOwnOrManaged(task) && !TERMINAL_CODES.includes(task.status_code)
}

function canStart(task) {
  return isOwnOrManaged(task) && ['new', 'waiting'].includes(task.status_code)
}

function canPause(task) {
  return isOwnOrManaged(task) && task.status_code === 'in_progress'
}

function canComplete(task) {
  if (task.task_type === 'showing' && task.showing_payment_status !== 'paid') return false
  return isOwnOrManaged(task) && ['new', 'in_progress', 'waiting'].includes(task.status_code)
}

function canStartBtn(task) {
  if (auth.isManager) return true
  if (task.assignee !== auth.user?.id) return false
  return workload.workload.in_progress_tasks < workload.workload.max_in_progress_tasks
}

function hasTaskMenu(task) {
  return canEditTask(task) || canPause(task) || canComplete(task)
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
    const conflictMessage = tasksApi.normalizeTaskError?.(error, data)
    toasts.error(
      conflictMessage
        || error
        || 'Нельзя стартовать задачу: превышен лимит',
    )
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

function startEditTask(task) {
  taskDraftRestored.value = false
  fillTaskForm(task)
  showForm.value = true
  syncTaskFormBaseline()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function removeTask(task) {
  const approved = await confirm.ask({
    title: 'Удаление задачи',
    message: `Удалить задачу «${task.title}»?`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  busyId.value = task.id
  const { ok, error } = await tasksApi.deleteTask(task.id)
  if (ok) {
    if (editingTaskId.value === task.id) {
      cancelTaskForm()
    }
    tasks.value = tasks.value.filter((item) => item.id !== task.id)
    history.value = history.value.filter((item) => item.id !== task.id)
    await Promise.all([
      load(),
      loadTaskCounts(),
      viewMode.value === 'history' ? loadHistory() : Promise.resolve(),
      workload.refresh(),
    ])
    toasts.success('Задача удалена')
  } else {
    toasts.error(error || 'Не удалось удалить задачу')
  }
  busyId.value = null
}

async function runBulkTaskAction() {
  if (!selectedTaskIds.value.length) return
  const actionLabel = {
    pause: 'приостановить',
    complete: 'завершить',
    delete: 'удалить',
  }[bulkTaskActionCode.value] || 'обработать'
  const approved = await confirm.ask({
    title: 'Массовое действие по задачам',
    message: `${actionLabel} выбранные задачи (${selectedTaskIds.value.length})?`,
    confirmLabel: 'Применить',
    danger: bulkTaskActionCode.value === 'delete',
  })
  if (!approved) return

  const result = await bulkTaskAction(
    [...selectedTaskIds.value],
    bulkTaskActionCode.value,
  )
  if (!result.ok) {
    toasts.error(result.error || 'Не удалось выполнить массовое действие по задачам')
    return
  }

  clearTaskSelection()
  await Promise.all([load(), loadTaskCounts(), workload.refresh()])
  const {
    processed,
    errors = [],
    not_found_ids: notFoundIds = [],
  } = result.data
  if (errors.length || notFoundIds.length) {
    toasts.warn(
      `Обработано задач: ${processed}. Пропущено: ${errors.length + notFoundIds.length}.`,
    )
    return
  }
  toasts.success(`Обработано задач: ${processed}.`)
}

async function reloadTaskBoard() {
  await Promise.all([
    load(),
    loadTaskCounts(),
    viewMode.value === 'history' ? loadHistory() : Promise.resolve(),
    auth.isStaff ? workload.refresh() : Promise.resolve(),
  ])
}

watch([searchFilter, statusFilter, typeFilter, operationFilter, dateFromFilter, dateToFilter], async () => {
  activePage.value = 1
  historyPage.value = 1
  await Promise.all([
    load(),
    loadTaskCounts(),
    viewMode.value === 'history' ? loadHistory() : Promise.resolve(),
  ])
})

watch(activePage, async () => {
  await load()
})

watch(historyPage, async () => {
  if (viewMode.value === 'history') {
    await loadHistory()
  }
})

watch(taskPageSize, async () => {
  const changedActivePage = activePage.value !== 1
  const changedHistoryPage = historyPage.value !== 1
  if (changedActivePage) activePage.value = 1
  if (changedHistoryPage) historyPage.value = 1
  if (changedActivePage || changedHistoryPage) {
    return
  }
  await Promise.all([
    load(),
    viewMode.value === 'history' ? loadHistory() : Promise.resolve(),
  ])
})

onMounted(async () => {
  // Если пришли с ?view=history (например, из TaskWorkflow после завершения)
  // — сразу открываем вкладку истории.
  if (route.query.view === 'history') {
    viewMode.value = 'history'
  }
  await Promise.all([loadLookups(), load()])
  await loadTaskCounts()
  if (viewMode.value === 'history') {
    await loadHistory()
  }
  if (!taskDraftRestored.value) {
    syncTaskFormBaseline()
  }
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

.tasks-head {
  margin-bottom: 12px;
}

.task-hero {
  padding: 24px 28px;
}

.task-hero__row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.task-hero__intro {
  min-width: 0;
}

.task-hero__title {
  color: #fff;
  margin-top: 8px;
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

.task-form__grid {
  align-items: start;
}

.task-form__property-actions {
  gap: 8px;
  flex-wrap: wrap;
}

.task-form__property-label {
  margin-top: 8px;
}

.task-form__actions {
  justify-content: flex-end;
}

.task-filters-grid {
  align-items: end;
  grid-template-columns: minmax(240px, 1.4fr) repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.task-filters-grid__search {
  min-width: 0;
}

.task-form__grid .select,
.task-filters-grid .select {
  color-scheme: light;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)),
    linear-gradient(45deg, transparent 50%, var(--c-accent) 50%),
    linear-gradient(135deg, var(--c-accent) 50%, transparent 50%);
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 20px rgba(16, 55, 52, 0.08);
}

.task-form__grid .select option,
.task-filters-grid .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.table-check-cell {
  width: 44px;
  min-width: 44px;
  max-width: 44px;
  text-align: center;
}

.table-check-cell input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.tasks-table {
  table-layout: fixed;
}

.tasks-table__col--check {
  width: 44px;
}

.tasks-table__col--title {
  width: 23%;
}

.tasks-table__col--type {
  width: 12%;
}

.tasks-table__col--assignee {
  width: 12%;
}

.tasks-table__col--request {
  width: 8%;
}

.tasks-table__col--priority {
  width: 8%;
}

.tasks-table__col--due {
  width: 10%;
}

.tasks-table__col--status {
  width: 9%;
}

.tasks-table__col--actions {
  width: 320px;
}

.task-actions {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  min-width: 0;
}

.task-actions__primary {
  display: flex;
  flex: 1 1 0;
  min-width: 0;
}

.task-actions__wide {
  width: 100%;
  min-width: 92px;
  white-space: nowrap;
}

.task-actions__status {
  flex: 0 0 136px;
  min-width: 136px;
  color: var(--c-page-text);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)),
    linear-gradient(45deg, transparent 50%, var(--c-accent) 50%),
    linear-gradient(135deg, var(--c-accent) 50%, transparent 50%);
  border-color: rgba(21, 56, 57, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 20px rgba(16, 55, 52, 0.08);
}

.task-actions__info {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0 10px;
  border-radius: 12px;
  background: rgba(255, 111, 134, 0.12);
  color: #ffd4dc;
  font-size: 12px;
  font-weight: 700;
}

.task-actions--history {
  min-width: 80px;
  flex-wrap: nowrap;
}

.task-more {
  position: relative;
  flex: 0 0 auto;
}

.task-more__trigger {
  font-size: 15px;
  letter-spacing: 0.08em;
  padding-left: 10px;
  padding-right: 10px;
  min-width: 36px;
}

.task-more__menu {
  display: none;
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 60;
  min-width: 156px;
  border-radius: 14px;
  border: 1px solid var(--c-border-strong);
  background: var(--grad-panel);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: 0 16px 36px rgba(4, 24, 22, 0.28);
  overflow: hidden;
  padding: 4px;
}

.task-more.is-open .task-more__menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-more__item {
  display: block;
  width: 100%;
  padding: 9px 14px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: var(--c-text);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.task-more__item:hover:not(:disabled) {
  background: rgba(99, 208, 197, 0.1);
  color: #effffd;
}

.task-request-cell {
  min-width: 110px;
  white-space: nowrap;
}

.task-request-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  max-width: 120px;
  min-height: 38px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(21, 56, 57, 0.16);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
  color: var(--c-page-text);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  text-decoration: none;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 8px 18px rgba(16, 55, 52, 0.08);
}

.task-section-head {
  margin-bottom: 14px;
}

.task-table-wrap .table {
  min-width: 1320px;
}

.task-history-wrap .table {
  min-width: 820px;
}

.task-table-wrap .table th,
.task-history-wrap .table th {
  padding: 0 16px 14px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.task-table-wrap .table td,
.task-history-wrap .table td {
  padding: 14px 16px;
  font-size: 14px;
  vertical-align: middle;
}

.task-badge,
.task-badge.tag--type,
.task-badge.tag--accent,
.task-badge.tag--panel,
.task-badge.tag--cancelled {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(21, 56, 57, 0.16);
  background: var(--grad-control-light);
  color: var(--c-page-text);
  box-shadow: 0 8px 18px rgba(16, 55, 52, 0.08);
  white-space: nowrap;
}

.task-badge--truncate {
  display: inline-flex;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-badge--type-full {
  display: flex;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  white-space: normal;
  text-align: center;
  line-height: 1.2;
  overflow-wrap: anywhere;
  word-break: break-word;
  hyphens: auto;
  padding: 9px 12px;
  border-radius: 18px;
  justify-content: center;
}

.task-type-cell {
  min-width: 0;
}

.tag--type {
  background: rgba(99, 208, 197, 0.14);
  color: #effffd;
  border-color: rgba(99, 208, 197, 0.2);
}

.tag--cancelled {
  background: rgba(255, 111, 134, 0.14);
  color: #ffd4dc;
  border-color: rgba(255, 111, 134, 0.22);
}

.overdue {
  margin-top: 6px;
  background: rgba(255, 111, 134, 0.14);
  color: #ffd4dc;
  border-color: rgba(255, 111, 134, 0.2);
}

.task-due-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  min-width: 0;
}

.task-due-date {
  white-space: nowrap;
}

.task-status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
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

.payment-pill {
  margin-top: 8px;
  display: inline-flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  min-height: 32px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.payment-pill.is-paid {
  background: rgba(99, 208, 197, 0.14);
  color: #9ef2d6;
  border: 1px solid rgba(99, 208, 197, 0.2);
}

.payment-pill.is-pending {
  background: rgba(255, 111, 134, 0.12);
  color: #ffd4dc;
  border: 1px solid rgba(255, 111, 134, 0.18);
}

.row--mine > td:first-child {
  box-shadow: inset 3px 0 0 rgba(31, 163, 154, 0.32);
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

.assignee-name {
  font-weight: 600;
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-subline {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-subline--gap {
  margin-top: 4px;
}

.history-result {
  min-width: 140px;
  max-width: 200px;
}

.payment-modal-warning {
  margin-top: 14px;
  border: 1px solid rgba(255, 111, 134, 0.24);
  background: rgba(255, 111, 134, 0.12);
  color: #ffd6de;
  padding: 10px 14px;
  border-radius: 18px;
  font-size: 13px;
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

@media (max-width: 1100px) {
  .task-filters-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .task-filters-grid {
    grid-template-columns: 1fr;
  }

  .task-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .task-actions__primary {
    flex: 1 1 100%;
  }

  .task-actions__status {
    flex: 1 1 100%;
    min-width: 0;
  }

  .assignee-cell {
    align-items: flex-start;
  }

  .assignee-name,
  .task-subline {
    white-space: normal;
  }
}
</style>
