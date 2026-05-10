<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Отчёты</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">Отчёты и выгрузки</h1>
          <div style="color: rgba(255,255,255,.78); font-size: 14px; margin-top: 6px">
            Два рабочих отчёта для дипломного контура: сделки и задачи сотрудников,
            с фильтрами, сортировкой и экспортом.
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button
            class="btn btn--sm"
            :class="{ 'btn--primary': reportType === 'deals' }"
            @click="switchReport('deals')"
          >
            Сделки
          </button>
          <button
            class="btn btn--sm"
            :class="{ 'btn--primary': reportType === 'tasks' }"
            @click="switchReport('tasks')"
          >
            Задачи
          </button>
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Фильтры отчёта</h2>
          <div class="muted">
            Период, статус, исполнитель, тип задачи и сортировка меняют выборку
            без перехода на другие страницы.
          </div>
        </div>
      </div>

      <div v-if="reportType === 'deals'" class="grid grid--4 reports-filter-grid">
        <div class="field">
          <label>Дата от</label>
          <input v-model="dealFilters.date_from" class="input" type="date" />
        </div>
        <div class="field">
          <label>Дата до</label>
          <input v-model="dealFilters.date_to" class="input" type="date" />
        </div>
        <div class="field">
          <label>Статус</label>
          <select v-model="dealFilters.status" class="select">
            <option value="">Все статусы</option>
            <option v-for="status in dealStatuses" :key="status.id" :value="String(status.id)">
              {{ status.name }}
            </option>
          </select>
        </div>
        <div v-if="canChooseEmployee" class="field">
          <label>Агент</label>
          <select v-model="dealFilters.agent" class="select">
            <option value="">Все сотрудники</option>
            <option value="me">Я</option>
            <option v-for="employee in employees" :key="employee.id" :value="String(employee.id)">
              {{ employee.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Сортировка</label>
          <select v-model="dealFilters.ordering" class="select">
            <option v-for="option in dealOrderingOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
      </div>

      <div v-else class="grid grid--4 reports-filter-grid">
        <div class="field">
          <label>Дата от</label>
          <input v-model="taskFilters.date_from" class="input" type="date" />
        </div>
        <div class="field">
          <label>Дата до</label>
          <input v-model="taskFilters.date_to" class="input" type="date" />
        </div>
        <div class="field">
          <label>Статус</label>
          <select v-model="taskFilters.status" class="select">
            <option value="">Все статусы</option>
            <option v-for="status in taskStatuses" :key="status.id" :value="String(status.id)">
              {{ status.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Тип задачи</label>
          <select v-model="taskFilters.task_type" class="select">
            <option value="">Все типы</option>
            <option v-for="type in taskTypes" :key="type.code" :value="type.code">
              {{ type.name }}
            </option>
          </select>
        </div>
        <div v-if="canChooseEmployee" class="field">
          <label>Исполнитель</label>
          <select v-model="taskFilters.assignee" class="select">
            <option value="">Все сотрудники</option>
            <option value="me">Я</option>
            <option v-for="employee in employees" :key="employee.id" :value="String(employee.id)">
              {{ employee.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Сортировка</label>
          <select v-model="taskFilters.ordering" class="select">
            <option v-for="option in taskOrderingOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="row reports-filter-actions" style="gap: 8px; justify-content: flex-end; margin-top: 18px">
        <button class="btn" @click="resetFilters">Сбросить</button>
        <button class="btn btn--accent" :disabled="loading" @click="loadCurrentReport">
          {{ loading ? 'Загрузка…' : 'Применить' }}
        </button>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">{{ currentReport.title || currentTitle }}</h2>
          <div class="muted">Записей в выборке: {{ currentReport.rows.length }}</div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--sm" :disabled="loading" @click="exportCurrent('csv')">CSV</button>
          <button class="btn btn--sm" :disabled="loading" @click="exportCurrent('json')">JSON</button>
          <button class="btn btn--sm" :disabled="loading" @click="exportCurrent('xlsx')">Excel</button>
          <button class="btn btn--sm btn--accent" :disabled="loading" @click="exportCurrent('pdf')">PDF</button>
        </div>
      </div>

      <div class="reports-summary">
        <article v-for="item in summaryEntries" :key="item.label" class="reports-summary__card">
          <div class="reports-summary__label">{{ item.label }}</div>
          <div class="reports-summary__value">{{ item.value }}</div>
        </article>
      </div>

      <DataFetchPanel
        v-if="reportLoadError && currentReport.rows.length"
        class="table-state"
        compact
        :error="reportLoadError"
        error-title="Отчёт обновлён не полностью"
        @retry="loadCurrentReport"
      />

      <DataFetchPanel
        v-else-if="loading && currentReport.rows.length"
        class="table-state"
        compact
        loading
        loading-title="Обновление отчёта"
        loading-text="Подтягиваем актуальные строки и сводные значения."
      />

      <DataFetchPanel
        v-if="loading && !currentReport.rows.length"
        loading
        loading-title="Загрузка отчёта"
        loading-text="Формируем выборку по текущим фильтрам."
      />

      <DataFetchPanel
        v-else-if="reportLoadError && !currentReport.rows.length"
        :error="reportLoadError"
        error-title="Не удалось загрузить отчёт"
        @retry="loadCurrentReport"
      />

      <div v-else class="table-wrap table-wrap--cards reports-table-wrap">
        <table class="table table--responsive-cards">
          <thead>
            <tr>
              <th v-for="column in currentReport.columns" :key="column.key">{{ column.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in currentReport.rows" :key="`${reportType}-${index}`">
              <td
                v-for="column in currentReport.columns"
                :key="column.key"
                :data-label="column.label"
              >
                {{ row[column.key] }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!currentReport.rows.length && !loading && !reportLoadError" class="empty">
        По выбранным фильтрам данных нет.
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { exportReportData } from '../api/exports'
import DataFetchPanel from '../components/DataFetchPanel.vue'
import { useAuthStore } from '../store/auth'
import { extractError, useToastsStore } from '../store/toasts'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const toasts = useToastsStore()

const reportType = ref('deals')
const loading = ref(false)
const reportLoadError = ref('')
const employees = ref([])
const dealStatuses = ref([])
const taskStatuses = ref([])

const dealReport = ref(emptyReport())
const taskReport = ref(emptyReport())

const dealOrderingOptions = [
  { value: '-deal_date', label: 'Дата: сначала новые' },
  { value: 'deal_date', label: 'Дата: сначала старые' },
  { value: '-price_final', label: 'Сумма: по убыванию' },
  { value: 'price_final', label: 'Сумма: по возрастанию' },
  { value: '-commission_amount', label: 'Комиссия: по убыванию' },
  { value: 'commission_amount', label: 'Комиссия: по возрастанию' },
  { value: 'deal_number', label: 'Номер: А-Я' },
  { value: '-deal_number', label: 'Номер: Я-А' },
]

const taskOrderingOptions = [
  { value: '-created_at', label: 'Создание: сначала новые' },
  { value: 'created_at', label: 'Создание: сначала старые' },
  { value: 'due_date', label: 'Срок: сначала ранние' },
  { value: '-due_date', label: 'Срок: сначала поздние' },
  { value: 'title', label: 'Название: А-Я' },
  { value: '-title', label: 'Название: Я-А' },
  { value: 'priority', label: 'Приоритет: по возрастанию' },
  { value: '-priority', label: 'Приоритет: по убыванию' },
]

const dealFilters = reactive({
  date_from: '',
  date_to: '',
  status: '',
  agent: '',
  ordering: '-deal_date',
})

const taskFilters = reactive({
  date_from: '',
  date_to: '',
  status: '',
  assignee: '',
  task_type: '',
  ordering: '-created_at',
})

const taskTypes = [
  { code: 'contact_client', name: 'Связаться с клиентом' },
  { code: 'property_search', name: 'Подбор объектов' },
  { code: 'showing', name: 'Показ объекта' },
  { code: 'documents', name: 'Подготовка документов' },
  { code: 'call', name: 'Звонок' },
  { code: 'other', name: 'Прочее' },
]

const canChooseEmployee = computed(() => auth.isManager)
const currentReport = computed(() => (reportType.value === 'deals' ? dealReport.value : taskReport.value))
const currentTitle = computed(() => (
  reportType.value === 'deals' ? 'Отчёт по сделкам' : 'Отчёт по задачам сотрудников'
))
const summaryEntries = computed(() => (
  Object.entries(currentReport.value.summary || {}).map(([label, value]) => ({ label, value }))
))

function emptyReport() {
  return {
    title: '',
    columns: [],
    rows: [],
    summary: {},
    ordering: '',
    ordering_options: [],
  }
}

function currentEndpoint() {
  return reportType.value === 'deals' ? '/reports/deals/' : '/reports/tasks/'
}

function currentParams() {
  return reportType.value === 'deals'
    ? { ...dealFilters }
    : { ...taskFilters }
}

function switchReport(type) {
  reportType.value = type
  const report = type === 'deals' ? dealReport.value : taskReport.value
  if (!report.rows.length) {
    loadCurrentReport()
  }
}

function resetFilters() {
  if (reportType.value === 'deals') {
    dealFilters.date_from = ''
    dealFilters.date_to = ''
    dealFilters.status = ''
    dealFilters.agent = ''
    dealFilters.ordering = '-deal_date'
  } else {
    taskFilters.date_from = ''
    taskFilters.date_to = ''
    taskFilters.status = ''
    taskFilters.assignee = ''
    taskFilters.task_type = ''
    taskFilters.ordering = '-created_at'
  }
  loadCurrentReport()
}

async function loadLookups() {
  try {
    const [usersResponse, dealStatusesResponse, taskStatusesResponse] = await Promise.all([
      api.get('/users/', { params: { user_type: 'employee', page_size: LOOKUP_PAGE_SIZE } }),
      api.get('/deal-statuses/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
      api.get('/task-statuses/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    ])
    employees.value = unpackPaginated(usersResponse.data).items
    dealStatuses.value = unpackPaginated(dealStatusesResponse.data).items
    taskStatuses.value = unpackPaginated(taskStatusesResponse.data).items
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить справочники отчётов'))
  }
}

async function loadCurrentReport() {
  loading.value = true
  reportLoadError.value = ''
  try {
    const { data } = await api.get(currentEndpoint(), { params: currentParams() })
    if (reportType.value === 'deals') {
      dealReport.value = data
      if (data.ordering) dealFilters.ordering = data.ordering
    } else {
      taskReport.value = data
      if (data.ordering) taskFilters.ordering = data.ordering
    }
  } catch (err) {
    reportLoadError.value = extractError(err, 'Не удалось загрузить отчёт')
    toasts.error(extractError(err, 'Не удалось загрузить отчёт'))
  } finally {
    loading.value = false
  }
}

async function exportCurrent(format) {
  loading.value = true
  try {
    await exportReportData(
      currentEndpoint(),
      format,
      currentParams(),
      `${reportType.value}-report.${format}`,
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось выгрузить отчёт'))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadLookups()
  await loadCurrentReport()
})
</script>

<style scoped>
.reports-filter-grid {
  align-items: end;
}

.reports-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 18px;
  margin-bottom: 18px;
}

.reports-summary__card {
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(21, 56, 57, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.94));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 24px rgba(16, 55, 52, 0.08);
}

.reports-summary__label {
  color: var(--c-ink-soft);
  font-size: 13px;
  margin-bottom: 6px;
}

.reports-summary__value {
  color: var(--c-page-text);
  font-size: 18px;
  font-weight: 700;
}

.reports-table-wrap {
  min-height: 280px;
}
</style>
