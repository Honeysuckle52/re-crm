<template>
  <section class="stack" v-if="task">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ВЫПОЛНЕНИЕ ЗАДАЧИ №{{ task.id }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">{{ task.title }}</h1>
          <div style="color: rgba(255,255,255,.8); font-size: 14px; margin-top: 6px">
            <span class="tag tag--type" style="margin-right: 6px">
              {{ task.task_type_display || task.task_type }}
            </span>
            <span>{{ task.client_username ? 'Клиент: ' + task.client_username : 'Клиент не указан' }}</span>
            <span v-if="task.due_date"> · Срок: {{ formatDate(task.due_date) }}</span>
            <span v-if="task.process_version_label"> · {{ task.process_version_label }}</span>
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <router-link to="/tasks" class="btn">← К списку задач</router-link>
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head workflow-surface-head">
        <div>
          <div class="surface-head__meta">Маршрут выполнения</div>
          <h2 class="h3">Этапы задачи</h2>
        </div>
        <div class="surface-head__caption">Готово: {{ completedStepCount }} из {{ visibleStepCount }}</div>
      </div>
      <ol class="steps">
        <li v-for="(s, i) in steps" :key="s.id"
            class="step"
            :class="{
              'step--done': i < currentStepIdx,
              'step--active': i === currentStepIdx,
              'step--skipped': s.skipped,
            }">
          <span class="step__num">{{ i + 1 }}</span>
          <span class="step__label">{{ s.label }}</span>
          <span v-if="s.skipped" class="step__hint">пропущено</span>
        </li>
      </ol>
    </div>

    <div class="panel panel--light workflow-body">
      <template v-if="currentStep.id === 'contact'">
        <h2 class="h3">Шаг 1. Связаться с клиентом</h2>
        <p class="muted" style="margin-top: 4px">
          Зафиксируйте факт связи. После — перейдёте к работе с заявкой.
        </p>

        <div v-if="clientContacts" class="contact-card">
          <div v-if="clientContacts.phone">
            <span class="muted">Телефон: </span>
            <a :href="`tel:${clientContacts.phone}`" class="link">{{ clientContacts.phone }}</a>
          </div>
          <div v-if="clientContacts.email">
            <span class="muted">Email: </span>
            <a :href="`mailto:${clientContacts.email}`" class="link">{{ clientContacts.email }}</a>
          </div>
        </div>

        <div class="field" style="margin-top: 14px">
          <label>Комментарий (опционально)</label>
          <textarea class="textarea" v-model="contactNote" rows="2"
                    placeholder="Например: согласовали встречу на среду"></textarea>
        </div>

        <div class="row" style="gap: 8px; flex-wrap: wrap; margin-top: 12px">
          <button class="btn btn--accent" :disabled="busy"
                  @click="submitContact('called')">
            Позвонил
          </button>
          <button class="btn btn--accent" :disabled="busy"
                  @click="submitContact('messaged')">
            Написал
          </button>
          <button class="btn" :disabled="busy"
                  @click="submitContact('missed')">
            Не дозвонился
          </button>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'request'">
        <h2 class="h3">Шаг 2. Заявка клиента</h2>

        <div v-if="task.request">
          <p class="muted" style="margin-top: 4px">
            Задача связана с заявкой. Откройте её, чтобы обсудить подбор.
          </p>
          <div class="linked-request">
            <div>
              <b>Заявка №{{ task.request }}</b>
              <div class="muted" style="font-size: 13px">
                {{ linkedRequest?.status_name || '—' }} ·
                {{ linkedRequest?.operation_type_name || '—' }}
              </div>
            </div>
            <div class="row" style="gap: 6px">
              <router-link :to="`/requests/${task.request}`"
                           class="btn btn--sm btn--primary">
                Перейти к заявке
              </router-link>
              <button class="btn btn--sm btn--accent" :disabled="busy"
                      @click="submitRequestStep('linked')">
                Далее
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="clientActiveRequest">
          <p class="muted" style="margin-top: 4px">
            У клиента есть активная заявка — можно продолжить работу по ней.
          </p>
          <div class="linked-request">
            <div>
              <b>Заявка №{{ clientActiveRequest.id }}</b>
              <div class="muted" style="font-size: 13px">
                {{ clientActiveRequest.status_name }} ·
                {{ clientActiveRequest.operation_type_name }}
              </div>
            </div>
            <div class="row" style="gap: 6px">
              <router-link :to="`/requests/${clientActiveRequest.id}`"
                           class="btn btn--sm btn--primary">
                Перейти к заявке
              </router-link>
              <button class="btn btn--sm btn--accent" :disabled="busy"
                      @click="submitRequestStep('exists', clientActiveRequest.id)">
                Далее
              </button>
            </div>
          </div>
        </div>

        <div v-else>
          <p class="muted" style="margin-top: 4px">
            У клиента нет активной заявки. Создайте её из разговора.
          </p>
          <div v-if="!task.client" class="warn">
            У задачи не указан клиент — создать заявку из этого экрана
            нельзя. Укажите клиента на странице задачи.
          </div>
          <form v-else class="grid grid--2" style="margin-top: 12px"
                @submit.prevent="createRequest">
            <div class="field">
              <label>Тип операции</label>
              <select class="select" v-model.number="newRequest.operation_type" required>
                <option :value="null" disabled>— выберите —</option>
                <option v-for="o in operationTypes" :key="o.id" :value="o.id">
                  {{ o.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>Тип недвижимости</label>
              <select class="select" v-model="newRequest.property_type">
                <option value="">Выберите тип</option>
                <option value="apartment">Квартира</option>
                <option value="house">Дом</option>
                <option value="commercial">Коммерческая недвижимость</option>
                <option value="land">Земельный участок</option>
                <option value="garage">Гараж</option>
                <option value="room">Комната</option>
              </select>
            </div>
            <div class="field">
              <label>Цена от</label>
              <input class="input" type="number" v-model.number="newRequest.min_price" />
            </div>
            <div class="field">
              <label>Цена до</label>
              <input class="input" type="number" v-model.number="newRequest.max_price" />
            </div>
            <div class="field">
              <label>Комнат</label>
              <input
                class="input"
                type="number"
                v-model.number="newRequest.rooms_count"
                :disabled="isNewRequestRoomsDisabled"
                :placeholder="isNewRequestRoomsDisabled ? 'Не применяется' : ''" />
            </div>
            <div class="field">
              <label>Район / адрес</label>
              <input class="input" v-model="newRequest.address_preferences" />
            </div>
            <div class="field" style="grid-column: 1 / -1">
              <label>Пожелания</label>
              <textarea class="textarea" v-model="newRequest.description" rows="2"></textarea>
            </div>
            <div class="row" style="grid-column: 1 / -1; justify-content: flex-end">
              <button type="submit" class="btn btn--accent" :disabled="busy">
                Создать заявку и продолжить
              </button>
            </div>
          </form>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'match'">
        <h2 class="h3">Шаг 3. Подбор объекта</h2>
        <p class="muted" style="margin-top: 4px">
          Подберите объекты для клиента в заявке, затем зафиксируйте,
          какой вариант он подтвердил.
        </p>

        <div v-if="activeRequestId" class="linked-request">
          <div>
            <b>Заявка №{{ activeRequestId }}</b>
            <div class="muted" style="font-size: 13px">
              Работа с подборкой ведётся на странице заявки.
            </div>
          </div>
          <div class="row" style="gap: 6px">
            <router-link :to="`/requests/${activeRequestId}`"
                         class="btn btn--sm btn--primary">
              Открыть подборку
            </router-link>
          </div>
        </div>

        <div class="row" style="gap: 8px; flex-wrap: wrap; margin-top: 14px">
          <button class="btn btn--accent" :disabled="busy"
                  @click="submitMatchStep('proposed')">
            Предложил варианты
          </button>
          <button class="btn btn--accent" :disabled="busy"
                  @click="submitMatchStep('showing_scheduled')">
            Назначил показ
          </button>
          <button class="btn btn--accent" :disabled="busy"
                  @click="submitMatchStep('confirmed')">
            Клиент подтвердил вариант
          </button>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'complete'">
        <h2 class="h3">Шаг 4. Завершить задачу</h2>
        <p class="muted" style="margin-top: 4px">
          Опишите итог — это попадёт в историю и в отчёты.
        </p>

        <div v-if="isTerminalTask" class="notice-card" style="margin-top: 12px">
          Задача уже завершена и открыта в историческом режиме.
        </div>

        <div v-if="task.steps_log?.length" class="steps-log">
          <div v-for="(entry, i) in task.steps_log" :key="i" class="steps-log__row">
            <span class="steps-log__time">{{ formatDate(entry.at) }}</span>
            <span class="steps-log__body">
              <b>{{ stepLabel(entry.step) }}</b>
              <span v-if="entry.outcome"> — {{ outcomeLabel(entry.outcome) }}</span>
              <span v-if="entry.note" class="muted"> · {{ entry.note }}</span>
            </span>
          </div>
        </div>

        <div class="field" style="margin-top: 14px">
          <label>Результат</label>
          <textarea class="textarea" v-model="completionSummary" rows="4"
                    :disabled="isTerminalTask"
                    placeholder="Например: клиент согласился на объект №12, договорились подписать договор 20 мая"></textarea>
        </div>
        <div v-if="showingPaymentBlocked" class="warn">
          Просмотр нельзя завершить, пока оплата клиента не подтверждена.
        </div>
        <div v-if="!isTerminalTask" class="row" style="gap: 8px; justify-content: flex-end">
          <button class="btn btn--accent" :disabled="busy || showingPaymentBlocked" @click="submitComplete">
            Завершить задачу
          </button>
        </div>
      </template>

    </div>

    <AuditLogPanel
      v-if="task"
      :params="{ task: task.id }"
      title="История задачи"
      caption="Журнал действий"
      empty-text="По задаче ещё нет записей журнала."
      :page-size="12"
    />
  </section>
  <div v-else class="empty">Загрузка задачи…</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import AuditLogPanel from '../components/AuditLogPanel.vue'
import * as tasksApi from '../api/tasks'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { formatDateShort as formatDate } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import { propertyTypeUsesRooms } from '@/utils/propertyTypes'
import { activeRequestStatusCodes } from '@/utils/requestClose'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()

const task = ref(null)
const linkedRequest = ref(null)
const clientActiveRequest = ref(null)
const operationTypes = ref([])
const busy = ref(false)
const contactNote = ref('')
const completionSummary = ref('')
let loadSeq = 0

const newRequest = reactive({
  operation_type: null,
  property_type: '',
  min_price: null,
  max_price: null,
  rooms_count: null,
  address_preferences: '',
  description: '',
})

function fallbackWorkflowSteps(taskPayload) {
  const isMatchRelevant = ['property_search', 'showing'].includes(taskPayload?.task_type)
  return [
    {
      id: 'contact',
      label: 'Контакт с клиентом',
      done: false,
      current: true,
    },
    {
      id: 'request',
      label: 'Заявка',
      done: false,
      current: false,
    },
    ...(isMatchRelevant
      ? [{
          id: 'match',
          label: 'Подбор/выполнение',
          done: false,
          current: false,
        }]
      : []),
    {
      id: 'complete',
      label: 'Завершение',
      done: false,
      current: false,
    },
  ]
}

const steps = computed(() => {
  const backendSteps = task.value?.workflow_steps
  if (Array.isArray(backendSteps) && backendSteps.length) {
    return backendSteps
  }
  return fallbackWorkflowSteps(task.value)
})

const currentStepIdx = computed(() => {
  const list = steps.value
  const backendCurrentIdx = list.findIndex((step) => step.current)
  if (backendCurrentIdx >= 0) return backendCurrentIdx
  for (let i = 0; i < list.length; i += 1) {
    const s = list[i]
    if (!s.done) return i
  }
  return Math.max(list.length - 1, 0)
})
const currentStep = computed(() => (
  steps.value[currentStepIdx.value]
  || { id: task.value?.workflow_current_step || 'contact' }
))
const visibleStepCount = computed(() => (
  steps.value.length
))
const completedStepCount = computed(() => (
  steps.value.filter((step) => step.done).length
))
const isTerminalTask = computed(() => ['done', 'cancelled'].includes(task.value?.status_code))
const showingPaymentBlocked = computed(() => (
  task.value?.task_type === 'showing' && task.value?.showing_payment_status !== 'paid'
))
const isNewRequestRoomsDisabled = computed(() => !propertyTypeUsesRooms(newRequest.property_type))

const activeRequestId = computed(() => (
  task.value?.request || clientActiveRequest.value?.id || null
))

const clientContacts = ref(null)

function resetNewRequestState () {
  Object.assign(newRequest, {
    operation_type: null,
    property_type: '',
    min_price: null,
    max_price: null,
    rooms_count: null,
    address_preferences: '',
    description: '',
  })
}

function resetWorkflowState () {
  task.value = null
  linkedRequest.value = null
  clientActiveRequest.value = null
  clientContacts.value = null
  operationTypes.value = []
  busy.value = false
  contactNote.value = ''
  completionSummary.value = ''
  resetNewRequestState()
}

async function load ({ reset = false } = {}) {
  const taskId = Number(route.params.id)
  const seq = ++loadSeq

  if (reset) {
    resetWorkflowState()
  }
  if (!Number.isFinite(taskId)) {
    return
  }

  try {
    const { data } = await api.get(`/tasks/${taskId}/`)
    if (seq != loadSeq) return

    if (data.assignee !== auth.user?.id && !auth.isManager) {
      await router.replace('/tasks')
      return
    }

    task.value = data
    completionSummary.value = taskResultText(data)

    let nextOperationTypes = []
    let nextLinkedRequest = null
    let nextClientActiveRequest = null
    let directoryContacts = null
    let requestContacts = null

    const extra = []
    extra.push(api.get('/operation-types/', {
      params: { page_size: LOOKUP_PAGE_SIZE },
    }).then((r) => {
      nextOperationTypes = unpackPaginated(r.data).items
    }).catch(() => {}))

    if (data.client) {
      extra.push(api.get(`/users/${data.client}/`).then((r) => {
        directoryContacts = {
          phone: r.data.phone || null,
          email: r.data.email || null,
        }
      }).catch(() => {}))
    }

    if (data.request) {
      extra.push(api.get(`/requests/${data.request}/`).then((r) => {
        nextLinkedRequest = r.data
        requestContacts = {
          phone: r.data.client_phone || null,
          email: r.data.client_email || null,
        }
      }).catch(() => {}))
    } else if (data.client) {
      extra.push(api.get('/requests/', {
        params: {
          client: data.client,
          status_code: activeRequestStatusCodes.join(','),
          page_size: 1,
        },
      }).then((r) => {
        nextClientActiveRequest = unpackPaginated(r.data).items[0] || null
      }).catch(() => {}))
    }

    await Promise.all(extra)
    if (seq != loadSeq) return

    operationTypes.value = nextOperationTypes
    linkedRequest.value = nextLinkedRequest
    clientActiveRequest.value = nextClientActiveRequest
    clientContacts.value = {
      phone: requestContacts?.phone || directoryContacts?.phone || null,
      email: requestContacts?.email || directoryContacts?.email || null,
    }
  } catch (err) {
    if (seq != loadSeq) return
    if (reset) {
      resetWorkflowState()
    }
    toasts.error(extractError(err, 'Failed to load task.'))
  }
}

const STEP_LABELS = {
  contact:  'Контакт',
  request:  'Заявка',
  match:    'Подбор',
  complete: 'Завершение',
}
const OUTCOME_LABELS = {
  called:             'позвонил',
  messaged:           'написал',
  missed:             'не дозвонился',
  created:            'создана новая заявка',
  linked:             'связана с существующей заявкой',
  exists:             'использована активная заявка клиента',
  proposed:           'предложил варианты',
  showing_scheduled:  'назначил показ',
  confirmed:          'клиент подтвердил вариант',
}
function stepLabel (id) { return STEP_LABELS[id] || id }
function outcomeLabel (id) { return OUTCOME_LABELS[id] || id }
function taskResultText (taskPayload) {
  if (!taskPayload?.result) return ''
  if (typeof taskPayload.result === 'string') return taskPayload.result
  return taskPayload.result.summary || JSON.stringify(taskPayload.result)
}

async function submitContact (outcome) {
  busy.value = true
  const { ok, data, error } = await tasksApi.recordTaskStep(task.value.id, {
    step: 'contact',
    outcome,
    note: contactNote.value || null,
  })
  if (ok) {
    task.value = data
    contactNote.value = ''
    toasts.success('Этап «Контакт» зафиксирован')
  } else {
    toasts.error(error || 'Не удалось зафиксировать этап')
  }
  busy.value = false
}

async function submitRequestStep (outcome, requestId = null) {
  busy.value = true
  if (!task.value.request && requestId) {
    const patch = await tasksApi.patchTask(task.value.id, { request: requestId })
    if (!patch.ok) {
      toasts.error(patch.error || 'Не удалось привязать заявку')
      busy.value = false
      return
    }
    task.value = patch.data
    if (clientActiveRequest.value?.id === requestId) {
      linkedRequest.value = clientActiveRequest.value
      clientActiveRequest.value = null
      clientContacts.value = {
        phone: linkedRequest.value.client_phone || clientContacts.value?.phone || null,
        email: linkedRequest.value.client_email || clientContacts.value?.email || null,
      }
    }
  }
  const { ok, data, error } = await tasksApi.recordTaskStep(task.value.id, {
    step: 'request',
    outcome,
    note: null,
  })
  if (ok) {
    task.value = data
    toasts.success('Этап «Заявка» зафиксирован')
  } else {
    toasts.error(error || 'Не удалось зафиксировать этап')
  }
  busy.value = false
}

async function createRequest () {
  if (!task.value.client) return
  busy.value = true
  const payload = { client: task.value.client }
  if (!propertyTypeUsesRooms(newRequest.property_type)) {
    newRequest.rooms_count = null
  }
  for (const [k, v] of Object.entries(newRequest)) {
    if (v === null || v === '' || Number.isNaN(v)) continue
    payload[k] = v
  }
  try {
    const { data: req } = await api.post('/requests/', payload)
    clientActiveRequest.value = req
    linkedRequest.value = req
    clientContacts.value = {
      phone: req.client_phone || clientContacts.value?.phone || null,
      email: req.client_email || clientContacts.value?.email || null,
    }
    const patch = await tasksApi.patchTask(task.value.id, { request: req.id })
    if (!patch.ok) {
      toasts.warn(
        `Заявка №${req.id} создана, но не привязана к задаче: ${patch.error || 'неизвестная ошибка'}`,
      )
      busy.value = false
      return
    }
    task.value = patch.data
    clientActiveRequest.value = null
    const res = await tasksApi.recordTaskStep(task.value.id, {
      step: 'request',
      outcome: 'created',
      note: `Создана заявка №${req.id}`,
    })
    if (res.ok) {
      task.value = res.data
      toasts.success('Заявка создана')
    } else {
      toasts.warn(
        `Заявка №${req.id} создана и привязана, но этап не удалось зафиксировать: ${res.error || 'неизвестная ошибка'}`,
      )
    }
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось создать заявку'))
  }
  busy.value = false
}

async function submitMatchStep (outcome) {
  busy.value = true
  const { ok, data, error } = await tasksApi.recordTaskStep(task.value.id, {
    step: 'match',
    outcome,
    note: null,
  })
  if (ok) {
    task.value = data
    toasts.success('Этап «Подбор» зафиксирован')
  } else {
    toasts.error(error || 'Не удалось зафиксировать этап')
  }
  busy.value = false
}

async function submitComplete () {
  if (showingPaymentBlocked.value) {
    toasts.warn('Нельзя завершить показ, пока оплата просмотра не подтверждена.')
    return
  }
  busy.value = true
  workload.optimisticCompleteTask(task.value.id)
  const payload = completionSummary.value
    ? { summary: completionSummary.value }
    : { summary: 'Задача выполнена' }
  const { ok, error } = await tasksApi.completeTask(task.value.id, payload)
  busy.value = false
  if (ok) {
    toasts.success('Задача завершена')
    router.push('/tasks')
  } else {
    workload.refresh()
    toasts.error(error || 'Не удалось завершить задачу')
  }
}

watch(() => route.params.id, () => {
  void load({ reset: true })
}, { immediate: true })

watch(() => newRequest.property_type, (value) => {
  if (!propertyTypeUsesRooms(value)) {
    newRequest.rooms_count = null
  }
})
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

.tag--type {
  background: rgba(99, 208, 197, 0.14);
  color: #effffd;
  font-size: 11px;
  border-color: rgba(99, 208, 197, 0.2);
}

.workflow-surface-head {
  margin-bottom: 14px;
}

.steps {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  counter-reset: step;
}
.step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  color: var(--c-text-muted);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-size: 13px;
  font-weight: 600;
}
.step__num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--c-ink-soft);
  font-weight: 700;
  font-size: 12px;
}
.step__hint {
  font-size: 11px;
  color: var(--c-text-muted);
  font-style: italic;
}
.step--done {
  background: rgba(99, 208, 197, 0.14);
  color: #effffd;
  border-color: rgba(99, 208, 197, 0.2);
}
.step--done .step__num {
  background: rgba(99, 208, 197, 0.22);
  color: #effffd;
}
.step--active {
  background: var(--grad-accent);
  color: #143634;
  border-color: rgba(255, 255, 255, 0.14);
  box-shadow: 0 10px 24px rgba(46, 159, 152, 0.14);
}
.step--active .step__num {
  background: rgba(4, 21, 32, 0.12);
  color: #143634;
}
.step--skipped {
  opacity: .55;
  text-decoration: line-through;
}

.workflow-body {
  min-height: 240px;
}

.contact-card {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 14px;
}

.linked-request {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.warn {
  margin-top: 12px;
  border: 1px solid rgba(255, 111, 134, 0.24);
  background: rgba(255, 111, 134, 0.12);
  color: #ffd6de;
  padding: 10px 14px;
  border-radius: 18px;
  font-size: 13px;
}

.steps-log {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}
.steps-log__row {
  display: flex;
  gap: 10px;
  align-items: baseline;
}
.steps-log__time {
  color: var(--c-text-muted);
  font-size: 12px;
  flex: 0 0 auto;
  min-width: 90px;
}

.steps-log__body b {
  font-weight: 700;
  color: var(--c-text);
}

@media (max-width: 720px) {
  .linked-request {
    align-items: flex-start;
  }

  .steps-log__row {
    flex-direction: column;
    gap: 4px;
  }

  .steps-log__time {
    min-width: 0;
  }
}

</style>
