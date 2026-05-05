<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">Сделки</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">Журнал сделок</h1>
      <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
        Воронка продаж: от подтверждённого варианта до договора и смены статуса сделки.
      </div>
    </div>

    <div class="kpi-strip">
      <article v-for="item in dealStats" :key="item.label"
               class="kpi-card" :class="{ 'kpi-card--accent': item.accent }">
        <div class="kpi-card__label">{{ item.label }}</div>
        <div class="kpi-card__value">{{ item.value }}</div>
        <div class="kpi-card__meta">{{ item.meta }}</div>
      </article>
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
          <div class="muted">Показано {{ filtered.length }} записей по текущему фильтру.</div>
        </div>
        <div class="surface-head__caption">
          Смена статуса и работа с договором доступны без перехода на отдельный экран.
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
              <td>
                <button v-if="deal.contract_url"
                        class="btn btn--sm"
                        @click="downloadContract(deal)">
                  Скачать PDF
                </button>
                <button v-else
                        class="btn btn--sm btn--ghost"
                        @click="regenerate(deal)"
                        title="Сгенерировать PDF-договор">
                  Сформировать
                </button>
                <div v-if="deal.contract_generated_at" class="muted deals-table__contract-meta">
                  {{ new Date(deal.contract_generated_at).toLocaleDateString('ru-RU') }}
                </div>
              </td>
              <td class="deals-table__status">
                <select class="select select--sm" :value="deal.status"
                        @change="changeStatus(deal, $event.target.value)">
                  <option disabled value="">Изменить статус</option>
                  <option v-for="s in statuses" :key="s.id" :value="s.id">
                    {{ s.name }}
                  </option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!filtered.length" class="empty">
        Сделок по выбранному статусу нет.
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney as fmtMoney } from '@/utils/formatters'

const deals = ref([])
const statuses = ref([])
const statusFilter = ref('')
const toasts = useToastsStore()

function formatMoney (value) {
  return fmtMoney(value, '0')
}

const filtered = computed(() => {
  if (!statusFilter.value) return deals.value
  return deals.value.filter(deal => deal.status === statusFilter.value)
})

const contractsReady = computed(() =>
  deals.value.filter(deal => !!deal.contract_url).length,
)

const totalAmount = computed(() =>
  deals.value.reduce((sum, deal) => sum + Number(deal.price_final || 0), 0),
)

const totalCommission = computed(() =>
  deals.value.reduce((sum, deal) => sum + Number(deal.commission_amount || 0), 0),
)

const activeDeals = computed(() =>
  deals.value.filter(deal => {
    const normalized = (deal.status_name || '').toLowerCase()
    return !normalized.includes('заверш') && !normalized.includes('отмен')
  }).length,
)

const dealStats = computed(() => [
  {
    label: 'Всего сделок',
    value: deals.value.length,
    meta: 'Полный журнал оформленных и текущих сделок.',
  },
  {
    label: 'В работе',
    value: activeDeals.value,
    meta: 'Сделки, которые ещё не завершены.',
    accent: true,
  },
  {
    label: 'Сумма сделок',
    value: formatMoney(totalAmount.value) + ' ₽',
    meta: 'Общий объём по финальной стоимости.',
  },
  {
    label: 'Комиссия',
    value: formatMoney(totalCommission.value) + ' ₽',
    meta: `PDF готово: ${contractsReady.value} из ${deals.value.length}`,
  },
])

function countByStatus (id) {
  return deals.value.filter(deal => deal.status === id).length
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
    await load()
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
    toasts.success(`Договор для сделки ${deal.deal_number} сформирован`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось сформировать договор'))
  }
}

async function load () {
  try {
    const [dealsResponse, statusesResponse] = await Promise.all([
      api.get('/deals/'),
      api.get('/deal-statuses/'),
    ])
    deals.value = dealsResponse.data.results || dealsResponse.data
    statuses.value = statusesResponse.data.results || statusesResponse.data
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить сделки'))
  }
}

onMounted(load)
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

.deal-filter__head {
  margin-bottom: 12px;
}

.deal-filter__actions {
  align-items: stretch;
}

.deals-table {
  min-width: 1120px;
}

.deals-table__sub {
  font-size: 11px;
}

.deals-table__contract-meta {
  margin-top: 6px;
  font-size: 11px;
}

.deals-table__status {
  min-width: 180px;
}

.deal-status--cancelled {
  border-color: rgba(194, 85, 74, 0.26);
  background: rgba(194, 85, 74, 0.14);
  color: #ffd8d1;
}
</style>
