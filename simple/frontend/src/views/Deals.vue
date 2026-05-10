<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">Сделки</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">Журнал сделок</h1>
    </div>

    <div class="panel panel--light">
      <div class="surface-head deal-filter__head">
        <div class="surface-head__meta">
          <h2 class="h3">Фильтр по статусам</h2>
          <div class="muted">Оставьте только нужный участок воронки и работайте с ним прямо из таблицы.</div>
        </div>
      </div>
      <div class="row deal-filter__actions" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn--sm"
                :class="{ 'btn--primary': statusFilter === '' }"
                @click="statusFilter = ''">
          Все ({{ deals.length }})
        </button>
        <button v-for="s in statuses" :key="s.id"
                class="btn btn--sm"
                :class="{ 'btn--primary': statusFilter === s.id }"
                @click="statusFilter = s.id">
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
        <div class="row" style="gap: 8px; flex-wrap: wrap">
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
              <th>Номер</th>
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
              <td data-label="Номер">
                <router-link :to="`/deals/${deal.id}`" class="link">
                  <b>{{ deal.deal_number }}</b>
                </router-link>
                <div v-if="deal.request" class="muted deals-table__sub">
                  из заявки
                  <router-link :to="`/requests/${deal.request}`" class="link">
                    #{{ deal.request }}
                  </router-link>
                </div>
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
const deals = ref([])
const statuses = ref([])
const statusFilter = ref('')
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
    const { data } = await api.get('/deal-statuses/', {
      params: { page_size: LOOKUP_PAGE_SIZE },
    })
    statuses.value = unpackPaginated(data).items
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
    const requests = [
      fetchDealCount(),
      ...statuses.value.map((status) => fetchDealCount({ status: status.id })),
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

function listParams () {
  const params = {
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
  await load()
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
  color: #f4fbfa;
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

.deals-table__sub {
  font-size: 11px;
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
