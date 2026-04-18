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
        <button class="btn btn--accent" @click="showForm = !showForm">
          {{ showForm ? 'Скрыть форму' : '+ Новая задача' }}
        </button>
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
        <button class="btn btn--accent" type="submit">Создать</button>
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

    <!-- Список -->
    <div class="panel panel--light">
      <table class="table">
        <thead>
          <tr>
            <th>Заголовок</th>
            <th>Исполнитель</th>
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
              <span class="tag" :class="priorityClass(t.priority)">
                {{ priorityLabel(t.priority) }}
              </span>
            </td>
            <td class="muted">
              {{ t.due_date ? new Date(t.due_date).toLocaleString('ru-RU') : '—' }}
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

const tasks = ref([])
const statuses = ref([])
const employees = ref([])
const requests = ref([])
const properties = ref([])
const statusFilter = ref('')
const showForm = ref(false)

const form = reactive({
  title: '', description: '',
  assignee: null, priority: 'normal',
  due_date: '', request: null, property: null,
})

const filtered = computed(() => {
  if (!statusFilter.value) return tasks.value
  return tasks.value.filter((t) => t.status === statusFilter.value)
})

function countBy(id) {
  return tasks.value.filter((t) => t.status === id).length
}

function priorityLabel(p) {
  return ({ low: 'Низкий', normal: 'Обычный', high: 'Высокий' })[p] || p
}
function priorityClass(p) {
  if (p === 'high') return 'tag--accent'
  if (p === 'low') return 'tag--panel'
  return ''
}

async function load() {
  const [t, s, e, r, p] = await Promise.all([
    api.get('/tasks/'),
    api.get('/task-statuses/'),
    api.get('/users/', { params: { user_type: 'employee' } }),
    api.get('/requests/'),
    api.get('/properties/'),
  ])
  tasks.value = t.data.results || t.data
  statuses.value = s.data.results || s.data
  employees.value = e.data.results || e.data
  requests.value = r.data.results || r.data
  properties.value = p.data.results || p.data
}

async function create() {
  const payload = { ...form }
  if (!payload.due_date) delete payload.due_date
  await api.post('/tasks/', payload)
  showForm.value = false
  Object.assign(form, {
    title: '', description: '',
    assignee: null, priority: 'normal',
    due_date: '', request: null, property: null,
  })
  await load()
}

async function changeStatus(task, statusId) {
  if (!statusId) return
  await api.post(`/tasks/${task.id}/change_status/`, { status_id: Number(statusId) })
  await load()
}

onMounted(load)
</script>
