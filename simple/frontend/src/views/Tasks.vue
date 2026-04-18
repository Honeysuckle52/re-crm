<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ЗАДАЧИ</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">Рабочие задачи</h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Поручения сотрудникам: звонки, показы, документы
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <div class="row" style="gap: 0; background: rgba(255,255,255,.1); border-radius: var(--r-pill); padding: 4px">
            <button class="btn btn--sm"
                    :class="viewMode === 'table' ? 'btn--accent' : 'btn--ghost'"
                    @click="viewMode = 'table'">Таблица</button>
            <button class="btn btn--sm"
                    :class="viewMode === 'kanban' ? 'btn--accent' : 'btn--ghost'"
                    @click="viewMode = 'kanban'">Канбан</button>
          </div>
          <button class="btn btn--accent" @click="toggleForm">
            {{ showForm ? 'Скрыть форму' : '+ Новая задача' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Форма -->
    <form v-if="showForm" class="panel panel--light stack" @submit.prevent="create">
      <div class="grid grid--3">
        <div class="field">
          <label>Заголовок</label>
          <input class="input" v-model="form.title" required />
        </div>
        <div class="field">
          <label>Исполнитель</label>
          <select class="select" v-model.number="form.assignee" required>
            <option :value="null" disabled>— выберите —</option>
            <option v-for="a in employees" :key="a.id" :value="a.id">
              {{ a.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Приоритет</label>
          <select class="select" v-model="form.priority">
            <option value="low">Низкий</option>
            <option value="normal">Обычный</option>
            <option value="high">Высокий</option>
          </select>
        </div>
        <div class="field">
          <label>Срок</label>
          <input class="input" type="datetime-local" v-model="form.due_date" />
        </div>
        <div class="field">
          <label>Связанная заявка</label>
          <select class="select" v-model.number="form.request">
            <option :value="null">— не выбрана —</option>
            <option v-for="r in requests" :key="r.id" :value="r.id">
              №{{ r.id }} — {{ r.client_username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Клиент</label>
          <select class="select" v-model.number="form.client">
            <option :value="null">— не выбран —</option>
            <option v-for="c in clients" :key="c.id" :value="c.id">
              {{ c.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Связанный объект</label>
          <select class="select" v-model.number="form.property">
            <option :value="null">— не выбран —</option>
            <option v-for="p in properties" :key="p.id" :value="p.id">
              {{ p.title || 'Объект №' + p.id }}
            </option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>Описание</label>
        <textarea class="textarea" v-model="form.description" rows="3"></textarea>
      </div>
      <div class="row" style="justify-content: flex-end">
        <button class="btn btn--accent" type="submit">Создать задачу</button>
      </div>
    </form>

    <!-- Фильтр по статусам (только для табличного вида) -->
    <div v-if="viewMode === 'table'" class="panel panel--light">
      <div class="row" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn--sm"
                :class="{ 'btn--primary': statusFilter === '' }"
                @click="statusFilter = ''">
          Все ({{ tasks.length }})
        </button>
        <button v-for="s in statuses" :key="s.id"
                class="btn btn--sm"
                :class="{ 'btn--primary': statusFilter === s.id }"
                @click="statusFilter = s.id">
          {{ s.name }} ({{ countBy(s.id) }})
        </button>
      </div>
    </div>

    <!-- Таблица -->
    <div v-if="viewMode === 'table'" class="panel panel--light">
      <table class="table">
        <thead>
          <tr>
            <th>Заголовок</th>
            <th>Исполнитель</th>
            <th>Заявка</th>
            <th>Приоритет</th>
            <th>Срок</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in filtered" :key="t.id">
            <td>
              <b>{{ t.title }}</b>
              <div class="muted" style="font-size: 12px" v-if="t.property_title">
                Объект: {{ t.property_title }}
              </div>
            </td>
            <td>{{ t.assignee_username }}</td>
            <td>
              <router-link v-if="t.request" :to="`/requests/${t.request}`"
                           class="link">
                №{{ t.request }}
              </router-link>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span class="tag" :class="priorityClass(t.priority)">
                {{ priorityLabel(t.priority) }}
              </span>
            </td>
            <td class="muted" style="white-space: nowrap">
              {{ t.due_date ? formatDate(t.due_date) : '—' }}
              <span v-if="t.is_overdue" class="tag overdue">просрочено</span>
            </td>
            <td>
              <span class="tag tag--accent">{{ t.status_name }}</span>
            </td>
            <td>
              <select class="select select--sm" :value="t.status"
                      @change="changeStatus(t, $event.target.value)">
                <option disabled value="">Изменить статус</option>
                <option v-for="s in statuses" :key="s.id" :value="s.id">
                  {{ s.name }}
                </option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!filtered.length" class="empty">Задач нет.</div>
    </div>

    <!-- Канбан -->
    <div v-else class="kanban">
      <div v-for="s in kanbanColumns" :key="s.id" class="kanban__col">
        <div class="kanban__head">
          <h3 class="h3">{{ s.name }}</h3>
          <span class="tag">{{ groupedTasks[s.id]?.length || 0 }}</span>
        </div>
        <div class="kanban__list">
          <article v-for="t in groupedTasks[s.id] || []" :key="t.id"
                   class="kanban__card"
                   :class="{ 'kanban__card--overdue': t.is_overdue }">
            <div class="row row--between" style="gap: 8px">
              <b>{{ t.title }}</b>
              <span class="tag" :class="priorityClass(t.priority)">
                {{ priorityLabel(t.priority) }}
              </span>
            </div>
            <div v-if="t.description" class="muted" style="font-size: 13px">
              {{ truncate(t.description, 120) }}
            </div>
            <div class="kanban__meta">
              <span>{{ t.assignee_username }}</span>
              <span v-if="t.due_date">· до {{ formatDate(t.due_date) }}</span>
            </div>
            <router-link v-if="t.request" :to="`/requests/${t.request}`"
                         class="link" style="font-size: 13px">
              → Заявка №{{ t.request }}
            </router-link>
            <select class="select select--sm"
                    :value="t.status"
                    @change="changeStatus(t, $event.target.value)">
              <option v-for="st in statuses" :key="st.id" :value="st.id">
                {{ st.name }}
              </option>
            </select>
          </article>
          <div v-if="!(groupedTasks[s.id] || []).length" class="kanban__empty">
            Нет задач
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const tasks = ref([])
const statuses = ref([])
const employees = ref([])
const clients = ref([])
const requests = ref([])
const properties = ref([])

const statusFilter = ref('')
const showForm = ref(false)
const viewMode = ref('table')  // 'table' | 'kanban'

const form = reactive(defaultForm())

function defaultForm () {
  return {
    title: '', description: '',
    assignee: null, priority: 'normal',
    due_date: '', request: null, client: null, property: null,
  }
}

const filtered = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter((t) => t.status === statusFilter.value)
})

// В канбане скрываем «Отменена», если нет задач — слишком много колонок.
const kanbanColumns = computed(() => {
  return statuses.value.filter(s => {
    if (s.code === 'cancelled') {
      return tasks.value.some(t => t.status === s.id)
    }
    return true
  })
})

const groupedTasks = computed(() => {
  const groups = {}
  for (const s of statuses.value) groups[s.id] = []
  for (const t of tasks.value) {
    if (groups[t.status]) groups[t.status].push(t)
  }
  return groups
})

function countBy (id) {
  return tasks.value.filter((t) => t.status === id).length
}

function priorityLabel (p) {
  return ({ low: 'Низкий', normal: 'Обычный', high: 'Высокий' })[p] || p
}
function priorityClass (p) {
  if (p === 'high') return 'tag--accent'
  if (p === 'low') return 'tag--panel'
  return ''
}

function formatDate (s) {
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function truncate (s, n) {
  return s && s.length > n ? s.slice(0, n - 1) + '…' : s
}

function toggleForm () {
  showForm.value = !showForm.value
  if (showForm.value) Object.assign(form, defaultForm())
}

async function load () {
  const [t, s, e, c, r, p] = await Promise.all([
    api.get('/tasks/'),
    api.get('/task-statuses/'),
    api.get('/users/', { params: { user_type: 'employee' } }),
    api.get('/users/', { params: { user_type: 'client' } }),
    api.get('/requests/'),
    api.get('/properties/'),
  ])
  tasks.value = t.data.results || t.data
  statuses.value = s.data.results || s.data
  employees.value = e.data.results || e.data
  clients.value = c.data.results || c.data
  requests.value = r.data.results || r.data
  properties.value = p.data.results || p.data
}

async function create () {
  const payload = { ...form }
  if (!payload.due_date) delete payload.due_date
  if (!payload.request) delete payload.request
  if (!payload.client) delete payload.client
  if (!payload.property) delete payload.property
  await api.post('/tasks/', payload)
  showForm.value = false
  Object.assign(form, defaultForm())
  await load()
}

async function changeStatus (task, statusId) {
  if (!statusId) return
  await api.post(`/tasks/${task.id}/change_status/`,
                 { status_id: Number(statusId) })
  await load()
}

onMounted(load)
</script>

<style scoped>
.link { color: var(--c-accent); font-weight: 500; }
.link:hover { text-decoration: underline; }
.overdue { background: #fee; color: #c2554a; margin-left: 6px; }
.select--sm { padding: 6px 10px; font-size: 13px; }

/* Канбан */
.kanban {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}
.kanban__col {
  background: var(--c-paper); border-radius: var(--r-md);
  padding: 14px; display: flex; flex-direction: column; gap: 10px;
  min-height: 120px; box-shadow: var(--shadow-1);
}
.kanban__head {
  display: flex; justify-content: space-between; align-items: center;
}
.kanban__list {
  display: flex; flex-direction: column; gap: 8px;
}
.kanban__card {
  background: var(--c-paper-2); border-radius: var(--r-sm);
  padding: 12px; display: flex; flex-direction: column; gap: 6px;
  border-left: 3px solid transparent;
}
.kanban__card--overdue {
  border-left-color: var(--c-danger);
  background: #fdf1ef;
}
.kanban__meta {
  font-size: 12px; color: var(--c-ink-soft);
}
.kanban__empty {
  color: var(--c-muted); font-size: 13px; text-align: center; padding: 10px;
}
</style>
