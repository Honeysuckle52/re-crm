<template>
  <section class="stack" v-if="request">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ЗАЯВКА №{{ request.id }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ request.operation_type_name }} ·
            {{ request.client_username }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Создана {{ formatDate(request.created_at) }} ·
            <span class="tag" :class="statusClass">{{ request.status_name }}</span>
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button v-if="auth.isStaff && canTakeRequest(request)"
                  class="btn btn--accent"
                  @click="takeRequest">
            Взять в работу
          </button>
          <button v-if="auth.isStaff && request.can_close"
                  class="btn btn--danger"
                  @click="closeDialogOpen = true">
            Закрыть заявку
          </button>
        </div>
      </div>
    </div>

    <div class="kpi-strip">
      <article class="kpi-card kpi-card--accent">
        <div class="kpi-card__label">Статус заявки</div>
        <div class="kpi-card__value">{{ request.status_name }}</div>
        <div class="kpi-card__meta">
          {{ request.agent_username ? 'Ведёт ' + request.agent_username : 'Агент пока не назначен' }}
        </div>
      </article>
      <article class="kpi-card">
        <div class="kpi-card__label">Вариантов в подборке</div>
        <div class="kpi-card__value">{{ matchesCount }}</div>
        <div class="kpi-card__meta">
          Подтверждено: {{ confirmedMatchesCount }}, в работе: {{ offeredMatchesCount }}
        </div>
      </article>
      <article class="kpi-card">
        <div class="kpi-card__label">Задач по заявке</div>
        <div class="kpi-card__value">{{ requestTasks.length }}</div>
        <div class="kpi-card__meta">
          Активных: {{ activeTasksCount }}, автозакрытых: {{ autoClosedTasksCount }}
        </div>
      </article>
      <article class="kpi-card" :class="{ 'kpi-card--accent': !!relatedDeal }">
        <div class="kpi-card__label">Сделка</div>
        <div class="kpi-card__value">{{ relatedDeal ? relatedDeal.deal_number : '—' }}</div>
        <div class="kpi-card__meta">
          {{ relatedDeal
            ? `${relatedDeal.status_name || 'Статус не указан'} · ${dealContractStatusLabel(relatedDeal)}`
            : 'Появится после закрытия заявки' }}
        </div>
      </article>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light">
        <h2 class="h3">Параметры заявки</h2>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Клиент" :value="request.client_username" />
          <InfoRow label="Агент" :value="request.agent_username || 'не назначен'" />
          <InfoRow label="Операция" :value="request.operation_type_name" />
          <InfoRow label="Тип недвижимости" :value="request.property_type || '—'" />
          <InfoRow label="Комнат" :value="formatRoomsValue(request.property_type, request.rooms_count)" />
          <InfoRow
            label="Бюджет"
            :value="formatMoney(request.min_price) + '–' + formatMoney(request.max_price) + ' ₽'"
          />
          <InfoRow label="Закрыта" :value="request.closed_at ? formatDate(request.closed_at) : '—'" />
        </div>
        <div class="request-process" style="margin-top: 16px">
          <div class="muted" style="font-size: 13px; margin-bottom: 8px">
            {{ request.process_version_label }}
          </div>
          <ol v-if="request.process_schema?.length" class="request-process__steps">
            <li
              v-for="step in request.process_schema"
              :key="step.id"
              class="request-process__step"
              :class="{ 'request-process__step--terminal': step.terminal }">
              <span>{{ step.label }}</span>
              <span v-if="step.terminal" class="request-process__hint">финал</span>
            </li>
          </ol>
        </div>
      </div>

      <div class="panel panel--light">
        <h2 class="h3">Желаемый объект</h2>
        <div v-if="request.property" class="stack" style="margin-top: 12px">
          <router-link :to="`/properties/${request.property}`" class="link">
            {{ request.property_title || 'Объект №' + request.property }}
          </router-link>
          <div class="muted">Клиент оставил заявку на конкретный объект.</div>
        </div>
        <div v-else class="muted" style="margin-top: 12px">
          Заявка на подбор: конкретный объект не указан — агент подбирает варианты.
        </div>

        <h2 class="h3" style="margin-top: 20px">Связанная сделка</h2>
        <div v-if="relatedDeal" class="deal-summary" style="margin-top: 12px">
          <div class="stack" style="gap: 4px; flex: 1">
            <router-link :to="`/deals/${relatedDeal.id}`" class="link">
              {{ relatedDeal.deal_number }}
            </router-link>
            <div class="muted" style="font-size: 13px">
              {{ relatedDeal.status_name || 'Статус не указан' }} ·
              {{ formatMoney(relatedDeal.price_final) }} ₽
            </div>
            <div class="muted" style="font-size: 12px">
              {{ dealContractStatusHint(relatedDeal) }}
            </div>
          </div>
          <div class="row deal-summary__actions" style="gap: 8px; flex-wrap: wrap">
            <button v-if="relatedDeal.contract_url"
                    class="btn btn--sm"
                    @click="downloadDealContract(relatedDeal)">
              Скачать PDF
            </button>
            <router-link :to="`/deals/${relatedDeal.id}`" class="btn btn--sm btn--ghost">
              Открыть сделку
            </router-link>
          </div>
        </div>
        <div v-else class="muted" style="margin-top: 12px">
          После закрытия заявки здесь появится связанная сделка и доступ к договору.
        </div>

        <h2 class="h3" style="margin-top: 20px">Пожелания клиента</h2>
        <p style="white-space: pre-wrap; margin-top: 8px">
          {{ request.description || 'Пожелания не указаны.' }}
        </p>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <h2 class="h3">Подборка вариантов ({{ request.matches?.length || 0 }})</h2>
        <div v-if="auth.isStaff" class="request-attach">
          <div class="request-attach__picker">
            <button
              type="button"
              class="btn btn--sm btn--ghost request-attach__trigger"
              @click="propertyPickerOpen = true"
            >
              {{ attachPropertyId ? 'Заменить объект' : 'Выбрать объект' }}
            </button>
          </div>
          <input class="input"
                 v-model="attachNote"
                 placeholder="Комментарий агента" />
          <button class="btn btn--sm btn--accent"
                  :disabled="!attachPropertyId"
                  @click="attachProperty">
            + Добавить
          </button>
          <div class="muted request-attach__hint">
            {{ attachPropertyLabel || 'Откройте модальное окно и выберите объект для подбора.' }}
          </div>
        </div>
      </div>

      <div v-if="request.matches?.length" class="match-list" style="margin-top: 14px">
        <div v-for="match in request.matches" :key="match.id" class="match">
          <div class="stack" style="gap: 4px; flex: 1">
            <router-link :to="`/properties/${match.property}`" class="link">
              {{ match.property_title || 'Объект №' + match.property }}
            </router-link>
            <div class="muted" style="font-size: 13px">
              {{ formatMoney(match.property_price) }} ₽ · предложил {{ match.agent_username }}
            </div>
            <div v-if="match.agent_note" style="font-size: 13px">
              «{{ match.agent_note }}»
            </div>
            <div class="match-badge" :class="matchBadgeClass(match)">
              {{ matchBadgeLabel(match) }}
            </div>
            <div v-if="match.is_confirmed && match.confirmed_at" class="muted" style="font-size: 12px">
              Подтвердил {{ match.confirmed_by_username || 'сотрудник' }} ·
              {{ formatDate(match.confirmed_at) }}
            </div>
          </div>
          <div v-if="auth.isStaff" class="match-actions">
            <button class="btn btn--sm btn--accent"
                    :disabled="confirmingId === match.id || !canConfirmMatch(match)"
                    title="Подтвердить выбор клиента"
                    @click="confirmProperty(match)">
              {{ match.is_confirmed ? 'Подтверждён' : 'Подтвердить' }}
            </button>
            <button class="btn btn--sm btn--danger"
                    @click="detachProperty(match)">
              Убрать
            </button>
          </div>
        </div>
      </div>
      <div v-else class="muted" style="margin-top: 12px">
        Варианты ещё не предложены.
      </div>
    </div>

    <div class="panel panel--light">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <h2 class="h3">Задачи по заявке ({{ requestTasks.length }})</h2>
        <router-link v-if="auth.isStaff" to="/tasks" class="btn btn--sm">
          Все задачи
        </router-link>
      </div>
      <div v-if="requestTasks.length" class="stack" style="margin-top: 12px">
        <div v-for="task in requestTasks" :key="task.id" class="task-row">
          <div class="stack" style="gap: 2px; flex: 1">
            <div class="row" style="gap: 8px; align-items: center">
              <b>{{ task.title }}</b>
              <span v-if="task.is_auto_closed" class="auto-badge" title="Закрыта автоматически">
                авто
              </span>
            </div>
            <div class="muted" style="font-size: 12px">
              <span class="tag tag--type">{{ task.task_type_display || task.task_type }}</span>
              Исполнитель: {{ task.assignee_username }} ·
              Срок: {{ task.due_date ? formatDate(task.due_date) : '—' }}
              <span v-if="task.is_overdue" class="tag" style="background: #fee; color: #c2554a">
                просрочено
              </span>
            </div>
            <div v-if="task.result" class="result-text">
              Результат: {{ taskResultLabel(task) }}
            </div>
          </div>
          <span class="tag tag--accent">{{ task.status_name }}</span>
        </div>
      </div>
    <div v-else class="muted" style="margin-top: 12px">
        Задач пока нет.
      </div>
    </div>

    <AuditLogPanel
      v-if="request"
      :params="{ request: request.id }"
      title="История заявки"
      caption="Журнал действий"
      empty-text="По заявке ещё нет записей журнала."
      :page-size="12"
    />
  </section>
  <PropertyPickerModal
    v-if="propertyPickerOpen"
    title="Выбор объекта для подбора"
    :selected-id="attachPropertyId"
    :params="{ ordering: '-created_at' }"
    @close="propertyPickerOpen = false"
    @select="selectAttachProperty"
  />
  <RequestCloseDialog
    v-if="closeDialogOpen && request"
    :request-id="request.id"
    :loading="closeLoading"
    @cancel="closeDialogOpen = false"
    @submit="submitCloseRequest"
  />
  <div v-if="!request" class="empty">Загрузка заявки…</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import AuditLogPanel from '../components/AuditLogPanel.vue'
import InfoRow from '../components/InfoRow.vue'
import PropertyPickerModal from '../components/PropertyPickerModal.vue'
import RequestCloseDialog from '../components/RequestCloseDialog.vue'
import { useVisibilityRefresh } from '../composables/useVisibilityRefresh'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { dealContractStatusHint, dealContractStatusLabel } from '@/utils/deals'
import { downloadBlobResponse } from '@/utils/downloads'
import { formatMoney, formatDate } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import { formatRoomsValue } from '@/utils/propertyTypes'
import {
  canTakeRequest,
  getRequestCloseSuccessMessage,
  terminalRequestStatusCodes,
} from '@/utils/requestClose'
import {
  closeRequest as closeRequestAction,
  takeRequest as takeRequestAction,
  acceptRequestMatch,
} from '../api/tasks'

const route = useRoute()
const auth = useAuthStore()
const confirm = useConfirmStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()

const request = ref(null)
const requestTasks = ref([])
const relatedDeal = ref(null)
const attachPropertyId = ref(null)
const attachPropertyLabel = ref('')
const attachNote = ref('')
const propertyPickerOpen = ref(false)
const confirmingId = ref(null)
const closeDialogOpen = ref(false)
const closeLoading = ref(false)
let loadSeq = 0

const statusClass = computed(() => {
  const code = request.value?.status_code
  if (terminalRequestStatusCodes.includes(code)) return 'tag--panel'
  return 'tag--accent'
})

const matchesCount = computed(() => request.value?.matches?.length || 0)
const confirmedMatchesCount = computed(() =>
  (request.value?.matches || []).filter((match) => match.state === 'confirmed').length,
)
const offeredMatchesCount = computed(() =>
  (request.value?.matches || []).filter((match) => ['offered', 'draft'].includes(match.state)).length,
)
const activeTasksCount = computed(() =>
  requestTasks.value.filter((task) => !['done', 'cancelled'].includes(task.status_code)).length,
)
const autoClosedTasksCount = computed(() =>
  requestTasks.value.filter((task) => task.is_auto_closed).length,
)
const hasPendingDealContract = computed(() => (
  ['pending', 'processing'].includes(relatedDeal.value?.contract_status)
))

function resetDetailState () {
  request.value = null
  requestTasks.value = []
  relatedDeal.value = null
  attachPropertyId.value = null
  attachPropertyLabel.value = ''
  attachNote.value = ''
  propertyPickerOpen.value = false
  confirmingId.value = null
  closeDialogOpen.value = false
  closeLoading.value = false
}

function matchBadgeLabel (match) {
  if (match.state === 'confirmed') return 'Подтверждён'
  if (match.state === 'rejected') return 'Отклонён'
  if (match.state === 'offered') return 'Предложен'
  return 'Черновик'
}

function matchBadgeClass (match) {
  if (match.state === 'confirmed') return 'match-badge--confirmed'
  if (match.state === 'rejected') return 'match-badge--rejected'
  return 'match-badge--offered'
}

function canConfirmMatch (match) {
  return request.value?.can_close && match.state !== 'confirmed'
}

function taskResultLabel (task) {
  if (!task?.result) return ''
  if (typeof task.result === 'string') return task.result
  return task.result.summary || task.result.detail || 'Результат сохранён'
}

function selectAttachProperty (property) {
  attachPropertyId.value = property.id
  attachPropertyLabel.value = `${property.title || `Объект №${property.id}`}${property.full_address ? ` · ${property.full_address}` : ''}`
  propertyPickerOpen.value = false
}

async function load ({ reset = false } = {}) {
  const requestId = Number(route.params.id)
  const seq = ++loadSeq

  if (reset) {
    resetDetailState()
  }
  if (!Number.isFinite(requestId)) {
    return
  }

  try {
    const calls = [
      api.get(`/requests/${requestId}/`),
      api.get('/deals/', {
        params: { request: requestId, page_size: 1 },
      }).catch(() => ({ data: [] })),
    ]
    if (auth.isStaff) {
      calls.push(api.get('/tasks/', {
        params: { request: requestId, page_size: LOOKUP_PAGE_SIZE },
      })
        .catch(() => ({ data: [] })))
    }
    const [requestResponse, dealsResponse, tasksResponse] = await Promise.all(calls)
    if (seq !== loadSeq) return

    request.value = requestResponse.data
    const allDeals = unpackPaginated(dealsResponse.data).items
    relatedDeal.value = allDeals[0] || null
    if (tasksResponse) {
      const allTasks = unpackPaginated(tasksResponse.data).items
      requestTasks.value = allTasks.filter((item) => item.request === requestId)
    } else {
      requestTasks.value = []
    }
  } catch (err) {
    if (seq !== loadSeq) return
    if (reset) {
      request.value = null
      requestTasks.value = []
      relatedDeal.value = null
    }
    toasts.error(extractError(err, 'Failed to load request.'))
  }
}
async function takeRequest () {
  const result = await takeRequestAction(route.params.id)
  if (!result.ok) {
    toasts.error(result.error || 'Не удалось взять заявку')
    return
  }
  toasts.success('Заявка взята в работу')
  await Promise.all([load(), workload.refresh()])
}

async function submitCloseRequest (outcome) {
  closeLoading.value = true
  const result = await closeRequestAction(route.params.id, outcome)
  closeLoading.value = false

  if (!result.ok) {
    toasts.error(result.error || 'Не удалось закрыть заявку')
    return
  }

  closeDialogOpen.value = false
  toasts.success(getRequestCloseSuccessMessage({
    outcome,
    data: result.data,
    requestId: request.value?.id,
  }))
  await Promise.all([load(), workload.refresh()])
}

async function attachProperty () {
  if (!attachPropertyId.value) return
  try {
    await api.post(`/requests/${route.params.id}/attach_property/`, {
      property_id: attachPropertyId.value,
      agent_note: attachNote.value,
    })
    attachPropertyId.value = null
    attachPropertyLabel.value = ''
    attachNote.value = ''
    toasts.success('Объект добавлен в подборку')
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось добавить объект'))
  }
}

async function detachProperty (match) {
  const approved = await confirm.ask({
    title: 'Удаление из подборки',
    message: 'Убрать объект из подборки?',
    confirmLabel: 'Убрать',
    danger: true,
  })
  if (!approved) return
  try {
    await api.post(`/requests/${route.params.id}/detach_property/`, {
      match_id: match.id,
    })
    toasts.success('Объект убран из подборки')
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось убрать объект'))
  }
}

async function confirmProperty (match) {
  confirmingId.value = match.id
  try {
    const result = await acceptRequestMatch(route.params.id, match.id)
    if (!result.ok) {
      toasts.error(result.error || 'Не удалось подтвердить вариант')
      return
    }
    toasts.success(
      result.data?.detail
        || 'Вариант подтверждён, задачи закрыты, письмо отправлено',
    )
    await Promise.all([load(), workload.refresh()])
  } finally {
    confirmingId.value = null
  }
}

async function downloadDealContract (deal) {
  try {
    const response = await api.get(`/deals/${deal.id}/contract/`, {
      responseType: 'blob',
    })
    downloadBlobResponse(response, `contract-${deal.deal_number}.pdf`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось скачать договор'))
  }
}

useVisibilityRefresh({
  enabled: () => hasPendingDealContract.value,
  interval: 5_000,
  onRefresh: () => { void load() },
})

watch(() => route.params.id, () => {
  void load({ reset: true })
}, { immediate: true })
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

.match-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.match {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.match:hover,
.task-row:hover {
  transform: translateY(-3px);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 18px 34px rgba(31, 163, 154, 0.12);
}

.match-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-self: center;
}

.task-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.deal-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
}

.request-process__steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.request-process__step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.05);
  font-size: 12px;
}

.request-process__step--terminal {
  border-color: rgba(99, 208, 197, 0.28);
  background: rgba(99, 208, 197, 0.1);
}

.request-process__hint {
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
}

.select--sm,
.input {
  font-size: 13px;
}

.request-attach {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(240px, 1fr) auto;
  gap: 8px 10px;
  align-items: end;
  justify-content: end;
  width: min(100%, 840px);
}

.request-attach__picker {
  display: flex;
  min-width: 0;
}

.request-attach__trigger {
  min-height: 40px;
  justify-content: center;
  width: 100%;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 20px rgba(16, 55, 52, 0.08);
}

.request-attach__trigger:hover {
  border-color: rgba(21, 56, 57, 0.24);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    0 12px 22px rgba(16, 55, 52, 0.12);
}

.request-attach__hint {
  grid-column: 1 / -1;
  max-width: 520px;
  font-size: 12px;
  line-height: 1.35;
  margin-top: -2px;
}

.request-attach > .input {
  min-width: 0;
  width: 100%;
  min-height: 40px;
}

.request-attach > .btn {
  min-height: 40px;
  white-space: nowrap;
}

.match-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  margin-top: 4px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.match-badge--confirmed {
  background: rgba(99, 208, 197, 0.16);
  color: #effffd;
  border-color: rgba(99, 208, 197, 0.24);
}

.match-badge--rejected {
  background: rgba(255, 111, 134, 0.14);
  color: #ffd3dd;
  border-color: rgba(255, 111, 134, 0.22);
}

.match-badge--offered {
  background: rgba(31, 163, 154, 0.16);
  color: #effffd;
  border-color: rgba(31, 163, 154, 0.22);
}

.auto-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid rgba(99, 208, 197, 0.2);
  background: rgba(99, 208, 197, 0.16);
  color: #effffd;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.tag--type {
  background: rgba(99, 208, 197, 0.14);
  color: #effffd;
  font-size: 10px;
  margin-right: 6px;
  border-color: rgba(99, 208, 197, 0.2);
}

.tag[style*='background: #fee'][style*='color: #c2554a'] {
  background: rgba(255, 111, 134, 0.14) !important;
  color: #ffd4dc !important;
  border-color: rgba(255, 111, 134, 0.22) !important;
}

.result-text {
  margin-top: 4px;
  color: var(--c-ink-soft);
  font-size: 12px;
  font-style: italic;
}

@media (max-width: 720px) {
  .match,
  .task-row,
  .deal-summary {
    flex-direction: column;
  }

  .request-attach {
    grid-template-columns: 1fr;
    width: 100%;
  }

  .match-actions {
    width: 100%;
  }
}
</style>
