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
          <label>Тип задачи</label>
          <select class="select" v-model="form.kind">
            <option v-for="k in taskKinds" :key="k.value" :value="k.value">
              {{ k.label }}
            </option>
          </select>
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
          <label>Авто-закрытие</label>
          <select class="select" v-model="form.auto_close_rule">
            <option :value="null">— не закрывается автоматически —</option>
            <option v-for="r in autoCloseRules" :key="r.value" :value="r.value">
              {{ r.label }}
            </option>
          </select>
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
        <button class="btn btn--accent" type="submit" :disabled="creating">
          {{ creating ? 'Создаём…' : 'Создать задачу' }}
        </button>
      </div>
    </form>

    <!-- Фильтры: по статусам + по типу -->
    <div class="panel panel--light stack" style="gap: 10px">
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
      <div class="row" style="gap: 8px; flex-wrap: wrap; align-items: center">
        <span class="muted" style="font-size: 12px; text-transform: uppercase; letter-spacing: .05em">Тип:</span>
        <button class="btn btn--sm"
                :class="{ 'btn--primary': kindFilter === '' }"
                @click="kindFilter = ''">
          Любой
        </button>
        <button v-for="k in taskKinds" :key="k.value"
                class="btn btn--sm"
                :class="{ 'btn--primary': kindFilter === k.value }"
                @click="kindFilter = k.value">
          {{ k.label }}
        </button>
      </div>
    </div>

    <!-- Таблица задач -->
    <div class="panel panel--light">
      <table class="table">
        <thead>
          <tr>
            <th>Заголовок</th>
            <th>Тип</th>
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
            <td>
              <span class="tag tag--panel" :title="t.auto_close_rule_display || ''">
                {{ t.kind_display || '—' }}
              </span>
              <div v-if="t.auto_close_rule" class="muted"
                   style="font-size: 11px; margin-top: 2px"
                   :title="t.auto_close_rule_display">
                авто-закрытие
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
              <div v-if="t.is_auto_closed" class="muted"
                   style="font-size: 11px; margin-top: 2px">
                закрыто автоматически
              </div>
            </td>
            <td class="task-actions">
              <button v-if="canStart(t)"
                      class="btn btn--sm btn--accent"
                      :disabled="!canStartBtn(t) || busyId === t.id"
                      :title="!canStartBtn(t) ? 'У сотрудника уже есть задача в работе' : 'Взять в работу'"
                      @click="onStart(t)">
                Старт
              </button>
              <button v-if="canPause(t)"
                      class="btn btn--sm"
                      :disabled="busyId === t.id"
                      @click="onPause(t)">
                Пауза
              </button>
              <button v-if="canComplete(t)"
                      class="btn btn--sm btn--ghost"
                      :disabled="busyId === t.id"
                      @click="openCompleteModal(t)">
                Завершить
              </button>
              <select class="select select--sm"
                      :value="t.status"
                      @change="onChangeStatus(t, $event.target.value)">
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

    <!-- Модалка завершения задачи: агент фиксирует, что именно сделано.
         Запись попадает в Task.result и в отчёты. -->
    <div v-if="completing.task" class="modal-backdrop" @click.self="closeCompleteModal">
      <div class="modal">
        <h3 style="margin: 0 0 12px">Завершить задачу</h3>
        <p class="muted" style="margin: 0 0 16px; font-size: 13px">
          Опишите, что сделано: это попадёт в историю задачи и статистику.
        </p>
        <div class="field">
          <label>Что сделано</label>
          <textarea class="textarea" rows="3"
                    v-model="completing.comment"
                    placeholder="Например: провёл показ, клиент заинтересовался"></textarea>
        </div>
        <div class="field">
          <label>Итог</label>
          <select class="select" v-model="completing.outcome">
            <option value="done">Выполнено</option>
            <option value="partial">Частично</option>
            <option value="not_reached">Клиент недоступен</option>
            <option value="other">Другое</option>
          </select>
        </div>
        <div class="row" style="gap: 8px; justify-content: flex-end">
          <button class="btn" @click="closeCompleteModal"
                  :disabled="completing.busy">Отмена</button>
          <button class="btn btn--accent"
                  :disabled="completing.busy"
                  @click="confirmComplete">
            {{ completing.busy ? 'Завершаем…' : 'Завершить' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import {
  startTask as apiStartTask,
  pauseTask as apiPauseTask,
  completeTask as apiCompleteTask,
  changeTaskStatus as apiChangeTaskStatus,
  createTask as apiCreateTask,
} from '../api/tasks'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { useToasts } from '../store/toasts'

const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToasts()

const tasks = ref([])
const statuses = ref([])
const employees = ref([])
const clients = ref([])
const requests = ref([])
const properties = ref([])

const statusFilter = ref('')
const kindFilter = ref('')
const showForm = ref(false)
const busyId = ref(null)
const creating = ref(false)

// Справочники типов задач и правил авто-закрытия — дублируют choices
// на бэкенде (Task.KIND_CHOICES / AUTO_CLOSE_CHOICES). Это нормально
// для MVP; при желании их можно будет получить с сервера через
// отдельный endpoint и закэшировать.
const taskKinds = [
  { value: 'call',            label: 'Звонок клиенту' },
  { value: 'client_search',   label: 'Поиск клиентов для объекта' },
  { value: 'property_search', label: 'Подбор объектов для клиента' },
  { value: 'viewing',         label: 'Показ объекта' },
  { value: 'documents',       label: 'Подготовка документов' },
  { value: 'follow_up',       label: 'Повторный контакт' },
  { value: 'other',           label: 'Прочее' },
]
const autoCloseRules = [
  { value: 'on_client_matched',   label: 'Когда подобран клиент для объекта' },
  { value: 'on_property_matched', label: 'Когда подобран объект для клиента' },
  { value: 'on_viewing_done',     label: 'Когда показ проведён' },
  { value: 'on_deal_created',     label: 'Когда создана сделка' },
  { value: 'on_request_closed',   label: 'Когда заявка закрыта' },
]

const form = reactive(defaultForm())

// Состояние модалки «Завершить задачу».
const completing = reactive({
  task: null,
  comment: '',
  outcome: 'done',
  busy: false,
})

function defaultForm () {
  return {
    title: '', description: '',
    kind: 'other', auto_close_rule: null,
    assignee: null, priority: 'normal',
    due_date: '', request: null, client: null, property: null,
  }
}

const filtered = computed(() => {
  return tasks.value.filter((t) => {
    if (statusFilter.value && t.status !== statusFilter.value) return false
    if (kindFilter.value && t.kind !== kindFilter.value) return false
    return true
  })
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
  if (!payload.auto_close_rule) delete payload.auto_close_rule

  creating.value = true
  const res = await apiCreateTask(payload)
  creating.value = false
  if (!res.ok) {
    toasts.error(res.error || 'Не удалось создать задачу')
    return
  }
  toasts.success('Задача создана')
  showForm.value = false
  Object.assign(form, defaultForm())
  await load()
}

async function onChangeStatus (task, statusId) {
  if (!statusId) return
  busyId.value = task.id
  const res = await apiChangeTaskStatus(task.id, statusId)
  busyId.value = null
  if (!res.ok) {
    toasts.error(res.error || 'Не удалось изменить статус.')
    return
  }
  toasts.success('Статус обновлён')
  await load()
}

// --- права на быстрые действия --------------------------------------------
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
function canStartBtn (task) {
  if (auth.isManager) return true
  if (task.assignee !== auth.user?.id) return false
  return workload.workload.in_progress_tasks
      < workload.workload.max_in_progress_tasks
}

async function onStart (task) {
  busyId.value = task.id
  const res = await apiStartTask(task.id)
  busyId.value = null
  if (!res.ok) {
    toasts.error(res.error || 'Нельзя стартовать задачу: превышен лимит.')
    return
  }
  toasts.success('Задача взята в работу')
  await load()
}

async function onPause (task) {
  busyId.value = task.id
  const res = await apiPauseTask(task.id)
  busyId.value = null
  if (!res.ok) {
    toasts.error(res.error || 'Не удалось приостановить задачу.')
    return
  }
  toasts.info('Задача приостановлена')
  await load()
}

function openCompleteModal (task) {
  completing.task = task
  completing.comment = ''
  completing.outcome = 'done'
  completing.busy = false
}
function closeCompleteModal () {
  if (completing.busy) return
  completing.task = null
}
async function confirmComplete () {
  const task = completing.task
  if (!task) return
  completing.busy = true
  const res = await apiCompleteTask(task.id, {
    comment: completing.comment,
    outcome: completing.outcome,
    source: 'tasks_view',
  })
  completing.busy = false
  if (!res.ok) {
    toasts.error(res.error || 'Не удалось завершить задачу.')
    return
  }
  toasts.success('Задача завершена, результат зафиксирован')
  completing.task = null
  await load()
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

/* --- Модалка «Завершить задачу» --- */
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, .5);
  display: flex; align-items: center; justify-content: center;
  padding: 16px; z-index: 120;
}
.modal {
  background: #fff;
  border-radius: 14px;
  padding: 20px;
  width: min(480px, 100%);
  box-shadow: 0 24px 48px rgba(15, 23, 42, .25);
}
</style>
