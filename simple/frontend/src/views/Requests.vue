<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ЗАЯВКИ</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            Запросы клиентов
          </h1>
        </div>
        <button class="btn btn--accent" @click="showForm = !showForm">
          {{ showForm ? 'Скрыть форму' : '+ Новая заявка' }}
        </button>
      </div>
    </div>

    <!-- Форма создания -->
    <form v-if="showForm" class="panel panel--light stack"
          @submit.prevent="createRequest">
      <div class="grid grid--3">
        <div class="field">
          <label>Клиент</label>
          <select class="select" v-model.number="form.client" required>
            <option v-for="c in clients" :key="c.id" :value="c.id">
              {{ c.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Агент</label>
          <select class="select" v-model.number="form.agent" required>
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
      <div class="row" style="justify-content: flex-end">
        <button class="btn btn--accent" type="submit">Создать</button>
      </div>
    </form>

    <!-- Список -->
    <div class="panel panel--light">
      <table class="table">
        <thead>
          <tr>
            <th>#</th><th>Клиент</th><th>Агент</th>
            <th>Операция</th><th>Цена</th><th>Статус</th>
            <th>Создана</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in requests" :key="r.id">
            <td>#{{ r.id }}</td>
            <td>{{ r.client_username }}</td>
            <td>{{ r.agent_username }}</td>
            <td>{{ r.operation_type_name }}</td>
            <td>
              {{ formatMoney(r.min_price) }}–{{ formatMoney(r.max_price) }} ₽
            </td>
            <td><span class="tag tag--accent">{{ r.status_name }}</span></td>
            <td class="muted">
              {{ new Date(r.created_at).toLocaleDateString('ru-RU') }}
            </td>
            <td>
              <button class="btn btn--sm" @click="closeRequest(r)">Закрыть</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!requests.length" class="empty">Заявок пока нет.</div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'

const requests = ref([])
const clients = ref([]); const agents = ref([]); const operations = ref([])
const showForm = ref(false)
const form = reactive({
  client: null, agent: null, operation_type: 1,
  property_type: '', rooms_count: null,
  min_price: null, max_price: null, description: '',
})

async function load() {
  const [r, c, a, o] = await Promise.all([
    api.get('/requests/'),
    api.get('/users/', { params: { user_type: 'client' } }),
    api.get('/users/', { params: { user_type: 'employee' } }),
    api.get('/operation-types/'),
  ])
  requests.value = r.data.results || r.data
  clients.value = c.data.results || c.data
  agents.value = a.data.results || a.data
  operations.value = o.data.results || o.data
}

async function createRequest() {
  await api.post('/requests/', form)
  showForm.value = false
  await load()
}

async function closeRequest(r) {
  await api.post(`/requests/${r.id}/close/`)
  await load()
}

function formatMoney(v) { return v ? new Intl.NumberFormat('ru-RU').format(v) : '—' }
onMounted(load)
</script>
