<template>
  <section v-if="task" class="stack">
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
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn" type="button" @click="openTaskHistory">
            История задачи
          </button>
          <router-link to="/tasks" class="btn">← К списку задач</router-link>
        </div>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="'toast--' + toast.type">
        {{ toast.message }}
      </div>
    </Transition>

    <div class="panel panel--light">
      <ol class="steps">
        <li
          v-for="(step, index) in steps"
          :key="step.id"
          class="step"
          :class="{
            'step--done': step.done,
            'step--active': step.current,
          }"
        >
          <span class="step__num">{{ index + 1 }}</span>
          <span class="step__label">{{ step.label }}</span>
        </li>
      </ol>
    </div>

    <div class="panel panel--light workflow-body">
      <template v-if="currentStep.id === 'contact'">
        <h2 class="h3">Шаг {{ currentStepNumber }}. Связаться с клиентом</h2>
        <p class="muted" style="margin-top: 4px">
          Зафиксируйте контакт с клиентом и переходите к заявке.
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
          <label>Комментарий</label>
          <textarea
            v-model="contactNote"
            class="textarea"
            rows="2"
            placeholder="Например: созвонились, договорились о времени"
          />
        </div>

        <div class="row" style="gap: 8px; flex-wrap: wrap; margin-top: 12px">
          <button class="btn btn--accent" :disabled="busy" @click="submitContact('called')">
            Позвонил
          </button>
          <button class="btn btn--accent" :disabled="busy" @click="submitContact('messaged')">
            Написал
          </button>
          <button class="btn btn--accent" :disabled="busy" @click="submitContact('in_person')">
            Клиент присутствует лично
          </button>
          <button class="btn" :disabled="busy" @click="submitContact('missed')">
            Не дозвонился
          </button>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'request'">
        <h2 class="h3">Шаг {{ currentStepNumber }}. Заявка клиента</h2>

        <div v-if="task.request" class="linked-request" style="margin-top: 14px">
          <div>
            <b>Заявка №{{ task.request }}</b>
            <div class="muted" style="font-size: 13px">
              {{ linkedRequest?.status_name || '—' }} · {{ linkedRequest?.operation_type_name || '—' }}
            </div>
          </div>
          <div class="row" style="gap: 6px">
            <router-link :to="`/requests/${task.request}`" class="btn btn--sm btn--primary">
              Перейти к заявке
            </router-link>
            <button class="btn btn--sm btn--accent" :disabled="busy" @click="submitRequestStep('linked')">
              Далее
            </button>
          </div>
        </div>

        <div v-else-if="clientActiveRequest" class="linked-request" style="margin-top: 14px">
          <div>
            <b>Заявка №{{ clientActiveRequest.id }}</b>
            <div class="muted" style="font-size: 13px">
              {{ clientActiveRequest.status_name }} · {{ clientActiveRequest.operation_type_name }}
            </div>
          </div>
          <div class="row" style="gap: 6px">
            <router-link :to="`/requests/${clientActiveRequest.id}`" class="btn btn--sm btn--primary">
              Перейти к заявке
            </router-link>
            <button class="btn btn--sm btn--accent" :disabled="busy" @click="submitRequestStep('exists', clientActiveRequest.id)">
              Далее
            </button>
          </div>
        </div>

        <div v-else>
          <p class="muted" style="margin-top: 4px">
            У клиента нет активной заявки. Создайте её прямо из разговора.
          </p>
          <div v-if="!task.client" class="warn">
            У задачи не указан клиент. Сначала укажите клиента на карточке задачи.
          </div>
          <form v-else class="grid grid--2" style="margin-top: 12px" @submit.prevent="createRequest">
            <div class="field">
              <label>Тип операции</label>
              <select v-model.number="newRequest.operation_type" class="select" required>
                <option :value="null" disabled>— выберите —</option>
                <option v-for="option in operationTypes" :key="option.id" :value="option.id">
                  {{ option.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>Тип недвижимости</label>
              <input v-model="newRequest.property_type" class="input" placeholder="Квартира / дом / коммерция" />
            </div>
            <div class="field">
              <label>Цена от</label>
              <input v-model.number="newRequest.min_price" class="input" type="number" />
            </div>
            <div class="field">
              <label>Цена до</label>
              <input v-model.number="newRequest.max_price" class="input" type="number" />
            </div>
            <div class="field">
              <label>Комнат</label>
              <input v-model.number="newRequest.rooms_count" class="input" type="number" />
            </div>
            <div class="field">
              <label>Район / адрес</label>
              <input v-model="newRequest.address_preferences" class="input" />
            </div>
            <div class="field" style="grid-column: 1 / -1">
              <label>Пожелания</label>
              <textarea v-model="newRequest.description" class="textarea" rows="2" />
            </div>
            <div class="row" style="grid-column: 1 / -1; justify-content: flex-end">
              <button class="btn btn--accent" type="submit" :disabled="busy">
                Создать заявку и продолжить
              </button>
            </div>
          </form>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'match'">
        <h2 class="h3">Шаг {{ currentStepNumber }}. {{ currentStep.label }}</h2>

        <div v-if="activeRequestId" class="linked-request" style="margin-top: 14px">
          <div>
            <b>Заявка №{{ activeRequestId }}</b>
            <div class="muted" style="font-size: 13px">
              Работа по подбору ведётся на странице заявки.
            </div>
          </div>
          <div class="row" style="gap: 6px">
            <router-link :to="`/requests/${activeRequestId}`" class="btn btn--sm btn--primary">
              Открыть подборку
            </router-link>
          </div>
        </div>

        <template v-if="isShowingTask">
          <div v-if="!task.client || !task.property" class="warn" style="margin-top: 14px">
            Для назначения просмотра у задачи должны быть указаны клиент и объект.
          </div>

          <div v-else class="payment-block" style="margin-top: 20px">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px">
              Назначение реального просмотра
            </div>
            <p class="muted" style="font-size: 13px; margin-bottom: 12px">
              Агент назначает дату и комментарий прямо из задачи. После этого откроется шаг оплаты предпросмотра.
            </p>

            <div v-if="payment.loadingViewing" class="muted" style="font-size: 13px; margin-bottom: 10px">
              Ищем текущую запись просмотра…
            </div>

            <div v-if="showing.id" class="payment-status-card" style="margin-bottom: 14px">
              <div class="row" style="gap: 12px; flex-wrap: wrap; align-items: center">
                <div>
                  <div style="font-size: 12px; color: #6a7a77; margin-bottom: 2px">Просмотр</div>
                  <code style="font-size: 12px">#{{ showing.id }}</code>
                </div>
                <div v-if="showing.scheduledAt">
                  <div style="font-size: 12px; color: #6a7a77; margin-bottom: 2px">Дата</div>
                  <span>{{ formatDate(showing.scheduledAt) }}</span>
                </div>
                <div v-if="showing.statusName">
                  <div style="font-size: 12px; color: #6a7a77; margin-bottom: 2px">Статус</div>
                  <span>{{ showing.statusName }}</span>
                </div>
              </div>
              <div v-if="showing.note" class="muted" style="font-size: 13px; margin-top: 8px">
                {{ showing.note }}
              </div>
            </div>

            <form class="grid grid--2" @submit.prevent="scheduleViewing">
              <div class="field">
                <label>Дата и время показа</label>
                <input v-model="viewingForm.scheduledAt" class="input" type="datetime-local" required />
              </div>
              <div class="field">
                <label>Комментарий агента</label>
                <input
                  v-model="viewingForm.note"
                  class="input"
                  type="text"
                  placeholder="Например: клиент будет на месте за 10 минут"
                />
              </div>
              <div class="row" style="grid-column: 1 / -1; justify-content: flex-end">
                <button class="btn btn--accent" type="submit" :disabled="busy || payment.busy">
                  {{ showing.id ? 'Переназначить просмотр' : 'Назначить просмотр' }}
                </button>
              </div>
            </form>
          </div>
        </template>

        <div v-else class="row" style="gap: 8px; flex-wrap: wrap; margin-top: 14px">
          <button class="btn btn--accent" :disabled="busy" @click="submitMatchStep('proposed')">
            Предложил варианты
          </button>
          <button class="btn btn--accent" :disabled="busy" @click="submitMatchStep('showing_scheduled')">
            Назначил показ
          </button>
          <button class="btn btn--accent" :disabled="busy" @click="submitMatchStep('confirmed')">
            Клиент подтвердил вариант
          </button>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'payment'">
        <h2 class="h3">Шаг {{ currentStepNumber }}. Оплата предпросмотра</h2>
        <p class="muted" style="margin-top: 4px">
          Сформируйте ссылку на оплату и контролируйте статус платежа прямо из задачи.
        </p>

        <div class="payment-block" style="margin-top: 20px">
          <div style="font-weight: 600; font-size: 14px; margin-bottom: 8px">
            Оплата предпросмотра
          </div>

          <div v-if="payment.loadingViewing" class="muted" style="font-size: 13px">
            Ищем запись просмотра…
          </div>

          <div v-else-if="!payment.viewingId" class="warn">
            Запись просмотра не найдена. Вернитесь к шагу назначения показа и сохраните просмотр в системе.
          </div>

          <template v-else>
            <div v-if="showing.scheduledAt" class="muted" style="font-size: 13px; margin-bottom: 10px">
              Просмотр №{{ payment.viewingId }} запланирован на {{ formatDate(showing.scheduledAt) }}.
            </div>

            <div v-if="!payment.paymentId">
              <p class="muted" style="font-size: 13px; margin-bottom: 10px">
                Создайте ссылку на оплату для просмотра №{{ payment.viewingId }}.
              </p>
              <button class="btn btn--primary" :disabled="payment.busy" @click="initiatePayment()">
                {{ payment.busy ? 'Создаём ссылку…' : 'Выставить ссылку на оплату' }}
              </button>
              <div v-if="payment.error" class="warn" style="margin-top: 8px">
                {{ payment.error }}
              </div>
            </div>

            <div v-else class="payment-status-card">
              <div class="row" style="gap: 12px; flex-wrap: wrap; align-items: center">
                <div>
                  <div style="font-size: 12px; color: #6a7a77; margin-bottom: 2px">Платёж</div>
                  <code style="font-size: 12px">#{{ payment.paymentId }}</code>
                </div>
                <div>
                  <div style="font-size: 12px; color: #6a7a77; margin-bottom: 2px">Сумма</div>
                  <span>{{ paymentAmountLabel(payment.amount) }}</span>
                </div>
                <div>
                  <div style="font-size: 12px; color: #6a7a77; margin-bottom: 2px">Статус</div>
                  <span class="payment-badge" :class="paymentStatusClass(payment.status)">
                    {{ paymentStatusLabel(payment.status) }}
                  </span>
                </div>
                <a
                  v-if="payment.paymentUrl && ['pending', 'failed'].includes(payment.status)"
                  class="btn btn--sm btn--primary"
                  :href="payment.paymentUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Перейти к оплате
                </a>
                <button class="btn btn--sm" :disabled="payment.busy" @click="checkPaymentStatus()">
                  {{ payment.busy ? '…' : 'Обновить статус' }}
                </button>
              </div>
              <div v-if="payment.error" class="warn" style="margin-top: 8px">
                {{ payment.error }}
              </div>
            </div>
          </template>
        </div>
      </template>

      <template v-else-if="currentStep.id === 'complete'">
        <h2 class="h3">Шаг {{ currentStepNumber }}. Завершить задачу</h2>
        <p class="muted" style="margin-top: 4px">
          Опишите итог. Это попадёт в историю и отчёты.
        </p>

        <div v-if="task.steps_log?.length" class="steps-log">
          <div v-for="(entry, index) in task.steps_log" :key="index" class="steps-log__row">
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
          <textarea
            v-model="completionSummary"
            class="textarea"
            rows="4"
            placeholder="Например: просмотр подтверждён, клиент оплатил предпросмотр"
          />
        </div>
        <div class="row" style="gap: 8px; justify-content: flex-end">
          <button class="btn btn--accent" :disabled="busy" @click="submitComplete">
            Завершить задачу
          </button>
        </div>
      </template>
    </div>
  </section>
  <div v-else class="empty">Загрузка задачи…</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import * as tasksApi from '../api/tasks'
import * as viewingPaymentsApi from '../api/viewingPayments'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { formatDateShort as formatDate } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const workload = useWorkloadStore()

const task = ref(null)
const linkedRequest = ref(null)
const clientActiveRequest = ref(null)
const operationTypes = ref([])
const busy = ref(false)
const contactNote = ref('')
const completionSummary = ref('')
const clientContacts = ref(null)

const isShowingTask = computed(() => task.value?.task_type === 'showing')

const payment = reactive({
  viewingId: null,
  paymentId: null,
  paymentUrl: null,
  amount: null,
  status: null,
  busy: false,
  error: null,
  pollTimer: null,
  loadingViewing: false,
})

const showing = reactive({
  id: null,
  scheduledAt: null,
  statusName: null,
  note: '',
})

const viewingForm = reactive({
  scheduledAt: '',
  note: '',
})

const newRequest = reactive({
  operation_type: null,
  property_type: '',
  min_price: null,
  max_price: null,
  rooms_count: null,
  address_preferences: '',
  description: '',
})

const toast = reactive({ show: false, message: '', type: 'success' })

const FALLBACK_STEPS = {
  default: [
    { id: 'contact', label: 'Контакт с клиентом', done: false, current: true },
    { id: 'request', label: 'Заявка', done: false, current: false },
    { id: 'complete', label: 'Завершение', done: false, current: false },
  ],
  match: [
    { id: 'contact', label: 'Контакт с клиентом', done: false, current: true },
    { id: 'request', label: 'Заявка', done: false, current: false },
    { id: 'match', label: 'Подбор/выполнение', done: false, current: false },
    { id: 'complete', label: 'Завершение', done: false, current: false },
  ],
  showing: [
    { id: 'contact', label: 'Контакт с клиентом', done: false, current: true },
    { id: 'request', label: 'Заявка', done: false, current: false },
    { id: 'match', label: 'Предпросмотр объекта', done: false, current: false },
    { id: 'payment', label: 'Оплата просмотра', done: false, current: false },
    { id: 'complete', label: 'Завершение', done: false, current: false },
  ],
}

const steps = computed(() => {
  const workflowSteps = task.value?.workflow_steps
  if (Array.isArray(workflowSteps) && workflowSteps.length) {
    return workflowSteps.map(step => ({
      ...step,
      done: Boolean(step.done),
      current: Boolean(step.current),
    }))
  }
  if (isShowingTask.value) return FALLBACK_STEPS.showing
  if (task.value?.task_type === 'property_search') return FALLBACK_STEPS.match
  return FALLBACK_STEPS.default
})

const currentStepIdx = computed(() => {
  const currentId = task.value?.workflow_current_step
  if (currentId) {
    const index = steps.value.findIndex(step => step.id === currentId)
    if (index >= 0) return index
  }
  const index = steps.value.findIndex(step => step.current)
  return index >= 0 ? index : 0
})

const currentStep = computed(() => steps.value[currentStepIdx.value] || steps.value[0] || { id: 'contact', label: 'Контакт' })
const currentStepNumber = computed(() => currentStepIdx.value + 1)
const activeRequestId = computed(() => task.value?.request || clientActiveRequest.value?.id || null)

const STEP_LABELS = {
  contact: 'Контакт',
  request: 'Заявка',
  match: 'Подбор',
  payment: 'Оплата',
  complete: 'Завершение',
  completed: 'Завершение',
}

const OUTCOME_LABELS = {
  called: 'позвонил',
  messaged: 'написал',
  in_person: 'клиент присутствует лично',
  missed: 'не дозвонился',
  created: 'создана новая заявка',
  linked: 'связана с существующей заявкой',
  exists: 'использована активная заявка клиента',
  proposed: 'предложил варианты',
  showing_scheduled: 'назначил показ',
  confirmed: 'клиент подтвердил вариант',
  link_sent: 'отправил ссылку на оплату',
}

function showToast(message, type = 'success') {
  toast.message = message
  toast.type = type
  toast.show = true
  setTimeout(() => {
    toast.show = false
  }, 4000)
}

function stepLabel(id) {
  return STEP_LABELS[id] || id
}

function outcomeLabel(id) {
  return OUTCOME_LABELS[id] || id
}

function toDatetimeLocalValue(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = part => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function viewingDatePayload(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

function hydratePaymentState() {
  const currentTask = task.value
  if (!currentTask || currentTask.task_type !== 'showing') return
  showing.id = currentTask.viewing_id || showing.id
  payment.viewingId = currentTask.viewing_id || payment.viewingId
  payment.paymentId = currentTask.showing_payment_id || payment.paymentId
  payment.paymentUrl = currentTask.showing_payment_url || payment.paymentUrl
  payment.status = currentTask.showing_payment_status || payment.status
  payment.amount = currentTask.showing_payment_amount || payment.amount
}

function syncViewingState(viewing, { overwriteForm = false } = {}) {
  if (!viewing) return
  showing.id = viewing.id || showing.id
  showing.scheduledAt = viewing.scheduled_date || viewing.viewing_date || showing.scheduledAt
  showing.statusName = viewing.status_name || showing.statusName
  showing.note = viewing.notes ?? viewing.comment ?? showing.note
  payment.viewingId = viewing.id || payment.viewingId
  payment.paymentId = viewing.payment_id || payment.paymentId
  payment.paymentUrl = viewing.payment_url || payment.paymentUrl
  payment.status = viewing.payment_status || payment.status
  payment.amount = viewing.payment_amount || payment.amount
  if (overwriteForm || !viewingForm.scheduledAt) {
    viewingForm.scheduledAt = toDatetimeLocalValue(showing.scheduledAt)
  }
  if (overwriteForm || !viewingForm.note) {
    viewingForm.note = showing.note || ''
  }
}

function paymentStatusLabel(status) {
  const labels = {
    pending: 'Ожидает оплаты',
    paid: 'Оплачен',
    failed: 'Ошибка оплаты',
    refunded: 'Возврат',
  }
  return labels[status] || status || '—'
}

function paymentStatusClass(status) {
  return `payment-badge--${(status || 'pending').toLowerCase()}`
}

function paymentAmountLabel(value) {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  if (Number.isNaN(amount)) return value
  return `${amount.toLocaleString('ru-RU')} ₽`
}

async function load() {
  const taskId = route.params.id
  const { data } = await api.get(`/tasks/${taskId}/`)
  task.value = data

  if (task.value.assignee !== auth.user?.id && !auth.isManager) {
    router.replace('/tasks')
    return
  }

  if (['done', 'cancelled'].includes(task.value.status_code)) {
    router.replace('/tasks')
    return
  }

  const extra = []

  extra.push(
    api.get('/operation-types/').then(response => {
      operationTypes.value = response.data.results || response.data
    }).catch(() => {})
  )

  if (task.value.request) {
    extra.push(
      api.get(`/requests/${task.value.request}/`).then(response => {
        linkedRequest.value = response.data
        clientContacts.value = {
          phone: response.data.client_phone || null,
          email: response.data.client_email || null,
        }
      }).catch(() => {})
    )
  } else if (task.value.client) {
    extra.push(
      api.get('/requests/', {
        params: { client: task.value.client, page_size: 5 },
      }).then(response => {
        const list = response.data.results || response.data
        clientActiveRequest.value = list.find(item => item.status_code !== 'closed') || null
      }).catch(() => {})
    )
  }

  await Promise.all(extra)

  hydratePaymentState()
  if (isShowingTask.value) {
    await loadViewingForTask()
  }
}

async function submitContact(outcome) {
  busy.value = true
  const { ok, data, error } = await tasksApi.recordTaskStep(task.value.id, {
    step: 'contact',
    outcome,
    note: contactNote.value || null,
  })
  if (ok) {
    task.value = data
    contactNote.value = ''
    showToast('Этап «Контакт» зафиксирован')
  } else {
    showToast(error, 'error')
  }
  busy.value = false
}

async function submitRequestStep(outcome, requestId = null) {
  busy.value = true
  if (!task.value.request && requestId) {
    const patch = await tasksApi.patchTask(task.value.id, { request: requestId })
    if (!patch.ok) {
      showToast(patch.error || 'Не удалось привязать заявку', 'error')
      busy.value = false
      return
    }
    task.value = patch.data
  }
  const { ok, data, error } = await tasksApi.recordTaskStep(task.value.id, {
    step: 'request',
    outcome,
    note: null,
  })
  if (ok) {
    task.value = data
    showToast('Этап «Заявка» зафиксирован')
  } else {
    showToast(error, 'error')
  }
  busy.value = false
}

async function createRequest() {
  if (!task.value.client) return
  busy.value = true
  const payload = { client: task.value.client }
  for (const [key, value] of Object.entries(newRequest)) {
    if (value === null || value === '' || Number.isNaN(value)) continue
    payload[key] = value
  }
  try {
    const { data: requestObject } = await api.post('/requests/', payload)
    await tasksApi.patchTask(task.value.id, { request: requestObject.id })
    const result = await tasksApi.recordTaskStep(task.value.id, {
      step: 'request',
      outcome: 'created',
      note: `Создана заявка №${requestObject.id}`,
    })
    if (result.ok) task.value = result.data
    clientActiveRequest.value = requestObject
    showToast('Заявка создана')
  } catch (error) {
    showToast(error.response?.data?.detail || 'Не удалось создать заявку', 'error')
  }
  busy.value = false
}

async function submitMatchStep(outcome) {
  busy.value = true
  const { ok, data, error } = await tasksApi.recordTaskStep(task.value.id, {
    step: 'match',
    outcome,
    note: null,
  })
  if (ok) {
    task.value = data
    showToast('Этап «Подбор» зафиксирован')
  } else {
    showToast(error, 'error')
  }
  busy.value = false
}

async function scheduleViewing() {
  const viewingDate = viewingDatePayload(viewingForm.scheduledAt)
  if (!viewingDate) {
    showToast('Укажите дату и время просмотра', 'error')
    return
  }

  busy.value = true
  const { ok, data, error } = await tasksApi.scheduleTaskViewing(task.value.id, {
    viewing_date: viewingDate,
    note: viewingForm.note || null,
  })

  if (!ok) {
    busy.value = false
    showToast(error || 'Не удалось назначить просмотр', 'error')
    return
  }

  task.value = data.task || task.value
  syncViewingState(data.viewing, { overwriteForm: true })
  hydratePaymentState()

  if (task.value?.workflow_current_step === 'match') {
    const stepResult = await tasksApi.recordTaskStep(task.value.id, {
      step: 'match',
      outcome: 'showing_scheduled',
      note: viewingForm.note || null,
    })
    if (stepResult.ok) {
      task.value = stepResult.data
      hydratePaymentState()
      showToast('Просмотр назначен, можно переходить к оплате')
    } else {
      showToast(stepResult.error || 'Просмотр создан, но этап не удалось зафиксировать', 'error')
    }
  } else {
    showToast('Просмотр назначен')
  }

  busy.value = false
}

function openTaskHistory() {
  router.push({ path: '/tasks', query: { view: 'history' } })
}

async function submitComplete() {
  busy.value = true
  workload.optimisticCompleteTask(task.value.id)
  const payload = completionSummary.value
    ? { summary: completionSummary.value }
    : { summary: 'Задача выполнена' }
  const { ok, error } = await tasksApi.completeTask(task.value.id, payload)
  busy.value = false
  if (ok) {
    showToast('Задача завершена')
    router.push('/tasks')
  } else {
    workload.refresh()
    showToast(error || 'Не удалось завершить задачу', 'error')
  }
}

async function loadViewingForTask() {
  const currentTask = task.value
  if (!currentTask || currentTask.task_type !== 'showing') return
  if (!currentTask.client || !currentTask.property) return

  payment.loadingViewing = true
  try {
    const response = await api.get('/viewings/', {
      params: {
        client: currentTask.client,
        property: currentTask.property,
        page_size: 5,
      },
    })
    const list = response.data.results || response.data || []
    if (list.length > 0) {
      syncViewingState(list[0])
    }
  } catch (_error) {
  } finally {
    payment.loadingViewing = false
  }
}

async function refreshTaskPaymentState() {
  const { ok, data } = await tasksApi.getTask(task.value.id)
  if (!ok) return
  task.value = data
  hydratePaymentState()
  await loadViewingForTask()
}

async function initiatePayment() {
  if (!task.value?.id) return
  payment.busy = true
  payment.error = null
  const { ok, data, error } = await tasksApi.initiateViewingPayment(task.value.id)
  payment.busy = false

  if (ok) {
    task.value = data.task || task.value
    const payload = data.payment || {}
    payment.viewingId = payload.viewing || task.value.viewing_id || payment.viewingId
    payment.paymentId = payload.id || payment.paymentId
    payment.paymentUrl = payload.payment_url || payment.paymentUrl
    payment.status = payload.status || payment.status
    payment.amount = payload.amount || payment.amount

    if (task.value?.workflow_current_step === 'payment') {
      const stepResult = await tasksApi.recordTaskStep(task.value.id, {
        step: 'payment',
        outcome: 'link_sent',
        note: null,
      })
      if (stepResult.ok) {
        task.value = stepResult.data
      }
    }

    showToast('Ссылка на оплату создана')
    if (payment.paymentUrl) {
      window.open(payment.paymentUrl, '_blank', 'noopener,noreferrer')
    }
    _startPaymentPoll()
  } else {
    payment.error = error || 'Не удалось создать ссылку на оплату'
    showToast(payment.error, 'error')
  }
}

async function checkPaymentStatus() {
  if (!payment.paymentId) return
  payment.busy = true
  payment.error = null
  const { ok, data, error } = await viewingPaymentsApi.syncViewingPayment(payment.paymentId)
  payment.busy = false
  if (ok) {
    const payload = data?.payment || data || {}
    payment.paymentId = payload.id || payment.paymentId
    payment.paymentUrl = payload.payment_url || payment.paymentUrl
    payment.status = payload.status || payment.status
    payment.amount = payload.amount || payment.amount
    await refreshTaskPaymentState()
    if (payment.status === 'paid') {
      _stopPaymentPoll()
      showToast('Оплата подтверждена')
    }
  } else {
    payment.error = error || 'Не удалось получить статус'
  }
}

function _startPaymentPoll() {
  _stopPaymentPoll()
  let attempts = 0
  payment.pollTimer = setInterval(async () => {
    attempts += 1
    if (attempts > 12 || !payment.paymentId) {
      _stopPaymentPoll()
      return
    }
    const { ok, data } = await viewingPaymentsApi.syncViewingPayment(payment.paymentId)
    if (ok) {
      const payload = data?.payment || data || {}
      payment.status = payload.status || payment.status
      payment.paymentUrl = payload.payment_url || payment.paymentUrl
      payment.amount = payload.amount || payment.amount
      if (['paid', 'failed', 'refunded'].includes(payment.status)) {
        _stopPaymentPoll()
        refreshTaskPaymentState()
        if (payment.status === 'paid') showToast('Оплата подтверждена')
      }
    }
  }, 10000)
}

function _stopPaymentPoll() {
  if (payment.pollTimer) {
    clearInterval(payment.pollTimer)
    payment.pollTimer = null
  }
}

onMounted(load)
onBeforeUnmount(_stopPaymentPoll)
</script>

<style scoped>
.link { color: var(--c-accent); font-weight: 500; }
.link:hover { text-decoration: underline; }

.tag--type { background: #e8f4f3; color: #1a5a52; font-size: 11px; }

.steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 4px 0;
  list-style: none;
}

.step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  background: #f1f4f3;
  color: #6a7a77;
  font-size: 13px;
  font-weight: 500;
}

.step__num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: #dbe2e0;
  color: #546664;
  font-weight: 700;
  font-size: 12px;
}

.step--done {
  background: #e0efe9;
  color: #0f3a33;
}

.step--done .step__num {
  background: #0f3a33;
  color: #fff;
}

.step--active {
  background: #0f3a33;
  color: #fff;
}

.step--active .step__num {
  background: #3ddbc7;
  color: #0f3a33;
}

.workflow-body { min-height: 200px; }

.contact-card,
.linked-request {
  margin-top: 14px;
  padding: 14px 16px;
  background: var(--c-paper-2, #f5f7f6);
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 14px;
}

.linked-request {
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.warn {
  margin-top: 12px;
  background: #fdece9;
  color: #9a3b32;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}

.payment-block {
  padding: 16px;
  background: var(--c-paper-2, #f5f7f6);
  border-radius: 10px;
  border: 1px solid #dbe6e4;
}

.payment-status-card {
  padding: 12px 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #dbe6e4;
}

.payment-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #e8f0ef;
  color: #4a6d68;
}

.payment-badge--paid { background: #d4f5e9; color: #0a5c38; }
.payment-badge--failed,
.payment-badge--refunded { background: #fdece9; color: #9a3b32; }
.payment-badge--pending { background: #e3effe; color: #1a4b8c; }

.steps-log {
  margin-top: 12px;
  background: var(--c-paper-2, #f5f7f6);
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.steps-log__row {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.steps-log__time {
  color: #8a9a97;
  font-size: 12px;
  flex: 0 0 auto;
  min-width: 90px;
}

.steps-log__body b { font-weight: 700; color: #0f3a33; }

.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  padding: 14px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 16px rgba(0,0,0,.15);
}

.toast--success { background: #0f3a33; color: #fff; }
.toast--error { background: #c2554a; color: #fff; }

.toast-enter-active,
.toast-leave-active { transition: all .3s ease; }

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
