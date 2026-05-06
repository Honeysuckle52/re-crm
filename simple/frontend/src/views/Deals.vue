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
      </div>

      <div class="table-wrap">
        <table class="table deals-table">
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
              <td>
                <b>{{ deal.deal_number }}</b>
                <div v-if="deal.request" class="muted deals-table__sub">
                  из заявки
                  <router-link :to="`/requests/${deal.request}`" class="link">
                    #{{ deal.request }}
                  </router-link>
                </div>
              </td>
              <td>
                <router-link v-if="deal.property" :to="`/properties/${deal.property}`" class="link">
                  {{ deal.property_title || 'Объект №' + deal.property }}
                </router-link>
                <span v-else class="muted">—</span>
              </td>
              <td><span class="tag tag--accent">{{ deal.operation_type_name }}</span></td>
              <td>{{ formatMoney(deal.price_final) }}</td>
              <td>
                {{ deal.commission_percent || '—' }}%
                <span class="muted">
                  ({{ deal.commission_amount ? formatMoney(deal.commission_amount) + ' ₽' : '—' }})
                </span>
              </td>
              <td>
                <span class="tag" :class="statusClass(deal.status_name)">
                  {{ deal.status_name || '—' }}
                </span>
              </td>
              <td class="muted">
                {{ new Date(deal.deal_date).toLocaleDateString('ru-RU') }}
              </td>
              <td class="deals-table__contract">
                <button v-if="deal.contract_url"
                        class="btn btn--sm deals-table__contract-btn"
                        :title="contractStatusHint(deal)"
                        @click="downloadContract(deal)">
                  Скачать PDF
                </button>
                <button v-else-if="contractQueueActive(deal)"
                        class="btn btn--sm deals-table__contract-btn"
                        disabled
                        :title="contractStatusHint(deal)">
                  {{ contractStatusLabel(deal) }}
                </button>
                <button v-else-if="auth.isStaff"
                        class="btn btn--sm btn--ghost deals-table__contract-btn"
                        :title="contractStatusHint(deal)"
                        @click="regenerate(deal)">
                  {{ deal.contract_status === 'failed' ? 'Повторить генерацию' : 'Поставить в очередь' }}
                </button>
                <span v-else
                      class="tag deals-table__contract-state"
                      :title="contractStatusHint(deal)">
                  {{ contractStatusLabel(deal) }}
                </span>
              </td>
              <td class="deals-table__status">
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

      <div v-if="!filtered.length" class="empty">
        Сделок по выбранному статусу нет.
      </div>

      <ListPagination
        v-if="filteredTotalCount > filtered.length"
        :count="filteredTotalCount"
        :page="dealPage"
        :visible-count="filtered.length"
        label="сделок"
        @change="setDealPage"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api'
import ListPagination from '../components/ListPagination.vue'
import { useAuthStore } from '../store/auth'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney as fmtMoney } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const deals = ref([])
const statuses = ref([])
const statusFilter = ref('')
const dealPage = ref(1)
const dealCount = ref(0)
const statusCounts = ref({})
const toasts = useToastsStore()

function formatMoney (value) {
  return fmtMoney(value, '0')
}

const filtered = computed(() => {
  return deals.value
})

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

function contractQueueActive (deal) {
  return ['pending', 'processing'].includes(deal.contract_status)
}

function contractStatusLabel (deal) {
  if (deal.contract_status === 'pending') return 'В очереди'
  if (deal.contract_status === 'processing') return 'Формируется'
  if (deal.contract_status === 'failed') return 'Ошибка PDF'
  if (deal.contract_url) return 'Готов'
  return 'Без PDF'
}

function contractStatusHint (deal) {
  if (deal.contract_status === 'pending') {
    return 'Договор уже поставлен в очередь на генерацию'
  }
  if (deal.contract_status === 'processing') {
    return 'Договор формируется в фоновом процессе'
  }
  if (deal.contract_status === 'failed') {
    return deal.contract_error_message || 'Предыдущая генерация завершилась ошибкой'
  }
  if (deal.contract_url) {
    return 'PDF-договор уже готов к скачиванию'
  }
  return 'Поставить PDF-договор в очередь на генерацию'
}

function statusClass (name) {
  const normalized = (name || '').toLowerCase()
  if (normalized.includes('заверш')) return 'tag--accent'
  if (normalized.includes('отмен')) return 'deal-status--cancelled'
  return ''
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
    const res = await api.get(`/deals/${deal.id}/contract/`, {
      responseType: 'blob',
    })
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `contract-${deal.deal_number}.pdf`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
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
    toasts.error(extractError(err, 'Не удалось загрузить сделки'))
  }
}

async function loadStatuses () {
  const { data } = await api.get('/deal-statuses/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  statuses.value = unpackPaginated(data).items
}

async function fetchDealCount (params = {}) {
  const { data } = await api.get('/deals/', {
    params: { page: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadStatusCounts () {
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
}

function listParams () {
  const params = { page: dealPage.value }
  if (statusFilter.value) {
    params.status = Number(statusFilter.value)
  }
  return params
}

function setDealPage (page) {
  if (page < 1 || page === dealPage.value) return
  dealPage.value = page
}

watch(statusFilter, async () => {
  dealPage.value = 1
  await load()
})

watch(dealPage, async () => {
  await load()
})

onMounted(async () => {
  await loadStatuses()
  await Promise.all([load(), loadStatusCounts()])
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
</style>
