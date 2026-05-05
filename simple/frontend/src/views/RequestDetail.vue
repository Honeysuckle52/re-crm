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
          <button v-if="auth.isStaff && !request.agent"
                  class="btn btn--accent"
                  @click="takeRequest">
            Взять в работу
          </button>
          <button v-if="auth.isStaff && request.can_close"
                  class="btn btn--danger"
                  @click="closeRequest">
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
            ? `${relatedDeal.status_name || 'Статус не указан'} · ${relatedDeal.contract_url ? 'договор готов' : 'без PDF'}`
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
          <InfoRow label="Комнат" :value="request.rooms_count || '—'" />
          <InfoRow
            label="Бюджет"
            :value="formatMoney(request.min_price) + '–' + formatMoney(request.max_price) + ' ₽'"
          />
          <InfoRow label="Закрыта" :value="request.closed_at ? formatDate(request.closed_at) : '—'" />
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
            <router-link to="/deals" class="link">
              {{ relatedDeal.deal_number }}
            </router-link>
            <div class="muted" style="font-size: 13px">
              {{ relatedDeal.status_name || 'Статус не указан' }} ·
              {{ formatMoney(relatedDeal.price_final) }} ₽
            </div>
            <div class="muted" style="font-size: 12px">
              {{ relatedDeal.contract_url ? 'Договор уже сформирован.' : 'PDF-договор ещё не сформирован.' }}
            </div>
          </div>
          <div class="row deal-summary__actions" style="gap: 8px; flex-wrap: wrap">
            <button v-if="relatedDeal.contract_url"
                    class="btn btn--sm"
                    @click="downloadDealContract(relatedDeal)">
              Скачать PDF
            </button>
            <router-link to="/deals" class="btn btn--sm btn--ghost">
              Открыть сделки
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
        <div v-if="auth.isStaff" class="row" style="gap: 8px">
          <select class="select select--sm" v-model.number="attachPropertyId">
            <option :value="null" disabled>— выберите объект —</option>
            <option v-for="propertyItem in availableProperties" :key="propertyItem.id" :value="propertyItem.id">
              {{ propertyItem.title || 'Объект №' + propertyItem.id }} · {{ formatMoney(propertyItem.price) }} ₽
            </option>
          </select>
          <input class="input"
                 v-model="attachNote"
                 placeholder="Комментарий агента" />
          <button class="btn btn--sm btn--accent"
                  :disabled="!attachPropertyId"
                  @click="attachProperty">
            + Добавить
          </button>
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
  </section>
  <div v-else class="empty">Загрузка заявки…</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import InfoRow from '../components/InfoRow.vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney, formatDate } from '@/utils/formatters'
import {
  takeRequest as takeRequestAction,
  acceptRequestMatch,
} from '../api/tasks'

const route = useRoute()
const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()

const request = ref(null)
const availableProperties = ref([])
const requestTasks = ref([])
const relatedDeal = ref(null)
const attachPropertyId = ref(null)
const attachNote = ref('')
const confirmingId = ref(null)

const statusClass = computed(() => {
  const code = request.value?.status_code
  if (code === 'closed') return 'tag--panel'
  if (code === 'cancelled') return ''
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

async function load () {
  const requestId = Number(route.params.id)
  try {
    const calls = [
      api.get(`/requests/${requestId}/`),
      api.get('/properties/'),
      api.get('/deals/', { params: { page_size: 200 } }).catch(() => ({ data: [] })),
    ]
    if (auth.isStaff) {
      calls.push(api.get('/tasks/', { params: { request: requestId } })
        .catch(() => ({ data: [] })))
    }
    const [requestResponse, propertiesResponse, dealsResponse, tasksResponse] = await Promise.all(calls)
    request.value = requestResponse.data
    availableProperties.value = propertiesResponse.data.results || propertiesResponse.data
    const allDeals = dealsResponse.data.results || dealsResponse.data
    relatedDeal.value = allDeals.find((item) => item.request === requestId) || null
    if (tasksResponse) {
      const allTasks = tasksResponse.data.results || tasksResponse.data
      requestTasks.value = allTasks.filter((item) => item.request === requestId)
    } else {
      requestTasks.value = []
    }
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось загрузить заявку'))
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

async function closeRequest () {
  if (!confirm('Закрыть заявку?')) return
  try {
    const response = await api.post(`/requests/${route.params.id}/close/`)
    if (response?.data?.deal?.deal_number) {
      toasts.success(
        `Заявка закрыта. Создана сделка ${response.data.deal.deal_number}, договор готов к скачиванию.`,
      )
    } else {
      toasts.success('Заявка закрыта')
    }
    await Promise.all([load(), workload.refresh()])
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось закрыть заявку'))
  }
}

async function attachProperty () {
  if (!attachPropertyId.value) return
  try {
    await api.post(`/requests/${route.params.id}/attach_property/`, {
      property_id: attachPropertyId.value,
      agent_note: attachNote.value,
    })
    attachPropertyId.value = null
    attachNote.value = ''
    toasts.success('Объект добавлен в подборку')
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось добавить объект'))
  }
}

async function detachProperty (match) {
  if (!confirm('Убрать объект из подборки?')) return
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

.select--sm,
.input {
  font-size: 13px;
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

  .match-actions {
    width: 100%;
  }
}
</style>
