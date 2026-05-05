<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Заявки</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ auth.isStaff ? 'Заявки клиентов' : 'Мои заявки' }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            {{ auth.isStaff
              ? 'Распределяйте заявки между агентами, следите за воронкой и закрывайте обращения без потери контекста.'
              : 'Здесь собраны все ваши обращения в агентство и текущий статус по каждому из них.' }}
          </div>
        </div>
        <button class="btn btn--accent" @click="toggleForm">
          {{ showForm ? 'Скрыть форму' : '+ Новая заявка' }}
        </button>
      </div>
    </div>

    <div class="kpi-strip">
      <article v-for="item in requestStats" :key="item.label"
               class="kpi-card" :class="{ 'kpi-card--accent': item.accent }">
        <div class="kpi-card__label">{{ item.label }}</div>
        <div class="kpi-card__value">{{ item.value }}</div>
        <div class="kpi-card__meta">{{ item.meta }}</div>
      </article>
    </div>

    <div v-if="auth.isStaff" class="panel panel--light">
      <div class="surface-head requests-head">
        <div class="surface-head__meta">
          <h2 class="h3">Область просмотра</h2>
          <div class="muted">Переключайтесь между общей очередью, неразобранными и своими заявками.</div>
        </div>
      </div>
      <div class="row requests-tabs" style="gap: 8px; flex-wrap: wrap">
        <button v-for="t in staffTabs" :key="t.value"
                class="btn btn--sm"
                :class="{ 'btn--primary': scope === t.value }"
                @click="scope = t.value">
          {{ t.label }} ({{ t.count }})
        </button>
      </div>
    </div>

    <form v-if="showForm" class="panel panel--light stack"
          @submit.prevent="createRequest">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Создание заявки</h2>
          <div class="muted">
            {{ auth.isStaff
              ? 'Можно сразу назначить клиента, агента и привязать конкретный объект.'
              : 'Укажите параметры поиска и пожелания, после чего агент подхватит заявку в работу.' }}
          </div>
        </div>
      </div>

      <div class="grid grid--3 request-form__grid">
        <div v-if="auth.isStaff" class="field">
          <label>Клиент</label>
          <select class="select" v-model.number="form.client" required>
            <option :value="null" disabled>— выберите —</option>
            <option v-for="c in clients" :key="c.id" :value="c.id">
              {{ c.username }}
            </option>
          </select>
        </div>
        <div v-if="auth.isStaff" class="field">
          <label>Агент</label>
          <select class="select" v-model.number="form.agent">
            <option :value="null">— не назначен —</option>
            <option v-for="a in agents" :key="a.id" :value="a.id">
              {{ a.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Операция</label>
          <select class="select" v-model.number="form.operation_type" required>
            <option v-for="o in operations" :key="o.id" :value="o.id">
              {{ o.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Конкретный объект</label>
          <select class="select" v-model.number="form.property">
            <option :value="null">— подбор по критериям —</option>
            <option v-for="p in properties" :key="p.id" :value="p.id">
              {{ p.title || 'Объект №' + p.id }} · {{ formatMoney(p.price) }} ₽
            </option>
          </select>
        </div>
        <div class="field">
          <label>Тип недвижимости</label>
          <input class="input" v-model="form.property_type"
                 placeholder="Квартира, дом, коммерция" />
        </div>
        <div class="field">
          <label>Комнат</label>
          <input class="input" type="number" v-model.number="form.rooms_count" />
        </div>
        <div class="field request-form__budget">
          <label>Цена от / до</label>
          <div class="request-form__budget-row">
            <input class="input" type="number" v-model.number="form.min_price" />
            <input class="input" type="number" v-model.number="form.max_price" />
          </div>
        </div>
      </div>

      <div class="field">
        <label>Пожелания</label>
        <textarea class="textarea" v-model="form.description" rows="3"></textarea>
      </div>

      <div v-if="formError" class="error">{{ formError }}</div>

      <div class="row" style="justify-content: flex-end">
        <button class="btn btn--accent" type="submit">Создать заявку</button>
      </div>
    </form>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Список заявок</h2>
          <div class="muted">Показано {{ visibleRequests.length }} заявок в текущем режиме.</div>
        </div>
        <div class="surface-head__caption">
          Быстрые действия по взятию и закрытию заявок доступны прямо из таблицы.
        </div>
      </div>

      <div class="table-wrap">
        <table class="table requests-table">
          <thead>
            <tr>
              <th>#</th>
              <th v-if="auth.isStaff">Клиент</th>
              <th>Агент</th>
              <th>Объект</th>
              <th>Операция</th>
              <th>Бюджет</th>
              <th>Статус</th>
              <th>Создана</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in visibleRequests" :key="r.id">
              <td>
                <router-link :to="`/requests/${r.id}`" class="link">
                  #{{ r.id }}
                </router-link>
              </td>
              <td v-if="auth.isStaff">{{ r.client_username }}</td>
              <td>
                <span v-if="r.agent_username">{{ r.agent_username }}</span>
                <span v-else class="tag">не назначен</span>
              </td>
              <td>
                <router-link v-if="r.property"
                             :to="`/properties/${r.property}`" class="link">
                  {{ r.property_title || 'Объект №' + r.property }}
                </router-link>
                <span v-else class="muted">подбор</span>
              </td>
              <td>{{ r.operation_type_name }}</td>
              <td>{{ formatMoney(r.min_price) }}–{{ formatMoney(r.max_price) }} ₽</td>
              <td><span class="tag" :class="statusClass(r)">{{ r.status_name }}</span></td>
              <td class="muted">
                {{ new Date(r.created_at).toLocaleDateString('ru-RU') }}
              </td>
              <td>
                <div class="row requests-table__actions" style="gap: 6px; flex-wrap: wrap">
                  <button v-if="auth.isStaff && !r.agent"
                          class="btn btn--sm btn--accent"
                          :disabled="takeDisabled"
                          :title="takeDisabled
                            ? 'Достигнут лимит активных заявок (' + workload.activeRequestsLabel + ')'
                            : 'Взять заявку в работу'"
                          @click="takeRequest(r)">
                    Взять
                  </button>
                  <button v-if="auth.isStaff && r.can_close"
                          class="btn btn--sm btn--danger"
                          @click="closeRequest(r)">
                    Закрыть
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!visibleRequests.length" class="empty">
        {{ emptyLabel }}
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney } from '@/utils/formatters'

const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToastsStore()

const requests = ref([])
const clients = ref([])
const agents = ref([])
const operations = ref([])
const properties = ref([])

const showForm = ref(false)
const formError = ref('')
const scope = ref('all')

const form = reactive(defaultForm())

function defaultForm () {
  return {
    client: null,
    agent: null,
    operation_type: null,
    property: null,
    property_type: '',
    rooms_count: null,
    min_price: null,
    max_price: null,
    description: '',
  }
}

const staffTabs = computed(() => [
  { value: 'all', label: 'Все', count: requests.value.length },
  {
    value: 'unassigned',
    label: 'Неразобранные',
    count: requests.value.filter(r => !r.agent).length,
  },
  {
    value: 'mine',
    label: 'Мои',
    count: requests.value.filter(r => r.agent === auth.user?.id).length,
  },
])

const visibleRequests = computed(() => {
  if (!auth.isStaff) return requests.value
  if (scope.value === 'unassigned') return requests.value.filter(r => !r.agent)
  if (scope.value === 'mine') return requests.value.filter(r => r.agent === auth.user?.id)
  return requests.value
})

const openCount = computed(() =>
  requests.value.filter(r => ['new', 'processing'].includes(r.status_code)).length,
)

const closedCount = computed(() =>
  requests.value.filter(r => r.status_code === 'closed').length,
)

const requestStats = computed(() => {
  if (auth.isStaff) {
    return [
      {
        label: 'Всего заявок',
        value: requests.value.length,
        meta: 'Полный объём обращений в текущем контуре.',
      },
      {
        label: 'В работе',
        value: openCount.value,
        meta: 'Активные обращения, требующие действий команды.',
        accent: true,
      },
      {
        label: 'Неразобранные',
        value: requests.value.filter(r => !r.agent).length,
        meta: 'Заявки без закреплённого сотрудника.',
      },
      {
        label: 'Мои заявки',
        value: requests.value.filter(r => r.agent === auth.user?.id).length,
        meta: auth.isManager
          ? 'Личный участок работы администратора/менеджера.'
          : 'Ваш текущий рабочий пул заявок.',
      },
    ]
  }

  return [
    {
      label: 'Всего обращений',
      value: requests.value.length,
      meta: 'Все заявки, отправленные вами через систему.',
    },
    {
      label: 'Активные',
      value: openCount.value,
      meta: 'Сейчас находятся в работе у агентства.',
      accent: true,
    },
    {
      label: 'Закрытые',
      value: closedCount.value,
      meta: 'Уже завершённые обращения.',
    },
  ]
})

const emptyLabel = computed(() => {
  if (!auth.isStaff) return 'Вы пока не подавали заявок.'
  if (scope.value === 'unassigned') return 'Нет нераспределённых заявок.'
  if (scope.value === 'mine') return 'У вас нет активных заявок.'
  return 'Заявок ещё не создано.'
})

const takeDisabled = computed(() =>
  !auth.isManager && !workload.workload.can_take_request,
)

function statusClass (requestItem) {
  const code = requestItem.status_code
  if (code === 'closed') return 'tag--panel'
  if (code === 'cancelled') return ''
  return 'tag--accent'
}

function toggleForm () {
  showForm.value = !showForm.value
  if (showForm.value) {
    formError.value = ''
    Object.assign(form, defaultForm())
    if (operations.value.length) {
      form.operation_type = operations.value[0].id
    }
  }
}

async function load () {
  const requestsReq = api.get('/requests/')
  const operationsReq = api.get('/operation-types/')
  const propertiesReq = api.get('/properties/')
  const clientsReq = auth.isStaff
    ? api.get('/users/', { params: { user_type: 'client' } })
    : Promise.resolve({ data: [] })
  const agentsReq = auth.isStaff
    ? api.get('/users/', { params: { user_type: 'employee' } })
    : Promise.resolve({ data: [] })

  const [r, c, a, o, p] = await Promise.all([
    requestsReq, clientsReq, agentsReq, operationsReq, propertiesReq,
  ])
  requests.value = r.data.results || r.data
  clients.value = c.data.results || c.data
  agents.value = a.data.results || a.data
  operations.value = o.data.results || o.data
  properties.value = p.data.results || p.data
  if (operations.value.length && !form.operation_type) {
    form.operation_type = operations.value[0].id
  }
}

async function createRequest () {
  formError.value = ''
  try {
    const payload = { ...form }
    if (!auth.isStaff) {
      delete payload.client
      delete payload.agent
    }
    if (!payload.property) delete payload.property
    await api.post('/requests/', payload)
    showForm.value = false
    Object.assign(form, defaultForm())
    if (operations.value.length) form.operation_type = operations.value[0].id
    await load()
    toasts.success('Заявка создана')
  } catch (err) {
    formError.value = err.response?.data
      ? Object.values(err.response.data).flat().join(' ')
      : 'Не удалось создать заявку.'
    toasts.error(extractError(err, 'Не удалось создать заявку'))
  }
}

async function takeRequest (requestItem) {
  if (!auth.isManager && !workload.workload.can_take_request) {
    toasts.warn(
      `Нельзя взять заявку: уже ${workload.workload.active_requests} в работе `
      + `из ${workload.workload.max_active_requests}. Закройте текущую.`,
    )
    return
  }

  try {
    await api.post(`/requests/${requestItem.id}/take/`)
    toasts.success(`Заявка #${requestItem.id} взята в работу`)
  } catch (err) {
    toasts.error(
      extractError(err, 'Не удалось взять заявку. Возможно, превышен лимит.'),
    )
  }

  await Promise.all([load(), workload.refresh()])
}

async function closeRequest (requestItem) {
  if (!confirm('Закрыть заявку?')) return

  try {
    const res = await api.post(`/requests/${requestItem.id}/close/`)
    if (res?.data?.deal?.deal_number) {
      toasts.success(
        `Заявка закрыта. Создана сделка ${res.data.deal.deal_number}, договор готов к скачиванию.`,
      )
    } else {
      toasts.success(`Заявка #${requestItem.id} закрыта`)
    }
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось закрыть заявку'))
  }

  await Promise.all([load(), workload.refresh()])
}

onMounted(async () => {
  await load()
  if (auth.isStaff) await workload.refresh()
})
</script>

<style scoped>
.requests-head {
  margin-bottom: 12px;
}

.requests-tabs {
  align-items: stretch;
}

.request-form__grid {
  align-items: start;
}

.request-form__budget {
  max-width: 420px;
}

.request-form__budget-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.requests-table__actions {
  min-width: 148px;
}

.link {
  color: var(--c-accent);
  font-weight: 600;
}

.link:hover {
  color: var(--c-accent-2);
  text-decoration: underline;
  text-decoration-color: rgba(99, 208, 197, 0.5);
}

@media (max-width: 960px) {
  .request-form__budget {
    max-width: none;
  }
}

@media (max-width: 640px) {
  .request-form__budget-row {
    grid-template-columns: 1fr;
  }
}
</style>
