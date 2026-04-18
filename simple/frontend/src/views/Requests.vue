<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ЗАЯВКИ</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ auth.isStaff ? 'Заявки клиентов' : 'Мои заявки' }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            {{ auth.isStaff
              ? 'Распределяйте заявки между агентами и ведите подборки объектов'
              : 'Здесь отображаются все ваши обращения к агентству' }}
          </div>
        </div>
        <button class="btn btn--accent" @click="toggleForm">
          {{ showForm ? 'Скрыть форму' : '+ Новая заявка' }}
        </button>
      </div>
    </div>

    <!-- Вкладки для сотрудника -->
    <div v-if="auth.isStaff" class="panel panel--light">
      <div class="row" style="gap: 8px; flex-wrap: wrap">
        <button v-for="t in staffTabs" :key="t.value"
                class="btn btn--sm"
                :class="{ 'btn--primary': scope === t.value }"
                @click="scope = t.value">
          {{ t.label }} ({{ t.count }})
        </button>
      </div>
    </div>

    <!-- Форма создания -->
    <form v-if="showForm" class="panel panel--light stack"
          @submit.prevent="createRequest">
      <div class="grid grid--3">
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
          <label>Агент (опционально)</label>
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
          <label>Конкретный объект (опционально)</label>
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
                 placeholder="Квартира, дом, коммерч." />
        </div>
        <div class="field">
          <label>Комнат</label>
          <input class="input" type="number" v-model.number="form.rooms_count" />
        </div>
        <div class="field">
          <label>Цена от / до</label>
          <div class="row">
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

    <!-- Список -->
    <div class="panel panel--light">
      <table class="table">
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
            <td>
              {{ formatMoney(r.min_price) }}–{{ formatMoney(r.max_price) }} ₽
            </td>
            <td><span class="tag" :class="statusClass(r)">{{ r.status_name }}</span></td>
            <td class="muted">
              {{ new Date(r.created_at).toLocaleDateString('ru-RU') }}
            </td>
            <td>
              <div class="row" style="gap: 6px; flex-wrap: wrap">
                <button v-if="auth.isStaff && !r.agent"
                        class="btn btn--sm btn--accent"
                        @click="takeRequest(r)">
                  Взять
                </button>
                <button v-if="r.can_close"
                        class="btn btn--sm btn--danger"
                        @click="closeRequest(r)">
                  Закрыть
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
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

const auth = useAuthStore()

const requests = ref([])
const clients = ref([])
const agents = ref([])
const operations = ref([])
const properties = ref([])

const showForm = ref(false)
const formError = ref('')
const scope = ref('all')  // all | unassigned | mine (только для сотрудника)

const form = reactive(defaultForm())

function defaultForm () {
  return {
    client: null, agent: null, operation_type: null,
    property: null, property_type: '', rooms_count: null,
    min_price: null, max_price: null, description: '',
  }
}

const staffTabs = computed(() => [
  { value: 'all', label: 'Все', count: requests.value.length },
  { value: 'unassigned', label: 'Неразобранное',
    count: requests.value.filter(r => !r.agent).length },
  { value: 'mine', label: 'Мои',
    count: requests.value.filter(r => r.agent === auth.user?.id).length },
])

const visibleRequests = computed(() => {
  if (!auth.isStaff) return requests.value
  if (scope.value === 'unassigned') return requests.value.filter(r => !r.agent)
  if (scope.value === 'mine') return requests.value.filter(r => r.agent === auth.user?.id)
  return requests.value
})

const emptyLabel = computed(() => {
  if (!auth.isStaff) return 'Вы пока не подавали заявок.'
  if (scope.value === 'unassigned') return 'Нет нераспределённых заявок.'
  if (scope.value === 'mine') return 'У вас нет активных заявок.'
  return 'Заявок ещё не создано.'
})

function statusClass (r) {
  const code = r.status_code
  if (code === 'closed') return 'tag--panel'
  if (code === 'cancelled') return ''
  if (code === 'processing') return 'tag--accent'
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
  const requests_req = api.get('/requests/')
  const operations_req = api.get('/operation-types/')
  const properties_req = api.get('/properties/')
  // Список пользователей доступен только сотрудникам.
  const clients_req = auth.isStaff
    ? api.get('/users/', { params: { user_type: 'client' } })
    : Promise.resolve({ data: [] })
  const agents_req = auth.isStaff
    ? api.get('/users/', { params: { user_type: 'employee' } })
    : Promise.resolve({ data: [] })

  const [r, c, a, o, p] = await Promise.all([
    requests_req, clients_req, agents_req, operations_req, properties_req,
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
    // Клиент не отправляет client/agent — сервер подставит сам.
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
  } catch (err) {
    formError.value = err.response?.data
      ? Object.values(err.response.data).flat().join(' ')
      : 'Не удалось создать заявку.'
  }
}

async function takeRequest (r) {
  await api.post(`/requests/${r.id}/take/`)
  await load()
}

async function closeRequest (r) {
  if (!confirm('Закрыть заявку?')) return
  await api.post(`/requests/${r.id}/close/`)
  await load()
}

function formatMoney (v) {
  return v ? new Intl.NumberFormat('ru-RU').format(v) : '—'
}

onMounted(load)
</script>

<style scoped>
.link { color: var(--c-accent); font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
