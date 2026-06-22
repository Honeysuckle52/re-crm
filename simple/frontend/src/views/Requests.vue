<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Заявки</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ auth.isStaff ? 'Заявки клиентов' : 'Мои заявки' }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            {{ auth.isStaff
              ? 'Распределяйте заявки между агентами, следите за воронкой и закрывайте обращения без потери контекста.'
              : 'Здесь собраны все ваши обращения в агентство и их текущий статус.' }}
          </div>
        </div>
        <button class="btn btn--accent" @click="toggleForm">
          {{ showForm ? 'Скрыть форму' : '+ Новая заявка' }}
        </button>
      </div>
    </div>

    <div v-if="auth.isStaff" class="panel panel--light">
      <div class="surface-head requests-head">
        <div class="surface-head__meta">
          <h2 class="h3">Область просмотра</h2>
          <div class="muted">
            Переключайтесь между общей очередью, неразобранными и своими заявками.
          </div>
        </div>
      </div>
      <div class="row requests-tabs" style="gap: 8px; flex-wrap: wrap">
        <button
          v-for="tab in staffTabs"
          :key="tab.value"
          class="btn btn--sm"
          :class="{ 'btn--primary': scope === tab.value }"
          @click="scope = tab.value"
        >
          {{ tab.label }} ({{ tab.count }})
        </button>
      </div>
    </div>

    <form v-if="showForm" class="panel panel--light stack" @submit.prevent="createRequest">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">
            {{ isEditingRequest ? `Редактирование заявки #${editingRequestId}` : 'Создание заявки' }}
          </h2>
          <div class="muted">
            {{ isEditingRequest
              ? 'Измените параметры заявки и сохраните обновлённую версию карточки.'
              : auth.isStaff
              ? 'Можно сразу назначить клиента, агента и привязать конкретный объект.'
              : 'Укажите параметры поиска и пожелания, после чего агент подхватит заявку в работу.' }}
          </div>
        </div>
      </div>

      <div class="grid grid--3 request-form__grid">
        <RemoteLookupField
          v-if="auth.isStaff"
          v-model="form.client"
          label="Клиент"
          placeholder="Найти клиента по логину, почте или телефону"
          endpoint="/users/"
          :params="{ user_type: 'client' }"
          :map-option="mapClientOption"
          :clearable="false"
        />
        <RemoteLookupField
          v-if="auth.isStaff"
          v-model="form.agent"
          label="Агент"
          placeholder="Найти сотрудника по логину, почте или имени"
          endpoint="/users/"
          :params="{ user_type: 'employee' }"
          :map-option="mapAgentOption"
        />
        <div class="field">
          <label>Операция</label>
          <select class="select" v-model.number="form.operation_type" required>
            <option v-for="operation in operations" :key="operation.id" :value="operation.id">
              {{ operation.name }}
            </option>
          </select>
        </div>
        <div class="field request-form__property">
          <label>Конкретный объект</label>
          <div class="row" style="gap: 8px; flex-wrap: wrap">
            <button class="btn btn--sm btn--accent" type="button" @click="propertyPickerOpen = true">
              {{ form.property ? 'Изменить объект' : 'Выбрать объект' }}
            </button>
            <button v-if="form.property" class="btn btn--sm" type="button" @click="clearSelectedProperty">
              Сбросить
            </button>
          </div>
          <div class="muted" style="margin-top: 8px">
            {{ form.property ? selectedPropertyLabel : 'Объект еще не выбран.' }}
          </div>
        </div>
        <div class="field">
          <label>Тип помещения</label>
          <select v-model="form.property_type" class="select">
            <option value="">Выберите тип</option>
            <option value="apartment">Квартира</option>
            <option value="house">Дом</option>
            <option value="commercial">Коммерческая недвижимость</option>
            <option value="land">Земельный участок</option>
            <option value="garage">Гараж</option>
            <option value="room">Комната</option>
          </select>
        </div>
        <div v-if="form.property_type === 'commercial'" class="field">
          <label>Площадь от</label>
          <input v-model.number="form.min_area" class="input" type="number" />
        </div>
        <div v-if="form.property_type === 'commercial'" class="field">
          <label>Площадь до</label>
          <input v-model.number="form.max_area" class="input" type="number" />
        </div>
        <div class="field">
          <label>Комнат</label>
          <input
            v-model.number="form.rooms_count"
            class="input"
            type="number"
            :disabled="isRequestRoomsDisabled"
            :placeholder="isRequestRoomsDisabled ? 'Не применяется' : ''" />
        </div>
        <div class="field request-form__budget">
          <label>Цена от / до</label>
          <div class="request-form__budget-row">
            <input v-model.number="form.min_price" class="input" type="number" />
            <input v-model.number="form.max_price" class="input" type="number" />
          </div>
        </div>
      </div>

      <div class="field">
        <label>Пожелания</label>
        <textarea v-model="form.description" class="textarea" rows="3"></textarea>
      </div>

      <div v-if="formError" class="error">{{ formError }}</div>

      <div class="row" style="justify-content: flex-end">
        <button v-if="isEditingRequest" class="btn" type="button" @click="cancelForm">
          Отмена
        </button>
        <button class="btn btn--accent" type="submit">
          {{ isEditingRequest ? 'Сохранить заявку' : 'Создать заявку' }}
        </button>
      </div>
    </form>

    <div class="panel panel--light">
      <div class="surface-head requests-head">
        <div class="surface-head__meta">
          <h2 class="h3">Фильтры</h2>
          <div class="muted">
            Отберите заявки по операции, статусу и дате создания.
          </div>
        </div>
        <button class="btn btn--sm btn--ghost" type="button" @click="resetFilters">
          Сбросить
        </button>
      </div>
      <div class="grid grid--4 request-filters-grid">
        <div class="field">
          <label>Операция</label>
          <select v-model="requestFilters.operation_type" class="select">
            <option value="">Все операции</option>
            <option
              v-for="operation in operations"
              :key="operation.id"
              :value="String(operation.id)"
            >
              {{ operation.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Статус</label>
          <select v-model="requestFilters.status" class="select">
            <option value="">Все статусы</option>
            <option
              v-for="status in statuses"
              :key="status.id"
              :value="String(status.id)"
            >
              {{ status.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Создана от</label>
          <input v-model="requestFilters.date_from" class="input" type="date" />
        </div>
        <div class="field">
          <label>Создана до</label>
          <input v-model="requestFilters.date_to" class="input" type="date" />
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Список заявок</h2>
          <div class="muted">
            Показано {{ visibleRequests.length }} из {{ requestCount }} заявок в текущем режиме.
          </div>
        </div>
      </div>

      <DataFetchPanel
        v-if="requestsLoadError && visibleRequests.length"
        class="table-state"
        compact
        :error="requestsLoadError"
        error-title="Список заявок загружен не полностью"
        @retry="reloadRequestsScreen"
      />

      <DataFetchPanel
        v-else-if="loadingRequests && visibleRequests.length"
        class="table-state"
        compact
        loading
        loading-title="Обновление заявок"
        loading-text="Подтягиваем актуальную выборку по заявкам."
      />

      <BulkActionBar
        v-if="auth.isStaff"
        :count="selectedRequestCount"
        label="заявок"
        @clear="clearRequestSelection"
      >
        <select v-model="bulkCloseOutcome" class="select select--sm">
          <option value="completed">Успешно</option>
          <option value="cancelled">Отменены</option>
          <option value="rejected">Отклонены</option>
          <option value="lost">Потеряны</option>
        </select>
        <button
          class="btn btn--sm btn--danger"
          type="button"
          @click="bulkCloseSelectedRequests"
        >
          Закрыть выбранные
        </button>
      </BulkActionBar>

      <DataFetchPanel
        v-if="loadingRequests && !visibleRequests.length"
        loading
        loading-title="Загрузка заявок"
        loading-text="Подтягиваем заявки и их статусы."
      />

      <DataFetchPanel
        v-else-if="requestsLoadError && !visibleRequests.length"
        :error="requestsLoadError"
        error-title="Не удалось загрузить заявки"
        @retry="reloadRequestsScreen"
      />

      <div v-else class="table-wrap table-wrap--cards">
        <table class="table requests-table table--responsive-cards">
          <thead>
            <tr>
              <th v-if="auth.isStaff" class="table-check-cell">
                <input
                  type="checkbox"
                  :checked="allRequestsOnPageSelected"
                  @change="toggleRequestsPageSelection($event.target.checked)" />
              </th>
              <th v-if="auth.isStaff">Клиент</th>
              <th>Агент</th>
              <th>Объект</th>
              <th>Операция</th>
              <th>Бюджет</th>
              <th>Статус</th>
              <th>Создана</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="requestItem in visibleRequests"
              :key="requestItem.id"
              class="requests-table__row-link"
              role="link"
              tabindex="0"
              @click="openRequest(requestItem.id)"
              @keydown.enter="openRequest(requestItem.id)"
              @keydown.space.prevent="openRequest(requestItem.id)"
            >
              <td v-if="auth.isStaff" class="table-check-cell" data-label="Выбор">
                <input
                  type="checkbox"
                  :checked="isRequestSelected(requestItem)"
                  @click.stop
                  @change="toggleRequestSelection(requestItem, $event.target.checked)" />
              </td>
              <td v-if="auth.isStaff" data-label="Клиент">
                <div class="user-cell">
                  <span class="user-avatar">{{ getInitials(requestItem.client_full_name || requestItem.client_username) }}</span>
                  <div class="user-info">
                    <div class="user-name">{{ requestItem.client_full_name || requestItem.client_username }}</div>
                    <div class="user-email" v-if="requestItem.client_email">{{ requestItem.client_email }}</div>
                  </div>
                </div>
              </td>
              <td data-label="Агент">
                <div v-if="requestItem.agent_id" class="user-cell">
                  <span class="user-avatar">{{ getInitials(requestItem.agent_full_name || requestItem.agent_username) }}</span>
                  <div class="user-info">
                    <div class="user-name">{{ requestItem.agent_full_name || requestItem.agent_username }}</div>
                    <div class="user-email" v-if="requestItem.agent_email">{{ requestItem.agent_email }}</div>
                  </div>
                </div>
                <span v-else class="tag">не назначен</span>
              </td>
              <td data-label="Объект">
                <router-link
                  v-if="requestItem.property"
                  :to="`/properties/${requestItem.property}`"
                  class="link requests-table__property-link"
                  style="color: #ffffff"
                >
                  {{ requestItem.property_title || 'Объект' }}
                </router-link>
                <span v-else class="muted">подбор</span>
              </td>
              <td data-label="Операция">{{ requestItem.operation_type_name }}</td>
              <td data-label="Бюджет">{{ formatBudget(requestItem) }}</td>
              <td data-label="Статус">
                <span class="tag" :class="statusClass(requestItem)">
                  {{ requestItem.status_name }}
                </span>
              </td>
              <td class="muted" data-label="Создана">
                {{ formatDate(requestItem.created_at) }}
              </td>
              <td class="table-actions-cell" data-label="Действия">
                <div class="row requests-table__actions" style="gap: 6px; flex-wrap: wrap">
                  <button
                    v-if="auth.isStaff && canTakeRequest(requestItem)"
                    class="btn btn--sm btn--accent"
                    :disabled="takeDisabled"
                    :title="takeDisabled
                      ? `Достигнут лимит активных заявок (${workload.activeRequestsLabel})`
                      : 'Взять заявку в работу'"
                    @click.stop="takeRequest(requestItem)"
                  >
                    Взять
                  </button>
                  <button
                    v-if="canEditRequest(requestItem)"
                    class="btn btn--sm"
                    @click.stop="startEditRequest(requestItem)"
                  >
                    Редактировать
                  </button>
                  <button
                    v-if="canDeleteRequest(requestItem)"
                    class="btn btn--sm btn--danger"
                    @click.stop="deleteRequest(requestItem)"
                  >
                    Удалить
                  </button>
                  <button
                    v-if="auth.isStaff && requestItem.can_close"
                    class="btn btn--sm btn--danger"
                    @click.stop="closeRequest(requestItem)"
                  >
                    Закрыть
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!loadingRequests && !requestsLoadError && !visibleRequests.length" class="empty">
        {{ emptyLabel }}
      </div>

      <ListPagination
        v-if="requestCount > visibleRequests.length"
        :count="requestCount"
        :page="requestPage"
        :visible-count="visibleRequests.length"
        :page-size="requestPageSize"
        label="заявок"
        @change="setRequestPage"
        @change-page-size="setRequestPageSize"
      />
    </div>

    <PropertyPickerModal
      v-if="propertyPickerOpen"
      title="Выбор объекта для заявки"
      :selected-id="form.property"
      :params="{ ordering: '-created_at' }"
      @close="propertyPickerOpen = false"
      @select="selectProperty"
    />
    <RequestCloseDialog
      v-if="closeDialog.open"
      :request-id="closeDialog.requestId"
      :loading="closeLoading"
      @cancel="resetCloseDialog"
      @submit="submitCloseRequest"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { bulkCloseRequests } from '../api/bulk'
import BulkActionBar from '../components/BulkActionBar.vue'
import DataFetchPanel from '../components/DataFetchPanel.vue'
import ListPagination from '../components/ListPagination.vue'
import PropertyPickerModal from '../components/PropertyPickerModal.vue'
import RemoteLookupField from '../components/RemoteLookupField.vue'
import RequestCloseDialog from '../components/RequestCloseDialog.vue'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { useBulkSelection } from '../composables/useBulkSelection'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { closeRequest as closeRequestAction } from '../api/tasks'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney, formatDate } from '@/utils/formatters'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import {
  activeRequestStatusCodes,
  canTakeRequest,
  getRequestCloseSuccessMessage,
  terminalRequestStatusCodes,
} from '@/utils/requestClose'
import { propertyTypeUsesRooms } from '@/utils/propertyTypes'

const auth = useAuthStore()
const router = useRouter()
const confirm = useConfirmStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()

const requests = ref([])
const operations = ref([])
const statuses = ref([])

const showForm = ref(false)
const formError = ref('')
const scope = ref('all')
const closeLoading = ref(false)
const requestPage = ref(1)
const requestPageSize = ref(DEFAULT_PAGE_SIZE)
const requestCount = ref(0)
const loadingRequests = ref(false)
const editingRequestId = ref(null)
const propertyPickerOpen = ref(false)
const selectedPropertyLabel = ref('')
const bulkCloseOutcome = ref('cancelled')
const requestFormBaseline = ref('')
const requestDraftRestored = ref(false)
const requestsLoadError = ref('')
const closeDialog = reactive({
  open: false,
  requestId: null,
})
const requestStatsSnapshot = reactive({
  total: 0,
  active: 0,
  closed: 0,
  unassigned: 0,
  mine: 0,
})
const requestFilters = reactive({
  operation_type: '',
  status: '',
  date_from: '',
  date_to: '',
})

const form = reactive(defaultForm())
const isEditingRequest = computed(() => editingRequestId.value !== null)
const isRequestRoomsDisabled = computed(() => !propertyTypeUsesRooms(form.property_type))
const requestFormSnapshot = computed(() => JSON.stringify({ ...form }))
const isRequestFormDirty = computed(() => (
  showForm.value && requestFormSnapshot.value !== requestFormBaseline.value
))

function defaultForm() {
  return {
    client: null,
    agent: null,
    operation_type: null,
    property: null,
    property_type: '',
    min_area: null,
    max_area: null,
    rooms_count: null,
    min_price: null,
    max_price: null,
    description: '',
  }
}

function syncRequestFormBaseline() {
  requestFormBaseline.value = requestFormSnapshot.value
}

function isRequestDraftEmpty(draft) {
  const formData = draft?.form || {}
  return !Object.entries(formData)
    .filter(([key]) => key !== 'operation_type')
    .some(([, value]) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== '' && value !== null && value !== undefined
    })
}

const { clearDraft: clearRequestDraft } = useDraftPersistence({
  key: 'requests:create',
  enabled: () => showForm.value && !isEditingRequest.value,
  getData: () => ({ form: { ...form } }),
  applyData: (draft) => {
    requestDraftRestored.value = true
    Object.assign(form, defaultForm(), draft?.form || {})
    formError.value = ''
    toasts.info('Черновик заявки восстановлен')
  },
  isEmpty: isRequestDraftEmpty,
})

const { confirmLeave: confirmRequestFormLeave } = useUnsavedChangesGuard({
  enabled: () => showForm.value,
  isDirty: () => isRequestFormDirty.value,
  message: 'Есть несохранённые изменения в форме заявки. Покинуть страницу?',
})

const staffTabs = computed(() => [
  { value: 'all', label: 'Все', count: requestStatsSnapshot.total },
  {
    value: 'unassigned',
    label: 'Неразобранные',
    count: requestStatsSnapshot.unassigned,
  },
  {
    value: 'mine',
    label: 'Мои',
    count: requestStatsSnapshot.mine,
  },
])

const visibleRequests = computed(() => requests.value)
const {
  selectedIds: selectedRequestIds,
  selectedCount: selectedRequestCount,
  allOnPageSelected: allRequestsOnPageSelected,
  isSelected: isRequestSelected,
  toggleSelection: toggleRequestSelection,
  togglePageSelection: toggleRequestsPageSelection,
  clearSelection: clearRequestSelection,
} = useBulkSelection(visibleRequests)

const emptyLabel = computed(() => {
  if (!auth.isStaff) return 'Вы пока не подавали заявок.'
  if (scope.value === 'unassigned') return 'Нет нераспределённых заявок.'
  if (scope.value === 'mine') return 'У вас нет активных заявок.'
  return 'Заявок ещё не создано.'
})

const takeDisabled = computed(() => !auth.isManager && !workload.workload.can_take_request)

function getInitials(name) {
  if (!name) return '?'
  const parts = name.split(' ')
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return name.substring(0, 2).toUpperCase()
}

function formatBudget(requestItem) {
  const min = requestItem.min_price ? `${formatMoney(requestItem.min_price)} ₽` : '—'
  const max = requestItem.max_price ? `${formatMoney(requestItem.max_price)} ₽` : '—'
  return `${min}–${max}`
}

function statusClass(requestItem) {
  const code = requestItem.status_code
  if (terminalRequestStatusCodes.includes(code)) return 'tag--panel'
  return 'tag--accent'
}

function formatRequestValidationError(data) {
  const labels = {
    client: 'Клиент',
    agent: 'Агент',
    property: 'Объект',
    operation_type: 'Тип операции',
    status: 'Статус',
    property_type: 'Тип помещения',
    min_price: 'Минимальная цена',
    max_price: 'Максимальная цена',
    min_area: 'Минимальная площадь',
    max_area: 'Максимальная площадь',
    rooms_count: 'Количество комнат',
    floor_number: 'Этаж',
    total_floors: 'Количество этажей',
    description: 'Пожелания',
  }

  if (!data || typeof data !== 'object') return ''
  const parts = []
  for (const [key, value] of Object.entries(data)) {
    const title = labels[key] || key
    const message = Array.isArray(value) ? value.filter(Boolean).join(' ') : String(value || '')
    if (message) parts.push(`${title}: ${message}`)
  }
  return parts.join(' ')
}

function mapClientOption(user) {
  const fullName = user.full_name || user.username
  return {
    id: user.id,
    label: fullName,
    hint: [user.email, user.phone].filter(Boolean).join(' · ') || 'Клиент',
  }
}

function mapAgentOption(user) {
  const fullName = user.full_name || user.username
  return {
    id: user.id,
    label: fullName,
    hint: [user.role_name, user.email].filter(Boolean).join(' · ') || 'Сотрудник',
  }
}

function selectProperty(property) {
  form.property = property.id
  selectedPropertyLabel.value = `${property.title || `Объект №${property.id}`}${property.full_address ? ` · ${property.full_address}` : ''}`
  propertyPickerOpen.value = false
}

function clearSelectedProperty() {
  form.property = null
  selectedPropertyLabel.value = ''
}

function toggleForm() {
  if (showForm.value) {
    cancelForm()
    return
  }
  openCreateForm()
}

function resetForm() {
  formError.value = ''
  editingRequestId.value = null
  Object.assign(form, defaultForm())
  if (operations.value.length) {
    form.operation_type = operations.value[0].id
  }
}

function cancelForm() {
  if (!confirmRequestFormLeave()) return
  showForm.value = false
  clearRequestDraft()
  resetForm()
  syncRequestFormBaseline()
}

function openCreateForm() {
  requestDraftRestored.value = false
  resetForm()
  showForm.value = true
  syncRequestFormBaseline()
}

function canEditRequest(requestItem) {
  return auth.isStaff && !terminalRequestStatusCodes.includes(requestItem.status_code)
}

function canDeleteRequest(requestItem) {
  return auth.isStaff && !terminalRequestStatusCodes.includes(requestItem.status_code)
}

function populateFormFromRequest(requestItem) {
  formError.value = ''
  editingRequestId.value = requestItem.id
  Object.assign(form, {
    client: requestItem.client ?? null,
    agent: requestItem.agent ?? null,
    operation_type: requestItem.operation_type ?? operations.value[0]?.id ?? null,
    property: requestItem.property ?? null,
    property_type: requestItem.property_type || '',
    min_area: requestItem.min_area ?? null,
    max_area: requestItem.max_area ?? null,
    rooms_count: requestItem.rooms_count ?? null,
    min_price: requestItem.min_price ?? null,
    max_price: requestItem.max_price ?? null,
    description: requestItem.description || '',
  })
  selectedPropertyLabel.value = requestItem.property
    ? (requestItem.property_title || `Объект #${requestItem.property}`)
    : ''
}

function startEditRequest(requestItem) {
  requestDraftRestored.value = false
  populateFormFromRequest(requestItem)
  showForm.value = true
  syncRequestFormBaseline()
}

async function load() {
  loadingRequests.value = true
  requestsLoadError.value = ''
  try {
    const { data } = await api.get('/requests/', { params: listParams() })
    const payload = unpackPaginated(data)
    requests.value = payload.items
    requestCount.value = payload.count
  } catch (err) {
    requestsLoadError.value = extractError(err, 'Не удалось загрузить заявки')
    toasts.error(requestsLoadError.value)
  } finally {
    loadingRequests.value = false
  }
}

async function loadLookups() {
  try {
    const [operationsResponse, statusesResponse] = await Promise.all([
      api.get('/operation-types/', {
        params: { page_size: LOOKUP_PAGE_SIZE },
      }),
      api.get('/request-statuses/', {
        params: { page_size: LOOKUP_PAGE_SIZE },
      }),
    ])
    operations.value = unpackPaginated(operationsResponse.data).items
    statuses.value = unpackPaginated(statusesResponse.data).items
    if (operations.value.length && !form.operation_type) {
      form.operation_type = operations.value[0].id
    }
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить справочники заявок'))
  }
}

function requestFilterParams({ includePaging = false } = {}) {
  const params = {}
  if (requestFilters.operation_type) {
    params.operation_type = Number(requestFilters.operation_type)
  }
  if (requestFilters.status) {
    params.status = Number(requestFilters.status)
  }
  if (requestFilters.date_from) {
    params.date_from = requestFilters.date_from
  }
  if (requestFilters.date_to) {
    params.date_to = requestFilters.date_to
  }
  if (includePaging) {
    params.page = requestPage.value
    params.page_size = requestPageSize.value
  }
  return params
}

function listParams() {
  const params = {
    ...requestFilterParams({ includePaging: true }),
  }
  if (auth.isStaff && scope.value !== 'all') {
    params.scope = scope.value
  }
  return params
}

async function fetchRequestCount(params = {}) {
  const { data } = await api.get('/requests/', {
    params: { page: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadRequestCounts() {
  try {
    if (auth.isStaff) {
      const totalParams = requestFilterParams()
      const activeParams = {
        ...requestFilterParams(),
        status_code: activeRequestStatusCodes.join(','),
      }
      delete activeParams.status
      const [total, active, unassigned, mine] = await Promise.all([
        fetchRequestCount(totalParams),
        fetchRequestCount(activeParams),
        fetchRequestCount({ ...totalParams, scope: 'unassigned' }),
        fetchRequestCount({ ...totalParams, scope: 'mine' }),
      ])
      requestStatsSnapshot.total = total
      requestStatsSnapshot.active = active
      requestStatsSnapshot.closed = Math.max(total - active, 0)
      requestStatsSnapshot.unassigned = unassigned
      requestStatsSnapshot.mine = mine
      return
    }

    const totalParams = requestFilterParams()
    const activeParams = {
      ...requestFilterParams(),
      status_code: activeRequestStatusCodes.join(','),
    }
    delete activeParams.status
    const terminalParams = {
      ...requestFilterParams(),
      status_code: terminalRequestStatusCodes.join(','),
    }
    delete terminalParams.status
    const [total, active, closed] = await Promise.all([
      fetchRequestCount(totalParams),
      fetchRequestCount(activeParams),
      fetchRequestCount(terminalParams),
    ])
    requestStatsSnapshot.total = total
    requestStatsSnapshot.active = active
    requestStatsSnapshot.closed = closed
    requestStatsSnapshot.unassigned = 0
    requestStatsSnapshot.mine = 0
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось обновить счётчики заявок'))
  }
}

function setRequestPage(page) {
  if (page < 1 || page === requestPage.value) return
  requestPage.value = page
}

function setRequestPageSize(size) {
  if (!size || size === requestPageSize.value) return
  requestPageSize.value = size
}

function resetFilters() {
  requestFilters.operation_type = ''
  requestFilters.status = ''
  requestFilters.date_from = ''
  requestFilters.date_to = ''
}

function openRequest(id) {
  router.push(`/requests/${id}`)
}

async function createRequest() {
  formError.value = ''
  if (auth.isStaff && !form.client) {
    formError.value = 'Выберите клиента для заявки.'
    return
  }
  if (!form.operation_type) {
    formError.value = 'Выберите тип операции.'
    return
  }

  try {
    const wasEditing = isEditingRequest.value
    const payload = { ...form }
    if (!propertyTypeUsesRooms(payload.property_type)) {
      payload.rooms_count = null
    }
    if (!auth.isStaff) {
      delete payload.client
      delete payload.agent
    }
    if (!isEditingRequest.value) {
      if (!payload.agent) delete payload.agent
      if (!payload.property) delete payload.property
      if (!payload.rooms_count) delete payload.rooms_count
      if (!payload.min_price) delete payload.min_price
      if (!payload.max_price) delete payload.max_price
      if (!payload.property_type) delete payload.property_type
    }

    if (wasEditing) {
      await api.patch(`/requests/${editingRequestId.value}/`, payload)
    } else {
      await api.post('/requests/', payload)
    }

    showForm.value = false
    clearRequestDraft()
    resetForm()
    syncRequestFormBaseline()
    requestPage.value = 1
    await Promise.all([
      load(),
      loadRequestCounts(),
      auth.isStaff ? workload.refresh() : Promise.resolve(),
    ])
    toasts.success(wasEditing ? 'Заявка обновлена' : 'Заявка создана')
  } catch (err) {
    const validationMessage = formatRequestValidationError(err.response?.data)
    formError.value = validationMessage || (
      isEditingRequest.value
        ? 'Не удалось обновить заявку.'
        : 'Не удалось создать заявку.'
    )
    toasts.error(extractError(
      err,
      isEditingRequest.value ? 'Не удалось обновить заявку' : 'Не удалось создать заявку',
    ))
  }
}

async function takeRequest(requestItem) {
  if (!auth.isManager && !workload.workload.can_take_request) {
    toasts.warn(
      `Нельзя взять заявку: уже ${workload.workload.active_requests} в работе `
        + `из ${workload.workload.max_active_requests}. Закройте текущую.`,
    )
    return
  }

  try {
    await api.post(`/requests/${requestItem.id}/take/`)
    toasts.success(`Заявка #${requestItem.id} взята в работу`)
  } catch (err) {
    toasts.error(
      extractError(err, 'Не удалось взять заявку. Возможно, превышен лимит.'),
    )
  }

  await Promise.all([load(), loadRequestCounts(), workload.refresh()])
}

async function deleteRequest(requestItem) {
  const approved = await confirm.ask({
    title: 'Удаление заявки',
    message: `Удалить заявку #${requestItem.id}?`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return

  try {
    await api.delete(`/requests/${requestItem.id}/`)
    if (editingRequestId.value === requestItem.id) {
      cancelForm()
    }
    requestPage.value = 1
    await Promise.all([load(), loadRequestCounts(), workload.refresh()])
    toasts.success(`Заявка #${requestItem.id} удалена`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось удалить заявку'))
  }
}

async function bulkCloseSelectedRequests() {
  if (!selectedRequestIds.value.length) return
  const approved = await confirm.ask({
    title: 'Массовое закрытие заявок',
    message: `Закрыть выбранные заявки (${selectedRequestIds.value.length})?`,
    confirmLabel: 'Закрыть',
    danger: true,
  })
  if (!approved) return

  const result = await bulkCloseRequests(
    [...selectedRequestIds.value],
    bulkCloseOutcome.value,
  )
  if (!result.ok) {
    toasts.error(result.error || 'Не удалось закрыть выбранные заявки')
    return
  }

  clearRequestSelection()
  await Promise.all([load(), loadRequestCounts(), workload.refresh()])
  const {
    closed,
    deals_created: dealsCreated = 0,
    errors = [],
    not_found_ids: notFoundIds = [],
  } = result.data
  if (errors.length || notFoundIds.length) {
    toasts.warn(
      `Закрыто заявок: ${closed}. Сделок создано: ${dealsCreated}. Пропущено: ${errors.length + notFoundIds.length}.`,
    )
    return
  }
  toasts.success(`Закрыто заявок: ${closed}. Сделок создано: ${dealsCreated}.`)
}

function closeRequest(requestItem) {
  closeDialog.open = true
  closeDialog.requestId = requestItem.id
}

function resetCloseDialog() {
  closeDialog.open = false
  closeDialog.requestId = null
  closeLoading.value = false
}

async function submitCloseRequest(outcome) {
  if (!closeDialog.requestId) return

  closeLoading.value = true
  const requestId = closeDialog.requestId
  const result = await closeRequestAction(requestId, outcome)
  closeLoading.value = false

  if (!result.ok) {
    toasts.error(result.error || 'Не удалось закрыть заявку')
    return
  }

  toasts.success(getRequestCloseSuccessMessage({
    outcome,
    data: result.data,
    requestId,
  }))
  resetCloseDialog()
  await Promise.all([load(), loadRequestCounts(), workload.refresh()])
}

async function reloadRequestsScreen() {
  await Promise.all([
    load(),
    loadLookups(),
    loadRequestCounts(),
    auth.isStaff ? workload.refresh() : Promise.resolve(),
  ])
}

watch(scope, async () => {
  requestPage.value = 1
  await load()
})

watch(
  () => [
    requestFilters.operation_type,
    requestFilters.status,
    requestFilters.date_from,
    requestFilters.date_to,
  ],
  async () => {
    requestPage.value = 1
    await Promise.all([load(), loadRequestCounts()])
  },
)

watch(() => form.property_type, (value) => {
  if (!propertyTypeUsesRooms(value)) {
    form.rooms_count = null
  }
})

watch(requestPage, async () => {
  await load()
})

watch(requestPageSize, async () => {
  if (requestPage.value !== 1) {
    requestPage.value = 1
    return
  }
  await load()
})

onMounted(async () => {
  await reloadRequestsScreen()
  syncRequestFormBaseline()
})
</script>

<style scoped>
.requests-head {
  margin-bottom: 12px;
}

.requests-tabs {
  align-items: stretch;
}

.request-filters-grid {
  align-items: end;
}

.table-check-cell {
  width: 44px;
  text-align: center;
}

.table-check-cell input {
  width: 16px;
  height: 16px;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--c-accent);
  color: #fff;
  text-transform: uppercase;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.user-name {
  font-weight: 600;
  color: var(--c-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-email {
  font-size: 12px;
  color: var(--c-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.request-form__grid {
  align-items: start;
}

.request-form__grid .select,
.request-filters-grid .select {
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

.request-form__grid .select option,
.request-filters-grid .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.request-form__property {
  min-width: 0;
}

.request-form__budget {
  max-width: 420px;
}

.request-form__budget-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.requests-table__actions {
  min-width: 240px;
}

.requests-table__row-link {
  cursor: pointer;
}

.requests-table__row-link:hover td {
  background: rgba(255, 255, 255, 0.03);
}

.requests-table__row-link:focus-visible {
  outline: 2px solid rgba(120, 216, 206, 0.42);
  outline-offset: -2px;
}

.table .requests-table__property-link,
.table .requests-table__property-link:hover {
  color: #ffffff;
  font-weight: 600;
}

.link {
  color: var(--c-accent);
  font-weight: 600;
}

.link:hover {
  color: var(--c-accent-2);
  text-decoration: underline;
  text-decoration-color: rgba(99, 208, 197, 0.5);
}

@media (max-width: 960px) {
  .request-form__budget {
    max-width: none;
  }
}

@media (max-width: 640px) {
  .requests-table__actions {
    min-width: 0;
    width: 100%;
  }

  .request-form__budget-row {
    grid-template-columns: 1fr;
  }
}
</style>