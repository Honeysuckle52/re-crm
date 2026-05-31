<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">Сделки</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">
        {{ auth.isClient ? 'Мои сделки' : 'Журнал сделок' }}
      </h1>
    </div>

    <div class="panel panel--light">
      <div class="surface-head deal-filter__head">
        <div class="surface-head__meta">
          <h2 class="h3">Фильтры сделок</h2>
          <div class="muted">
            Оставьте нужный этап, операцию и период, чтобы быстро найти нужную сделку.
          </div>
        </div>
        <button class="btn btn--sm btn--ghost" type="button" @click="resetFilters">
          Сбросить
        </button>
      </div>
      <div class="grid grid--4 deal-filter__grid">
        <div class="field">
          <label>Операция</label>
          <select v-model="operationFilter" class="select">
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
          <label>Дата от</label>
          <input v-model="dateFromFilter" class="input" type="date" />
        </div>
        <div class="field">
          <label>Дата до</label>
          <input v-model="dateToFilter" class="input" type="date" />
        </div>
      </div>
      <div class="row deal-filter__actions" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn--sm"
                 :class="{ 'btn--primary': statusFilter === '' }"
                 @click="statusFilter = ''">
          Все ({{ dealCount }})
        </button>
        <button v-for="s in statuses" :key="s.id"
                 class="btn btn--sm"
                 :class="{ 'btn--primary': statusFilter === String(s.id) }"
                 @click="statusFilter = String(s.id)">
          {{ s.name }} ({{ countByStatus(s.id) }})
        </button>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Сделки в работе</h2>
          <div class="muted">Показано {{ filtered.length }} из {{ filteredTotalCount }} записей по текущему фильтру.</div>
        </div>
        <div v-if="auth.isStaff" class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--sm" :disabled="exportingDeals" @click="exportDeals('csv')">CSV</button>
          <button class="btn btn--sm" :disabled="exportingDeals" @click="exportDeals('xlsx')">XLSX</button>
          <button class="btn btn--sm" :disabled="exportingDeals" @click="exportDeals('json')">JSON</button>
        </div>
      </div>

      <DataFetchPanel
        v-if="dealsLoadError && filtered.length"
        class="table-state"
        compact
        :error="dealsLoadError"
        error-title="Список сделок загружен не полностью"
        @retry="reloadDealsScreen"
      />

      <DataFetchPanel
        v-else-if="loadingDeals && filtered.length"
        class="table-state"
        compact
        loading
        loading-title="Обновление сделок"
        loading-text="Подтягиваем актуальную выборку по сделкам."
      />

      <DataFetchPanel
        v-if="loadingDeals && !filtered.length"
        loading
        loading-title="Загрузка сделок"
        loading-text="Подтягиваем сделки и статусы договоров."
      />

      <DataFetchPanel
        v-else-if="dealsLoadError && !filtered.length"
        :error="dealsLoadError"
        error-title="Не удалось загрузить сделки"
        @retry="reloadDealsScreen"
      />

      <div v-else class="table-wrap table-wrap--cards">
        <table class="table deals-table table--responsive-cards">
          <thead>
            <tr>
              <th>Заявка</th>
              <th>Объект</th>
              <th>Тип</th>
              <th>Стоимость, ₽</th>
              <th>Комиссия</th>
              <th>Статус</th>
              <th>Дата</th>
              <th>Договор</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="deal in filtered" :key="deal.id">
              <td
                class="deals-table__request-cell"
                :class="{ 'deals-table__request-cell--clickable': deal.request }"
                data-label="Заявка"
                :role="deal.request ? 'link' : undefined"
                :tabindex="deal.request ? 0 : undefined"
                @click="openDealRequest(deal)"
                @keydown.enter="openDealRequest(deal)"
                @keydown.space.prevent="openDealRequest(deal)"
              >
                <b v-if="deal.request">#{{ deal.request }}</b>
                <span v-else class="muted">—</span>
              </td>
              <td data-label="Объект">
                <router-link v-if="deal.property" :to="`/properties/${deal.property}`" class="link">
                  {{ deal.property_title || 'Объект №' + deal.property }}
                </router-link>
                <span v-else class="muted">—</span>
              </td>
              <td data-label="Тип"><span class="tag tag--accent">{{ deal.operation_type_name }}</span></td>
              <td data-label="Стоимость">{{ formatMoney(deal.price_final) }}</td>
              <td data-label="Комиссия">
                {{ deal.commission_percent || '—' }}%
                <span class="muted">
                  ({{ deal.commission_amount ? formatMoney(deal.commission_amount) + ' ₽' : '—' }})
                </span>
              </td>
              <td data-label="Статус">
                <span class="tag" :class="dealStatusClass(deal.status_name)">
                  {{ deal.status_name || '—' }}
                </span>
              </td>
              <td class="muted" data-label="Дата">
                {{ new Date(deal.deal_date).toLocaleDateString('ru-RU') }}
              </td>
              <td class="deals-table__contract" data-label="Договор">
                <button v-if="deal.contract_url"
                        class="btn btn--sm deals-table__contract-btn"
                        :title="dealContractStatusHint(deal)"
                        @click="downloadContract(deal)">
                  Скачать PDF
                </button>
                <button v-else-if="dealContractQueueActive(deal)"
                        class="btn btn--sm deals-table__contract-btn"
                        disabled
                        :title="dealContractStatusHint(deal)">
                  {{ dealContractStatusLabel(deal) }}
                </button>
                <button v-else-if="auth.isStaff"
                        class="btn btn--sm btn--ghost deals-table__contract-btn"
                        :title="dealContractStatusHint(deal)"
                        @click="regenerate(deal)">
                  {{ deal.contract_status === 'failed' ? 'Повторить генерацию' : 'Поставить в очередь' }}
                </button>
                <span v-else
                      class="tag deals-table__contract-state"
                      :title="dealContractStatusHint(deal)">
                  {{ dealContractStatusLabel(deal) }}
                </span>
              </td>
              <td class="deals-table__status table-actions-cell" data-label="Действия">
                <select v-if="auth.isStaff"
                        class="select select--sm" :value="deal.status"
                        @change="changeStatus(deal, $event.target.value)">
                  <option disabled value="">Изменить статус</option>
                  <option v-for="s in dealStatusOptions(deal)" :key="s.id" :value="s.id">
                    {{ s.name }}
                  </option>
                </select>
                <span v-else class="muted">только просмотр</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!loadingDeals && !dealsLoadError && !filtered.length" class="empty">
        Сделок по выбранному статусу нет.
      </div>

      <ListPagination
        v-if="filteredTotalCount > filtered.length"
        :count="filteredTotalCount"
        :page="dealPage"
        :visible-count="filtered.length"
        :page-size="dealPageSize"
        label="сделок"
        @change="setDealPage"
        @change-page-size="setDealPageSize"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { exportEntityData } from '../api/exports'
import DataFetchPanel from '../components/DataFetchPanel.vue'
import ListPagination from '../components/ListPagination.vue'
import { useVisibilityRefresh } from '../composables/useVisibilityRefresh'
import { useAuthStore } from '../store/auth'
import { extractError, useToastsStore } from '../store/toasts'
import {
  dealContractQueueActive,
  dealContractStatusHint,
  dealContractStatusLabel,
  dealStatusClass,
} from '@/utils/deals'
import { downloadBlobResponse } from '@/utils/downloads'
import { formatMoney as fmtMoney } from '@/utils/formatters'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const router = useRouter()
const deals = ref([])
const statuses = ref([])
const operations = ref([])
const statusFilter = ref('')
const operationFilter = ref('')
const dateFromFilter = ref('')
const dateToFilter = ref('')
const dealPage = ref(1)
const dealPageSize = ref(DEFAULT_PAGE_SIZE)
const dealCount = ref(0)
const statusCounts = ref({})
const exportingDeals = ref(false)
const loadingDeals = ref(false)
const dealsLoadError = ref('')
const toasts = useToastsStore()

function formatMoney (value) {
  return fmtMoney(value, '0')
}

const filtered = computed(() => {
  return deals.value
})

const hasPendingContracts = computed(() => (
  deals.value.some((deal) => dealContractQueueActive(deal))
))

const filteredTotalCount = computed(() => (
  statusFilter.value ? (statusCounts.value[statusFilter.value] || 0) : dealCount.value
))

function countByStatus (id) {
  return statusCounts.value[id] || 0
}

function dealStatusOptions (deal) {
  const allowedIds = new Set(deal.allowed_status_ids || [])
  return statuses.value.filter((status) => allowedIds.has(status.id))
}

async function changeStatus (deal, statusId) {
  if (!statusId) return
  try {
    await api.post(`/deals/${deal.id}/change_status/`, {
      status_id: Number(statusId),
    })
    await Promise.all([load(), loadStatusCounts()])
    const nextStatus = statuses.value.find(item => String(item.id) === String(statusId))
    toasts.success(
      `Статус сделки ${deal.deal_number} обновлён`
      + (nextStatus ? `: ${nextStatus.name}` : '.'),
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить статус сделки'))
  }
}

async function downloadContract (deal) {
  try {
    const response = await api.get(`/deals/${deal.id}/contract/`, {
      responseType: 'blob',
    })
    downloadBlobResponse(response, `contract-${deal.deal_number}.pdf`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось скачать договор'))
  }
}

async function regenerate (deal) {
  try {
    await api.post(`/deals/${deal.id}/regenerate_contract/`)
    await load()
    toasts.success(`Договор для сделки ${deal.deal_number} поставлен в очередь`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось поставить договор в очередь'))
  }
}

async function load () {
  loadingDeals.value = true
  dealsLoadError.value = ''
  try {
    const { data } = await api.get('/deals/', {
      params: listParams(),
    })
    const payload = unpackPaginated(data)
    deals.value = payload.items
    if (!statusFilter.value) {
      dealCount.value = payload.count
    }
  } catch (err) {
    dealsLoadError.value = extractError(err, 'Не удалось загрузить сделки')
    toasts.error(extractError(err, 'Не удалось загрузить сделки'))
  } finally {
    loadingDeals.value = false
  }
}

async function loadStatuses () {
  try {
    const [statusesResponse, operationsResponse] = await Promise.all([
      api.get('/deal-statuses/', {
        params: { page_size: LOOKUP_PAGE_SIZE },
      }),
      api.get('/operation-types/', {
        params: { page_size: LOOKUP_PAGE_SIZE },
      }),
    ])
    statuses.value = unpackPaginated(statusesResponse.data).items
    operations.value = unpackPaginated(operationsResponse.data).items
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить статусы сделок'))
  }
}

async function fetchDealCount (params = {}) {
  const { data } = await api.get('/deals/', {
    params: { page: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadStatusCounts () {
  try {
    const baseParams = baseFilterParams()
    const requests = [
      fetchDealCount(baseParams),
      ...statuses.value.map((status) => fetchDealCount({
        ...baseParams,
        status: status.id,
      })),
    ]
    const [total, ...counts] = await Promise.all(requests)
    dealCount.value = total
    const nextCounts = {}
    statuses.value.forEach((status, index) => {
      nextCounts[status.id] = counts[index]
    })
    statusCounts.value = nextCounts
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось обновить счётчики сделок'))
  }
}

function baseFilterParams () {
  const params = {}
  if (operationFilter.value) {
    params.operation_type = Number(operationFilter.value)
  }
  if (dateFromFilter.value) {
    params.date_from = dateFromFilter.value
  }
  if (dateToFilter.value) {
    params.date_to = dateToFilter.value
  }
  return params
}

function listParams () {
  const params = {
    ...baseFilterParams(),
    page: dealPage.value,
    page_size: dealPageSize.value,
  }
  if (statusFilter.value) {
    params.status = Number(statusFilter.value)
  }
  return params
}

function dealExportParams () {
  const params = listParams()
  delete params.page
  delete params.page_size
  return params
}

function resetFilters () {
  statusFilter.value = ''
  operationFilter.value = ''
  dateFromFilter.value = ''
  dateToFilter.value = ''
}

function openDealRequest (deal) {
  if (!deal.request) return
  router.push(`/requests/${deal.request}`)
}

function setDealPage (page) {
  if (page < 1 || page === dealPage.value) return
  dealPage.value = page
}

function setDealPageSize (size) {
  if (!size || size === dealPageSize.value) return
  dealPageSize.value = size
}

async function exportDeals (format) {
  exportingDeals.value = true
  try {
    await exportEntityData(
      '/deals/export/',
      format,
      dealExportParams(),
      `deals.${format}`,
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось выгрузить сделки'))
  } finally {
    exportingDeals.value = false
  }
}

async function reloadDealsScreen () {
  await Promise.all([load(), loadStatusCounts()])
}

useVisibilityRefresh({
  enabled: () => hasPendingContracts.value,
  interval: 5_000,
  onRefresh: () => load(),
})

watch(statusFilter, async () => {
  dealPage.value = 1
  await Promise.all([load(), loadStatusCounts()])
})

watch([operationFilter, dateFromFilter, dateToFilter], async () => {
  dealPage.value = 1
  await Promise.all([load(), loadStatusCounts()])
})

watch(dealPage, async () => {
  await load()
})

watch(dealPageSize, async () => {
  if (dealPage.value !== 1) {
    dealPage.value = 1
    return
  }
  await load()
})

onMounted(async () => {
  await loadStatuses()
  await reloadDealsScreen()
})
</script>

<style scoped>
.link {
  color: #ffffff;
  font-weight: 700;
}

.link:hover {
  color: #ffffff;
  text-decoration: underline;
  text-decoration-color: rgba(255, 255, 255, 0.38);
}

.deal-filter__head {
  margin-bottom: 12px;
}

.deal-filter__actions {
  align-items: stretch;
  margin-top: 14px;
}

.deal-filter__grid {
  align-items: end;
}

.deal-filter__grid .select {
  color-scheme: light;
  background-color: #f4f8fa;
  background-image:
    var(--grad-control-light),
    linear-gradient(45deg, transparent 50%, var(--c-accent) 50%),
    linear-gradient(135deg, var(--c-accent) 50%, transparent 50%);
  background-position:
    0 0,
    calc(100% - 24px) calc(50% - 3px),
    calc(100% - 18px) calc(50% - 3px);
  background-size: 100% 100%, 6px 6px, 6px 6px;
  background-repeat: no-repeat;
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 20px rgba(16, 55, 52, 0.08);
}

.deal-filter__grid .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.deals-table {
  min-width: 1120px;
}

.deals-table .tag,
.deals-table .tag--accent,
.deals-table .deal-status--cancelled {
  min-height: 38px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(21, 56, 57, 0.16);
  background: var(--grad-control-light);
  color: var(--c-page-text);
  box-shadow: 0 8px 18px rgba(16, 55, 52, 0.08);
}

.deals-table__request-cell {
  color: var(--c-text);
  font-weight: 700;
}

.deals-table__request-cell--clickable {
  cursor: pointer;
}

.deals-table__request-cell--clickable:hover,
.deals-table__request-cell--clickable:focus-visible {
  color: var(--c-text);
  text-decoration: underline;
  text-decoration-color: rgba(244, 251, 250, 0.45);
}

.deals-table__request-cell--clickable:focus-visible {
  outline: 2px solid rgba(120, 216, 206, 0.42);
  outline-offset: -2px;
}

.deals-table__status {
  min-width: 180px;
}

.deals-table__status .select {
  width: 100%;
  min-width: 180px;
}

.deals-table__contract {
  white-space: nowrap;
}

.deals-table__contract-btn {
  min-width: 154px;
  min-height: 38px;
  padding: 7px 14px;
  border-color: rgba(21, 56, 57, 0.16);
  background: var(--grad-control-light);
  color: var(--c-page-text);
  box-shadow: 0 8px 18px rgba(16, 55, 52, 0.08);
}

.deals-table__contract-state {
  min-height: 38px;
  min-width: 154px;
  justify-content: center;
}

.deal-status--cancelled {
  border-color: rgba(194, 85, 74, 0.22);
  color: #7b4741;
}

@media (max-width: 640px) {
  .deals-table__status {
    min-width: 0;
  }

  .deals-table__status .select,
  .deals-table__contract-btn,
  .deals-table__contract-state {
    min-width: 0;
    width: 100%;
  }

  .deals-table__contract {
    white-space: normal;
  }
}
</style>
