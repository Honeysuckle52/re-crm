<template>
  <section v-if="deal" class="stack">
    <div class="hero deal-detail-hero">
      <div class="row row--between deal-detail-hero__row">
        <div>
          <div class="hero__eyebrow">Сделка {{ deal.deal_number }}</div>
          <h1 class="h2 deal-detail-hero__title">
            {{ deal.operation_type_name || 'Сделка' }} · {{ deal.client_full_name || deal.client_username || 'клиент не указан' }}
          </h1>
          <div class="deal-detail-hero__meta">
            {{ deal.deal_date ? formatDate(deal.deal_date) : 'Дата не указана' }}
            <span class="tag" :class="dealStatusClass(deal.status_name)">{{ deal.status_name || '—' }}</span>
          </div>
        </div>

        <div class="row deal-detail-hero__actions">
          <button
            v-if="deal.contract_url"
            class="btn btn--sm deal-detail__contract-btn"
            type="button"
            @click="downloadContract"
          >
            Скачать договор
          </button>
          <button
            v-else-if="auth.isStaff"
            class="btn btn--sm btn--ghost deal-detail__contract-btn"
            type="button"
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
        <div class="stack deal-detail__info">
          <InfoRow label="Номер сделки" :value="deal.deal_number" />
          <InfoRow label="Тип операции" :value="deal.operation_type_name || '—'" />
          <InfoRow label="Стоимость" :value="`${formatMoney(deal.price_final)} ₽`" />
          <InfoRow label="Комиссия" :value="commissionLabel" />
          <InfoRow label="Клиент" :value="deal.client_full_name || deal.client_username || '—'" />
          <InfoRow label="Агент" :value="deal.agent_full_name || deal.agent_username || '—'" />
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
        <h2 class="h3">Связанные данные</h2>

        <div class="stack deal-detail__links">
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
              №{{ deal.request }}
            </router-link>
            <span v-else>—</span>
          </div>
        </div>

        <h2 class="h3 deal-detail__section-title">Договор</h2>
        <div class="deal-contract-card">
          <div class="deal-contract-card__head">
            <div class="deal-contract-card__title">{{ dealContractStatusLabel(deal) }}</div>
            <span class="tag deal-contract-card__badge">{{ deal.contract_status_display || 'Статус не указан' }}</span>
          </div>
          <div class="muted deal-contract-card__hint">
            {{ dealContractStatusHint(deal) }}
          </div>
          <div class="deal-contract-card__meta">
            <div v-if="deal.contract_requested_at" class="muted">
              Поставлен в очередь: {{ formatDate(deal.contract_requested_at) }}
            </div>
            <div v-if="deal.contract_generated_at" class="muted">
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
      v-if="auth.isStaff"
      :params="{ deal: deal.id }"
      title="История сделки"
      empty-text="Для этой сделки пока нет записей в журнале."
    />
  </section>

  <section v-else class="stack">
    <div class="panel panel--light empty">
      {{ loading ? 'Загрузка сделки...' : 'Сделка не найдена.' }}
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
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

watch(() => route.params.id, async () => {
  await Promise.all([loadStatuses(), loadDeal()])
}, { immediate: true })
</script>

<style scoped>
.deal-detail-hero {
  padding: 24px 28px;
}

.deal-detail-hero__row {
  flex-wrap: wrap;
  gap: 12px;
}

.deal-detail-hero__title {
  color: #fff;
  margin-top: 8px;
}

.deal-detail-hero__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 14px;
  margin-top: 6px;
}

.deal-detail-hero__actions {
  gap: 8px;
  flex-wrap: wrap;
}

.deal-detail__contract-btn {
  min-width: 180px;
  color: #17302f;
  font-weight: 700;
  white-space: nowrap;
}

.deal-detail__contract-btn.btn--ghost {
  color: #17302f;
}

.deal-detail__info {
  margin-top: 12px;
}

.deal-detail__status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.deal-detail__status .select {
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

.deal-detail__status .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.deal-detail__links {
  margin-top: 12px;
}

.deal-detail__link-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.deal-detail__section-title {
  margin-top: 20px;
}

.deal-contract-card {
  margin-top: 12px;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid rgba(21, 56, 57, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(232, 240, 243, 0.94));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.86),
    0 14px 30px rgba(16, 55, 52, 0.08);
  color: var(--c-page-text);
}

.deal-contract-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.deal-contract-card__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--c-page-text);
}

.deal-contract-card__badge {
  flex: 0 0 auto;
}

.deal-contract-card__hint {
  margin-top: 8px;
  line-height: 1.35;
  color: var(--c-page-text);
}

.deal-contract-card__meta {
  margin-top: 12px;
  display: grid;
  gap: 6px;
  color: var(--c-page-text);
}

.deal-contract-card__meta .muted,
.deal-contract-card__hint.muted {
  color: var(--c-page-text);
}

.deal-notes {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(21, 56, 57, 0.1);
}

.link {
  color: #ffffff;
  font-weight: 700;
}

.link:hover {
  color: #ffffff;
  text-decoration: underline;
  text-decoration-color: rgba(255, 255, 255, 0.38);
}

@media (max-width: 900px) {
  .deal-detail__link-row,
  .deal-contract-card__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .deal-detail__contract-btn {
    min-width: 0;
    width: 100%;
  }
}
</style>
