<template>
  <section class="stack" v-if="deal">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">СДЕЛКА {{ deal.deal_number }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ deal.operation_type_name }} · {{ deal.client_username || 'клиент не указан' }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            {{ deal.deal_date ? formatDate(deal.deal_date) : 'Дата не указана' }} ·
            <span class="tag" :class="dealStatusClass(deal.status_name)">{{ deal.status_name || '—' }}</span>
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button
            v-if="deal.contract_url"
            class="btn btn--sm"
            @click="downloadContract"
          >
            Скачать PDF
          </button>
          <button
            v-else-if="auth.isStaff"
            class="btn btn--sm btn--ghost"
            :disabled="dealContractQueueActive(deal)"
            @click="regenerateContract"
          >
            {{ deal.contract_status === 'failed' ? 'Повторить генерацию' : 'Поставить в очередь' }}
          </button>
        </div>
      </div>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light">
        <h2 class="h3">Основные данные</h2>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Номер" :value="deal.deal_number" />
          <InfoRow label="Тип операции" :value="deal.operation_type_name || '—'" />
          <InfoRow label="Стоимость" :value="`${formatMoney(deal.price_final)} ₽`" />
          <InfoRow label="Комиссия" :value="commissionLabel" />
          <InfoRow label="Клиент" :value="deal.client_username || '—'" />
          <InfoRow label="Агент" :value="deal.agent_username || '—'" />
          <InfoRow label="Дата сделки" :value="deal.deal_date ? formatDate(deal.deal_date) : '—'" />
        </div>

        <div class="deal-detail__status">
          <label>Статус сделки</label>
          <select
            v-if="auth.isStaff"
            class="select"
            :value="deal.status"
            @change="changeStatus($event.target.value)"
          >
            <option disabled value="">Изменить статус</option>
            <option v-for="status in dealStatusOptions" :key="status.id" :value="status.id">
              {{ status.name }}
            </option>
          </select>
          <div v-else class="muted">{{ deal.status_name || '—' }}</div>
        </div>
      </div>

      <div class="panel panel--light">
        <h2 class="h3">Связанные сущности</h2>
        <div class="stack" style="margin-top: 12px">
          <div class="deal-detail__link-row">
            <span class="muted">Объект</span>
            <router-link v-if="deal.property" :to="`/properties/${deal.property}`" class="link">
              {{ deal.property_title || `Объект №${deal.property}` }}
            </router-link>
            <span v-else>—</span>
          </div>
          <div class="deal-detail__link-row">
            <span class="muted">Заявка</span>
            <router-link v-if="deal.request" :to="`/requests/${deal.request}`" class="link">
              #{{ deal.request }}
            </router-link>
            <span v-else>—</span>
          </div>
        </div>

        <h2 class="h3" style="margin-top: 20px">Договор</h2>
        <div class="deal-contract" style="margin-top: 12px">
          <div class="stack" style="gap: 4px; flex: 1">
            <div class="deal-contract__label">{{ dealContractStatusLabel(deal) }}</div>
            <div class="muted">{{ dealContractStatusHint(deal) }}</div>
            <div v-if="deal.contract_requested_at" class="muted" style="font-size: 12px">
              Поставлен в очередь: {{ formatDate(deal.contract_requested_at) }}
            </div>
            <div v-if="deal.contract_generated_at" class="muted" style="font-size: 12px">
              Сформирован: {{ formatDate(deal.contract_generated_at) }}
            </div>
          </div>
        </div>

        <div v-if="deal.notes" class="deal-notes">
          <h2 class="h3">Примечание</h2>
          <p class="muted">{{ deal.notes }}</p>
        </div>
      </div>
    </div>

    <AuditLogPanel
      entity-type="deal"
      :entity-id="deal.id"
      title="История сделки"
      empty-text="Для этой сделки пока нет записей в журнале."
    />
  </section>

  <section v-else class="stack">
    <div class="panel panel--light empty">
      {{ loading ? 'Загрузка сделки…' : 'Сделка не найдена.' }}
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import AuditLogPanel from '../components/AuditLogPanel.vue'
import InfoRow from '../components/InfoRow.vue'
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
import { formatDate as fmtDate, formatMoney as fmtMoney } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const route = useRoute()
const auth = useAuthStore()
const toasts = useToastsStore()

const deal = ref(null)
const statuses = ref([])
const loading = ref(false)

const dealStatusOptions = computed(() => {
  const allowedIds = new Set(deal.value?.allowed_status_ids || [])
  return statuses.value.filter((status) => allowedIds.has(status.id))
})

const commissionLabel = computed(() => {
  if (!deal.value) return '—'
  const percent = deal.value.commission_percent ? `${deal.value.commission_percent}%` : '—'
  const amount = deal.value.commission_amount ? `${formatMoney(deal.value.commission_amount)} ₽` : '—'
  return `${percent} (${amount})`
})

function formatMoney(value) {
  return fmtMoney(value, '0')
}

function formatDate(value) {
  return fmtDate(value)
}

async function loadStatuses() {
  const { data } = await api.get('/deal-statuses/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  statuses.value = unpackPaginated(data).items
}

async function loadDeal() {
  loading.value = true
  try {
    const { data } = await api.get(`/deals/${route.params.id}/`)
    deal.value = data
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить карточку сделки'))
    deal.value = null
  } finally {
    loading.value = false
  }
}

async function changeStatus(statusId) {
  if (!statusId || !deal.value) return
  try {
    await api.post(`/deals/${deal.value.id}/change_status/`, {
      status_id: Number(statusId),
    })
    await loadDeal()
    const nextStatus = statuses.value.find((item) => String(item.id) === String(statusId))
    toasts.success(
      `Статус сделки ${deal.value.deal_number} обновлён`
      + (nextStatus ? `: ${nextStatus.name}` : '.'),
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить статус сделки'))
  }
}

async function downloadContract() {
  if (!deal.value) return
  try {
    const response = await api.get(`/deals/${deal.value.id}/contract/`, {
      responseType: 'blob',
    })
    downloadBlobResponse(response, `contract-${deal.value.deal_number}.pdf`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось скачать договор'))
  }
}

async function regenerateContract() {
  if (!deal.value) return
  try {
    await api.post(`/deals/${deal.value.id}/regenerate_contract/`)
    await loadDeal()
    toasts.success(`Договор для сделки ${deal.value.deal_number} поставлен в очередь`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось поставить договор в очередь'))
  }
}

useVisibilityRefresh({
  enabled: () => dealContractQueueActive(deal.value),
  interval: 5_000,
  onRefresh: () => loadDeal(),
})

onMounted(async () => {
  await Promise.all([loadStatuses(), loadDeal()])
})
</script>

<style scoped>
.deal-detail__status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.deal-detail__link-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.deal-contract__label {
  font-size: 18px;
  font-weight: 700;
  color: var(--c-page-text);
}

.deal-notes {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(21, 56, 57, 0.1);
}

.link {
  color: #f4fbfa;
  font-weight: 700;
}

.link:hover {
  color: #ffffff;
  text-decoration: underline;
  text-decoration-color: rgba(255, 255, 255, 0.38);
}

@media (max-width: 900px) {
  .deal-detail__link-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
