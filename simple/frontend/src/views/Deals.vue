<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">Сделки</div>
      <h1 class="h2 deals-hero__title">
        {{ auth.isClient ? 'Мои сделки' : 'Журнал сделок' }}
      </h1>
    </div>

    <div class="panel panel--light">
      <div class="surface-head deals-head">
        <div class="surface-head__meta">
          <h2 class="h3">Фильтры сделок</h2>
          <div class="muted">
            Ищите сделки по клиенту, объекту, этапу и дате без перегруженной панели действий.
          </div>
        </div>
        <button class="btn btn--sm btn--ghost" type="button" @click="resetFilters">
          Сбросить
        </button>
      </div>

      <div class="grid grid--4 deals-filters-grid">
        <div class="field deals-filters-grid__search">
          <label>Поиск</label>
          <input
            v-model.trim="searchFilter"
            class="input"
            type="search"
            placeholder="ФИО клиента, объект или номер сделки"
          />
        </div>

        <div class="field">
          <label>Статус</label>
          <select v-model="statusFilter" class="select">
            <option value="">Все статусы</option>
            <option v-for="status in statuses" :key="status.id" :value="String(status.id)">
              {{ status.name }} ({{ countByStatus(status.id) }})
            </option>
          </select>
        </div>

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
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Сделки в работе</h2>
          <div class="muted">
            Показано {{ filtered.length }} из {{ filteredTotalCount }} записей по текущему фильтру.
          </div>
        </div>
      </div>

      <DataFetchPanel
        v-if="dealsLoadError && filtered.length"
        class="table-state"
        compact
        :error="dealsLoadError"
        error-title="Список сделок обновлён не полностью"
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
          <colgroup>
            <col class="deals-table__col deals-table__col--client" />
            <col class="deals-table__col deals-table__col--property" />
            <col class="deals-table__col deals-table__col--operation" />
            <col class="deals-table__col deals-table__col--price" />
            <col class="deals-table__col deals-table__col--commission" />
            <col class="deals-table__col deals-table__col--status" />
            <col class="deals-table__col deals-table__col--date" />
            <col class="deals-table__col deals-table__col--contract" />
            <col class="deals-table__col deals-table__col--actions" />
          </colgroup>
          <thead>
            <tr>
              <th>Клиент</th>
              <th>Объект</th>
              <th>Тип</th>
              <th>Стоимость, ₽</th>
              <th>Комиссия</th>
              <th>Статус</th>
              <th>Дата</th>
              <th>Договор</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="deal in filtered" :key="deal.id">
              <td
                class="deals-table__client-cell"
                :class="{ 'deals-table__client-cell--clickable': deal.request }"
                data-label="Клиент"
                :role="deal.request ? 'link' : undefined"
                :tabindex="deal.request ? 0 : undefined"
                @click="openDealRequest(deal)"
                @keydown.enter="openDealRequest(deal)"
                @keydown.space.prevent="openDealRequest(deal)"
              >
                <div class="deals-table__client-name">
                  {{ deal.client_full_name || deal.client_username || '—' }}
                </div>
                <div class="muted deals-table__subline">
                  Сделка №{{ deal.deal_number || deal.id }}
                </div>
                <div v-if="deal.request" class="muted deals-table__subline">
                  Заявка №{{ deal.request }}
                </div>
              </td>

              <td data-label="Объект">
                <router-link
                  v-if="deal.property"
                  :to="`/properties/${deal.property}`"
                  class="deals-table__property-link"
                >
                  {{ deal.property_title || `Объект №${deal.property}` }}
                </router-link>
                <span v-else class="muted">—</span>
              </td>

              <td class="deals-table__type-cell" data-label="Тип">
                <span class="tag tag--accent deals-table__badge deals-table__badge--full">
                  {{ deal.operation_type_name || '—' }}
                </span>
              </td>

              <td data-label="Стоимость">
                {{ formatMoney(deal.price_final) }}
              </td>

              <td data-label="Комиссия">
                <div>{{ deal.commission_percent || '—' }}%</div>
                <div class="muted deals-table__subline">
                  {{ deal.commission_amount ? `${formatMoney(deal.commission_amount)} ₽` : '—' }}
                </div>
              </td>

              <td class="deals-table__type-cell" data-label="Статус">
                <span class="tag deals-table__badge deals-table__badge--full" :class="dealStatusClass(deal.status_name)">
                  {{ deal.status_name || '—' }}
                </span>
              </td>

              <td class="muted" data-label="Дата">
                {{ formatDate(deal.deal_date) }}
              </td>

              <td class="deals-table__contract" data-label="Договор">
                <button
                  v-if="deal.contract_url"
                  class="btn btn--sm deals-table__contract-btn"
                  :title="dealContractStatusHint(deal)"
                  @click="downloadContract(deal)"
                >
                  Скачать PDF
                </button>
                <button
                  v-else-if="dealContractQueueActive(deal)"
                  class="btn btn--sm deals-table__contract-btn"
                  disabled
                  :title="dealContractStatusHint(deal)"
                >
                  {{ dealContractStatusLabel(deal) }}
                </button>
                <button
                  v-else-if="auth.isStaff"
                  class="btn btn--sm btn--ghost deals-table__contract-btn"
                  :title="dealContractStatusHint(deal)"
                  @click="regenerate(deal)"
                >
                  {{ deal.contract_status === 'failed' ? 'Повторить генерацию' : 'Поставить в очередь' }}
                </button>
                <span
                  v-else
                  class="tag deals-table__contract-state"
                  :title="dealContractStatusHint(deal)"
                >
                  {{ dealContractStatusLabel(deal) }}
                </span>
              </td>

              <td class="deals-table__actions-cell" data-label="Действия">
                <div class="deals-table__actions">
                  <div class="deals-table__primary-action">
                    <router-link :to="`/deals/${deal.id}`" class="btn btn--sm btn--accent deals-table__open">
                      Открыть
                    </router-link>
                  </div>

                  <div v-if="auth.isStaff" class="deal-more" :class="{ 'is-open': openStatusMenuId === deal.id }">
                    <button
                      class="btn btn--sm deal-more__trigger"
                      type="button"
                      @click="toggleStatusMenu(deal.id)"
                    >
                      ...
                    </button>
                    <div class="deal-more__menu">
                      <button
                        v-for="status in dealStatusOptions(deal)"
                        :key="status.id"
                        class="deal-more__item"
                        type="button"
                        :disabled="String(status.id) === String(deal.status)"
                        @click="changeStatus(deal, status.id)"
                      >
                        {{ status.name }}
                      </button>
                    </div>
                  </div>

                  <span v-else class="muted deals-table__readonly">только просмотр</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!loadingDeals && !dealsLoadError && !filtered.length" class="empty">
        Сделок по выбранному фильтру нет.
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
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
import { formatMoney as fmtMoney, formatDate } from '@/utils/formatters'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const router = useRouter()
const toasts = useToastsStore()

const deals = ref([])
const statuses = ref([])
const operations = ref([])
const searchFilter = ref('')
const statusFilter = ref('')
const operationFilter = ref('')
const dateFromFilter = ref('')
const dateToFilter = ref('')
const dealPage = ref(1)
const dealPageSize = ref(DEFAULT_PAGE_SIZE)
const dealCount = ref(0)
const statusCounts = ref({})
const loadingDeals = ref(false)
const dealsLoadError = ref('')
const openStatusMenuId = ref(null)

function formatMoney(value) {
  return fmtMoney(value, '0')
}

const filtered = computed(() => deals.value)

const hasPendingContracts = computed(() => (
  deals.value.some((deal) => dealContractQueueActive(deal))
))

const filteredTotalCount = computed(() => (
  statusFilter.value ? (statusCounts.value[statusFilter.value] || 0) : dealCount.value
))

function countByStatus(id) {
  return statusCounts.value[id] || 0
}

function dealStatusOptions(deal) {
  const allowedIds = new Set(deal.allowed_status_ids || [])
  return statuses.value.filter((status) => allowedIds.has(status.id))
}

function toggleStatusMenu(dealId) {
  openStatusMenuId.value = openStatusMenuId.value === dealId ? null : dealId
}

function closeStatusMenu() {
  openStatusMenuId.value = null
}

async function changeStatus(deal, statusId) {
  if (!statusId) return
  closeStatusMenu()
  try {
    await api.post(`/deals/${deal.id}/change_status/`, {
      status_id: Number(statusId),
    })
    await Promise.all([load(), loadStatusCounts()])
    const nextStatus = statuses.value.find((item) => String(item.id) === String(statusId))
    toasts.success(
      `Статус сделки ${deal.deal_number || deal.id} обновлён`
      + (nextStatus ? `: ${nextStatus.name}` : '.'),
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить статус сделки'))
  }
}

async function downloadContract(deal) {
  try {
    const response = await api.get(`/deals/${deal.id}/contract/`, {
      responseType: 'blob',
    })
    downloadBlobResponse(response, `contract-${deal.deal_number || deal.id}.pdf`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось скачать договор'))
  }
}

async function regenerate(deal) {
  try {
    await api.post(`/deals/${deal.id}/regenerate_contract/`)
    await load()
    toasts.success(`Договор для сделки ${deal.deal_number || deal.id} поставлен в очередь`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось поставить договор в очередь'))
  }
}

async function load() {
  loadingDeals.value = true
  dealsLoadError.value = ''
  closeStatusMenu()
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

async function loadStatuses() {
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

async function fetchDealCount(params = {}) {
  const { data } = await api.get('/deals/', {
    params: { page: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadStatusCounts() {
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

function baseFilterParams() {
  const params = {}
  if (searchFilter.value) {
    params.search = searchFilter.value
  }
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

function listParams() {
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

function resetFilters() {
  searchFilter.value = ''
  statusFilter.value = ''
  operationFilter.value = ''
  dateFromFilter.value = ''
  dateToFilter.value = ''
}

function openDealRequest(deal) {
  if (!deal.request) return
  router.push(`/requests/${deal.request}`)
}

function setDealPage(page) {
  if (page < 1 || page === dealPage.value) return
  dealPage.value = page
}

function setDealPageSize(size) {
  if (!size || size === dealPageSize.value) return
  dealPageSize.value = size
}

async function reloadDealsScreen() {
  await Promise.all([load(), loadStatusCounts()])
}

function handleDocumentClick(event) {
  const target = event.target
  if (!(target instanceof Element) || !target.closest('.deal-more')) {
    closeStatusMenu()
  }
}

useVisibilityRefresh({
  enabled: () => hasPendingContracts.value,
  interval: 5_000,
  onRefresh: () => load(),
})

watch([statusFilter, operationFilter, dateFromFilter, dateToFilter, searchFilter], async () => {
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
  document.addEventListener('click', handleDocumentClick)
  await loadStatuses()
  await reloadDealsScreen()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.deals-hero__title {
  color: #fff;
  margin-top: 8px;
}

.deals-head {
  margin-bottom: 12px;
}

.deals-filters-grid {
  align-items: end;
  grid-template-columns: minmax(240px, 1.4fr) repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.deals-filters-grid__search {
  min-width: 0;
}

.deals-filters-grid .select {
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

.deals-filters-grid .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.deals-table {
  table-layout: fixed;
}

.deals-table__col--client {
  width: 17%;
}

.deals-table__col--property {
  width: 18%;
}

.deals-table__col--operation {
  width: 10%;
}

.deals-table__col--price {
  width: 11%;
}

.deals-table__col--commission {
  width: 12%;
}

.deals-table__col--status {
  width: 11%;
}

.deals-table__col--date {
  width: 9%;
}

.deals-table__col--contract {
  width: 12%;
}

.deals-table__col--actions {
  width: 170px;
}

.deals-table td,
.deals-table th {
  vertical-align: middle;
}

.deals-table__client-cell {
  min-width: 0;
  color: var(--c-text);
}

.deals-table__client-cell--clickable {
  cursor: pointer;
}

.deals-table__client-cell--clickable:hover,
.deals-table__client-cell--clickable:focus-visible {
  text-decoration: underline;
  text-decoration-color: rgba(244, 251, 250, 0.45);
}

.deals-table__client-cell--clickable:focus-visible {
  outline: 2px solid rgba(120, 216, 206, 0.42);
  outline-offset: -2px;
}

.deals-table__client-name {
  font-weight: 700;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deals-table__subline {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deals-table__property-link,
.deals-table__property-link:hover {
  color: #ffffff;
  font-weight: 600;
}

.deals-table__badge,
.deals-table__contract-state {
  min-height: 38px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(21, 56, 57, 0.16);
  background: var(--grad-control-light);
  color: var(--c-page-text);
  box-shadow: 0 8px 18px rgba(16, 55, 52, 0.08);
}

.deals-table__badge--full {
  display: flex;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  justify-content: center;
  text-align: center;
  white-space: normal;
  line-height: 1.2;
  overflow-wrap: anywhere;
  word-break: break-word;
  hyphens: auto;
  padding: 9px 12px;
  border-radius: 18px;
}

.deals-table__type-cell {
  min-width: 0;
}

.deals-table__contract {
  min-width: 0;
}

.deals-table__contract-btn {
  width: 100%;
  min-width: 154px;
  min-height: 38px;
  padding: 7px 14px;
  border-color: rgba(21, 56, 57, 0.16);
  background: var(--grad-control-light);
  color: #17302f;
  box-shadow: 0 8px 18px rgba(16, 55, 52, 0.08);
  white-space: nowrap;
  line-height: 1.2;
  font-weight: 700;
  text-align: center;
  justify-content: center;
}

.deals-table__contract-btn.btn--ghost {
  color: #17302f;
}

.deals-table__contract-state {
  display: inline-flex;
  width: 100%;
  min-width: 154px;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}

.deals-table__actions-cell {
  min-width: 0;
}

.deals-table__actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.deals-table__primary-action {
  display: flex;
  flex: 1 1 0;
  min-width: 0;
}

.deals-table__open {
  width: 100%;
  min-width: 88px;
  color: #17302f;
  font-weight: 700;
}

.deals-table__open:hover,
.deals-table__open:focus-visible {
  color: #17302f;
}

.deals-table__readonly {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  font-size: 12px;
  white-space: nowrap;
}

.deal-more {
  position: relative;
  flex: 0 0 auto;
}

.deal-more__trigger {
  min-width: 36px;
  padding-left: 10px;
  padding-right: 10px;
  font-size: 15px;
  letter-spacing: 0.08em;
}

.deal-more__menu {
  display: none;
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 60;
  min-width: 188px;
  padding: 4px;
  border-radius: 14px;
  border: 1px solid var(--c-border-strong);
  background: var(--grad-panel);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: 0 16px 36px rgba(4, 24, 22, 0.28);
}

.deal-more.is-open .deal-more__menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.deal-more__item {
  display: block;
  width: 100%;
  padding: 9px 14px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--c-text);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.deal-more__item:hover:not(:disabled) {
  background: rgba(99, 208, 197, 0.1);
  color: #effffd;
}

.deal-more__item:disabled {
  opacity: 0.55;
  cursor: default;
}

@media (max-width: 980px) {
  .deals-filters-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .deals-filters-grid {
    grid-template-columns: 1fr;
  }

  .deals-table__actions {
    flex-wrap: wrap;
  }

  .deals-table__primary-action {
    flex: 1 1 100%;
  }

  .deals-table__open,
  .deals-table__contract-btn,
  .deals-table__contract-state {
    width: 100%;
  }

  .deals-table__contract-btn,
  .deals-table__contract-state {
    min-width: 0;
    white-space: normal;
  }

  .deals-table__client-name,
  .deals-table__subline {
    white-space: normal;
  }
}
</style>
