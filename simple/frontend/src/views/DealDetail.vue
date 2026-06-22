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
            v-if="deal.contract_url || deal.contract_status === 'ready'"
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

        <div v-if="auth.isStaff" class="deal-edit">
          <div class="row row--between deal-edit__head">
            <h2 class="h3">Данные для договора</h2>
            <button
              class="btn btn--sm"
              type="button"
              @click="toggleEdit"
            >
              {{ editMode ? 'Скрыть форму' : 'Изменить' }}
            </button>
          </div>

          <form v-if="editMode" class="stack deal-edit__form" @submit.prevent="saveDeal">
            <RemoteLookupField
              v-model="editForm.client"
              label="Клиент услуги"
              placeholder="Найти клиента по ФИО"
              endpoint="/users/"
              :params="{ user_type: 'client' }"
              :map-option="mapClientOption"
              :disabled="saving"
            />

            <div class="deal-participants">
              <div class="row row--between deal-participants__head">
                <div>
                  <div class="deal-owners__title">Стороны договора</div>
                  <div class="muted">Покупатель / продавец или арендатор / арендодатель.</div>
                </div>
                <div class="row deal-participants__toolbar">
                  <button class="btn btn--sm" type="button" :disabled="saving" @click="applyOwnersToParticipants">
                    Подставить владельцев
                  </button>
                  <button class="btn btn--sm" type="button" :disabled="saving" @click="addParticipant">
                    Добавить сторону
                  </button>
                </div>
              </div>

              <div v-if="editForm.participants.length" class="stack" style="margin-top: 12px">
                <div
                  v-for="(participant, index) in editForm.participants"
                  :key="participant.key"
                  class="deal-participants__row"
                >
                  <div class="field">
                    <label>Роль</label>
                    <select v-model.number="participant.role" class="select" :disabled="saving">
                      <option :value="null" disabled>Выберите роль</option>
                      <option v-for="role in filteredParticipantRoleOptions" :key="role.id" :value="role.id">
                        {{ role.name }}
                      </option>
                    </select>
                  </div>

                  <RemoteLookupField
                    v-model="participant.client"
                    label="Клиент"
                    placeholder="Найти клиента по ФИО"
                    endpoint="/users/"
                    :params="{ user_type: 'client' }"
                    :map-option="mapClientOption"
                    :disabled="saving"
                  />

                  <button class="btn btn--sm" type="button" :disabled="saving" @click="removeParticipant(index)">
                    Удалить
                  </button>
                </div>
              </div>

              <div v-else class="muted" style="margin-top: 12px">
                Используются базовые данные сделки. Добавьте стороны, если договор нужно настроить точно.
              </div>
            </div>

            <div class="field">
              <label>Объект сделки</label>
              <div class="row deal-edit__property-actions">
                <button
                  class="btn btn--sm btn--accent"
                  type="button"
                  :disabled="saving"
                  @click="propertyPickerOpen = true"
                >
                  {{ editForm.property ? 'Изменить объект' : 'Выбрать объект' }}
                </button>
                <button
                  v-if="editForm.property"
                  class="btn btn--sm"
                  type="button"
                  :disabled="saving"
                  @click="clearSelectedProperty"
                >
                  Сбросить
                </button>
              </div>
              <div class="muted deal-edit__property-label">
                {{ editForm.property ? selectedPropertyLabel : 'Объект еще не выбран.' }}
              </div>
            </div>

            <div v-if="editPropertyOwners.length" class="deal-owners">
              <div class="deal-owners__title">Владельцы объекта</div>
              <div class="stack" style="margin-top: 10px">
                <div
                  v-for="owner in editPropertyOwners"
                  :key="`${owner.property}-${owner.client_profile}`"
                  class="deal-owners__row"
                >
                  <div>
                    <b>{{ formatOwnerName(owner) }}</b>
                    <div class="muted">
                      {{ owner.client_username || '—' }}
                      <span v-if="owner.ownership_share !== null && owner.ownership_share !== undefined">
                        · {{ owner.ownership_share }}%
                      </span>
                    </div>
                  </div>
                  <div class="muted deal-owners__contacts">
                    {{ formatOwnerContacts(owner) }}
                  </div>
                </div>
              </div>
            </div>

            <div class="grid grid--2">
              <div class="field">
                <label>Сумма сделки, ₽</label>
                <input v-model.number="editForm.price_final" class="input" type="number" min="0" step="0.01" :disabled="saving" />
              </div>
              <div class="field">
                <label>Комиссия, %</label>
                <input v-model.number="editForm.commission_percent" class="input" type="number" min="0" max="100" step="0.01" :disabled="saving" />
              </div>
              <div class="field">
                <label>Сумма комиссии, ₽</label>
                <input v-model.number="editForm.commission_amount" class="input" type="number" min="0" step="0.01" :disabled="saving" />
              </div>
              <div class="field">
                <label>Дата сделки</label>
                <input v-model="editForm.deal_date" class="input" type="date" :disabled="saving" />
              </div>
            </div>

            <div class="field">
              <label>Примечание</label>
              <textarea v-model="editForm.notes" class="textarea" rows="3" :disabled="saving"></textarea>
            </div>

            <div class="row deal-edit__actions">
              <button class="btn btn--accent" type="submit" :disabled="saving">
                {{ saving ? 'Сохраняем...' : 'Сохранить и обновить договор' }}
              </button>
              <button class="btn" type="button" :disabled="saving" @click="resetEditForm">
                Сбросить
              </button>
            </div>
          </form>
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
            <span class="muted">Адрес объекта</span>
            <span>{{ deal.property_full_address || '—' }}</span>
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

    <PropertyPickerModal
      v-if="propertyPickerOpen"
      :selected-id="editForm.property"
      @select="selectProperty"
      @close="propertyPickerOpen = false"
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
import PropertyPickerModal from '../components/PropertyPickerModal.vue'
import RemoteLookupField from '../components/RemoteLookupField.vue'
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
const saving = ref(false)
const editMode = ref(false)
const propertyPickerOpen = ref(false)
const selectedPropertyLabel = ref('')
const editPropertyOwners = ref([])
const participantRoleOptions = ref([])
const editForm = ref(emptyEditForm())

const filteredParticipantRoleOptions = computed(() => {
  const operationName = (deal.value?.operation_type_name || '').toLowerCase()
  const roleCodeMap = new Map(participantRoleOptions.value.map((role) => [role.id, role.code]))
  if (operationName.includes('аренд')) {
    return participantRoleOptions.value.filter((role) => ['tenant', 'landlord'].includes(role.code))
  }
  if (operationName.includes('прод') || operationName.includes('покуп')) {
    return participantRoleOptions.value.filter((role) => ['buyer', 'seller'].includes(role.code))
  }
  const usedCodes = new Set(editForm.value.participants.map((item) => roleCodeMap.get(item.role)).filter(Boolean))
  if (usedCodes.has('tenant') || usedCodes.has('landlord')) {
    return participantRoleOptions.value.filter((role) => ['tenant', 'landlord'].includes(role.code))
  }
  return participantRoleOptions.value.filter((role) => ['buyer', 'seller'].includes(role.code))
})

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

function emptyEditForm() {
  return {
    client: null,
    property: null,
    price_final: null,
    commission_percent: null,
    commission_amount: null,
    deal_date: '',
    notes: '',
    participants: [],
  }
}

function formatMoney(value) {
  return fmtMoney(value, '0')
}

function formatDate(value) {
  return fmtDate(value)
}

function mapClientOption(user) {
  return {
    id: user.id,
    label: user.full_name || user.email || `Клиент #${user.id}`,
    hint: '',
  }
}

function formatOwnerName(owner) {
  return [owner.client_last_name, owner.client_first_name, owner.client_middle_name].filter(Boolean).join(' ') || owner.client_username || '—'
}

function formatOwnerContacts(owner) {
  return [owner.client_phone, owner.client_email].filter(Boolean).join(' · ') || '—'
}

function syncEditForm() {
  if (!deal.value) {
    editForm.value = emptyEditForm()
    selectedPropertyLabel.value = ''
    editPropertyOwners.value = []
    return
  }
  editForm.value = {
    client: deal.value.client ?? null,
    property: deal.value.property ?? null,
    price_final: deal.value.price_final ?? null,
    commission_percent: deal.value.commission_percent ?? null,
    commission_amount: deal.value.commission_amount ?? null,
    deal_date: deal.value.deal_date || '',
    notes: deal.value.notes || '',
    participants: (deal.value.participants || []).map((participant, index) => ({
      key: participant.id || `${participant.role || 'role'}-${participant.client || 'client'}-${index}`,
      role: participant.role ?? null,
      client: participant.client ?? null,
    })),
  }
  selectedPropertyLabel.value = deal.value.property
    ? `${deal.value.property_title || `Объект #${deal.value.property}`}${deal.value.property_full_address ? ` · ${deal.value.property_full_address}` : ''}`
    : ''
  editPropertyOwners.value = deal.value.property_owners || []
}

function addParticipant() {
  const firstRoleId = filteredParticipantRoleOptions.value[0]?.id ?? participantRoleOptions.value[0]?.id ?? null
  editForm.value.participants.push({
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role: firstRoleId,
    client: null,
  })
}

function removeParticipant(index) {
  editForm.value.participants.splice(index, 1)
}

function roleByCode(code) {
  return participantRoleOptions.value.find((role) => role.code === code) || null
}

function ownerRoleCode() {
  const operationName = (deal.value?.operation_type_name || '').toLowerCase()
  return operationName.includes('аренд') ? 'landlord' : 'seller'
}

function clientRoleCode() {
  const operationName = (deal.value?.operation_type_name || '').toLowerCase()
  return operationName.includes('аренд') ? 'tenant' : 'buyer'
}

function applyOwnersToParticipants() {
  const ownerRole = roleByCode(ownerRoleCode())
  const clientRole = roleByCode(clientRoleCode())
  const next = []

  if (clientRole && editForm.value.client) {
    next.push({
      key: `${clientRole.code}-${editForm.value.client}`,
      role: clientRole.id,
      client: editForm.value.client,
    })
  }

  for (const owner of editPropertyOwners.value) {
    if (!ownerRole || !owner.client_profile) continue
    next.push({
      key: `${ownerRole.code}-${owner.client_profile}`,
      role: ownerRole.id,
      client: owner.client_user_id || null,
    })
  }

  editForm.value.participants = next.filter((item) => item.client)
}

async function loadStatuses() {
  const { data } = await api.get('/deal-statuses/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  statuses.value = unpackPaginated(data).items
}

async function loadParticipantRoles() {
  const { data } = await api.get('/deal-participant-roles/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  participantRoleOptions.value = unpackPaginated(data).items
}

async function loadDeal() {
  loading.value = true
  try {
    const { data } = await api.get(`/deals/${route.params.id}/`)
    deal.value = data
    syncEditForm()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить карточку сделки'))
    deal.value = null
  } finally {
    loading.value = false
  }
}

function toggleEdit() {
  editMode.value = !editMode.value
  if (editMode.value) {
    syncEditForm()
  }
}

function resetEditForm() {
  syncEditForm()
}

function selectProperty(property) {
  editForm.value.property = property.id
  selectedPropertyLabel.value = `${property.title || `Объект #${property.id}`}${property.full_address ? ` · ${property.full_address}` : ''}`
  editPropertyOwners.value = property.owners || []
  if (!editForm.value.participants.length) {
    applyOwnersToParticipants()
  }
  propertyPickerOpen.value = false
}

function clearSelectedProperty() {
  editForm.value.property = null
  selectedPropertyLabel.value = ''
  editPropertyOwners.value = []
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

async function saveDeal() {
  if (!deal.value) return
  saving.value = true
  try {
    const payload = {
      client: editForm.value.client,
      property: editForm.value.property,
      price_final: editForm.value.price_final,
      commission_percent: editForm.value.commission_percent,
      commission_amount: editForm.value.commission_amount,
      deal_date: editForm.value.deal_date,
      notes: editForm.value.notes,
      participants: editForm.value.participants
        .filter((participant) => participant.role && participant.client)
        .map((participant) => ({
          role: participant.role,
          client: participant.client,
        })),
    }
    const { data } = await api.patch(`/deals/${deal.value.id}/`, payload)
    deal.value = data
    syncEditForm()
    editMode.value = false
    toasts.success(`Сделка ${deal.value.deal_number} обновлена, договор поставлен на перегенерацию`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось сохранить сделку'))
  } finally {
    saving.value = false
  }
}

useVisibilityRefresh({
  enabled: () => dealContractQueueActive(deal.value),
  interval: 5_000,
  onRefresh: () => loadDeal(),
})

watch(() => route.params.id, async () => {
  await Promise.all([loadStatuses(), loadParticipantRoles(), loadDeal()])
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

.deal-edit {
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid rgba(21, 56, 57, 0.1);
  color: var(--c-page-text);
}

.deal-edit :deep(label),
.deal-edit :deep(.field label),
.deal-edit :deep(.muted),
.deal-edit :deep(.input),
.deal-edit :deep(.textarea),
.deal-edit :deep(.select),
.deal-edit :deep(.remote-lookup__label),
.deal-edit :deep(.remote-lookup__hint),
.deal-edit :deep(.remote-lookup__value),
.deal-edit :deep(.remote-lookup__placeholder) {
  color: var(--c-page-text);
}

.deal-edit :deep(.input),
.deal-edit :deep(.textarea),
.deal-edit :deep(.select) {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)),
    linear-gradient(45deg, transparent 50%, var(--c-accent) 50%),
    linear-gradient(135deg, var(--c-accent) 50%, transparent 50%);
  border-color: rgba(21, 56, 57, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 20px rgba(16, 55, 52, 0.08);
}

.deal-edit :deep(.select option) {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.deal-edit__head {
  align-items: center;
  gap: 12px;
}

.deal-edit__form {
  margin-top: 14px;
}

.deal-edit__property-actions {
  gap: 8px;
  flex-wrap: wrap;
}

.deal-edit__property-label {
  margin-top: 8px;
}

.deal-edit__actions {
  gap: 10px;
  flex-wrap: wrap;
}

.deal-owners {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(21, 56, 57, 0.1);
  background: rgba(245, 249, 250, 0.8);
}

.deal-participants {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(21, 56, 57, 0.1);
  background: rgba(250, 252, 252, 0.9);
}

.deal-participants__head {
  align-items: center;
  gap: 12px;
}

.deal-participants__row {
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
}

.deal-owners__title {
  font-weight: 700;
  color: var(--c-page-text);
}

.deal-owners__row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.deal-owners__contacts {
  text-align: right;
  color: var(--c-page-text);
}

.deal-owners__row b,
.deal-participants__head,
.deal-participants__row,
.deal-participants .muted,
.deal-edit__property-label {
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
  .deal-contract-card__head,
  .deal-owners__row,
  .deal-participants__row {
    align-items: flex-start;
    flex-direction: column;
  }

  .deal-detail__contract-btn {
    min-width: 0;
    width: 100%;
  }
}
</style>
