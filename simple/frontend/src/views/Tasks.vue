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
          <!-- Индикатор личной нагрузки сотрудника — сразу под заголовком. -->
          <div v-if="!auth.isManager"
               class="workload-banner"
               :class="{ 'is-limit': workload.isOverloaded }">
            <span>Моя загрузка:</span>
            <b>{{ workload.activeTasksLabel }}</b> задач ·
            <b>{{ workload.activeRequestsLabel }}</b> заявок ·
            <b>{{ workload.workload.in_progress_tasks }}/{{ workload.workload.max_in_progress_tasks }}</b>
            в работе
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--accent" @click="toggleForm">
            {{ showForm ? 'Скрыть форму' : '+ Новая задача' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Форма создания -->
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

    <!-- Фильтр по статусам -->
    <div class="panel panel--light">
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

    <!-- Таблица задач -->
    <div class="panel panel--light">
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
              <div v-if="t.assignee === auth.user?.id && t.status_code === 'in_progress'"
                   class="muted" style="font-size: 11px; margin-top: 2px">
                вы сейчас выполняете
              </div>
            </td>
            <td class="task-actions">
              <!-- Быстрые переходы по статусам. «Старт» блокируется,
                   если у сотрудника уже есть задача в работе — лимит 1. -->
              <button v-if="canStart(t)"
                      class="btn btn--sm btn--accent"
                      :disabled="!canStartBtn(t) || busyId === t.id"
                      :title="!canStartBtn(t) ? 'У сотрудника уже есть задача в работе' : 'Взять в работу'"
                      @click="startTask(t)">
                Старт
              </button>
              <button v-if="canPause(t)"
                      class="btn btn--sm"
                      :disabled="busyId === t.id"
                      @click="pauseTask(t)">
                Пауза
              </button>
              <button v-if="canComplete(t)"
                      class="btn btn--sm btn--ghost"
                      :disabled="busyId === t.id"
                      @click="completeTask(t)">
                Завершить
              </button>
              <select class="select select--sm"
                      :value="t.status"
                      @change="changeStatus(t, $event.target.value)">
                <option disabled value="">Статус…</option>
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'

const auth = useAuthStore()
const workload = useWorkloadStore()

const tasks = ref([])
const statuses = ref([])
const employees = ref([])
const clients = ref([])
const requests = ref([])
const properties = ref([])

const statusFilter = ref('')
const showForm = ref(false)
const busyId = ref(null)

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
  try {
    await api.post(`/tasks/${task.id}/change_status/`,
                   { status_id: Number(statusId) })
  } catch (err) {
    alert(err.response?.data?.detail || 'Не удалось изменить статус.')
  }
  await refreshAll()
}

// --- права на быстрые действия --------------------------------------------
// Сотрудник может стартовать/паузить/завершать только свои задачи.
// Менеджер и админ — любые (для ручного вмешательства).
function isOwnOrManaged (task) {
  return auth.isManager || task.assignee === auth.user?.id
}
function canStart (task) {
  return isOwnOrManaged(task)
    && ['new', 'waiting'].includes(task.status_code)
}
function canPause (task) {
  return isOwnOrManaged(task) && task.status_code === 'in_progress'
}
function canComplete (task) {
  return isOwnOrManaged(task)
    && ['new', 'in_progress', 'waiting'].includes(task.status_code)
}
// Кнопка «Старт» становится активной только если не превышен лимит
// параллельных in_progress-задач у конкретного сотрудника.
function canStartBtn (task) {
  if (auth.isManager) return true
  // Если задача уже у меня и в работе — старт не нужен.
  if (task.assignee !== auth.user?.id) return false
  return workload.workload.in_progress_tasks
      < workload.workload.max_in_progress_tasks
}

async function startTask (task) {
  busyId.value = task.id
  try {
    await api.post(`/tasks/${task.id}/start/`)
    await refreshAll()
  } catch (err) {
    alert(err.response?.data?.detail
      || 'Нельзя стартовать задачу: превышен лимит.')
  } finally { busyId.value = null }
}
async function pauseTask (task) {
  busyId.value = task.id
  try {
    await api.post(`/tasks/${task.id}/pause/`)
    await refreshAll()
  } catch (err) {
    alert(err.response?.data?.detail || 'Не удалось приостановить задачу.')
  } finally { busyId.value = null }
}
async function completeTask (task) {
  busyId.value = task.id
  try {
    await api.post(`/tasks/${task.id}/complete/`)
    await refreshAll()
  } catch (err) {
    alert(err.response?.data?.detail || 'Не удалось завершить задачу.')
  } finally { busyId.value = null }
}

async function refreshAll () {
  await Promise.all([load(), workload.refresh()])
}

onMounted(async () => {
  await load()
  if (auth.isStaff) workload.refresh()
})
</script>

<style scoped>
.link { color: var(--c-accent); font-weight: 500; }
.link:hover { text-decoration: underline; }
.overdue { background: #fee; color: #c2554a; margin-left: 6px; }
.select--sm { padding: 6px 10px; font-size: 13px; }

.task-actions {
  display: flex; gap: 6px; flex-wrap: wrap;
  align-items: center;
}

.workload-banner {
  margin-top: 10px;
  background: rgba(255,255,255,.12);
  color: #fff; font-size: 13px;
  padding: 6px 12px; border-radius: 999px;
  display: inline-flex; gap: 6px; align-items: center;
}
.workload-banner.is-limit {
  background: rgba(194, 85, 74, .9);
}
</style>
