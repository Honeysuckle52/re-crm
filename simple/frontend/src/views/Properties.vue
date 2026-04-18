<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ОБЪЕКТЫ</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            Каталог недвижимости
          </h1>
        </div>
        <router-link to="/properties/new" class="btn btn--accent">
          + Добавить объект
        </router-link>
      </div>
    </div>

    <!-- Фильтры -->
    <div class="panel panel--light">
      <div class="grid grid--3">
        <div class="field">
          <label>Тип операции</label>
          <select class="select" v-model="filters.operation_type">
            <option value="">Все</option>
            <option v-for="o in dict.operations" :key="o.id" :value="o.id">
              {{ o.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Статус</label>
          <select class="select" v-model="filters.status">
            <option value="">Все</option>
            <option v-for="s in dict.statuses" :key="s.id" :value="s.id">
              {{ s.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Комнат</label>
          <select class="select" v-model="filters.rooms">
            <option value="">Любое</option>
            <option v-for="n in [1,2,3,4,5]" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="field">
          <label>Цена от</label>
          <input class="input" type="number" v-model.number="filters.min_price" />
        </div>
        <div class="field">
          <label>Цена до</label>
          <input class="input" type="number" v-model.number="filters.max_price" />
        </div>
        <div class="field">
          <label>Поиск</label>
          <input class="input" v-model="filters.search" placeholder="Название или описание" />
        </div>
      </div>
      <div class="row" style="justify-content: flex-end; margin-top: 14px">
        <button class="btn btn--sm" @click="reset">Сбросить</button>
        <button class="btn btn--primary btn--sm" @click="load">Применить</button>
      </div>
    </div>

    <!-- Список -->
    <div v-if="loading" class="empty">Загрузка…</div>
    <div v-else-if="items.length" class="grid grid--3">
      <PropertyCard v-for="p in items" :key="p.id" :property="p" />
    </div>
    <div v-else class="empty">Ничего не найдено по выбранным фильтрам.</div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import PropertyCard from '../components/PropertyCard.vue'

const filters = reactive({
  operation_type: '', status: '', rooms: '',
  min_price: null, max_price: null, search: '',
})
const dict = reactive({ operations: [], statuses: [] })
const items = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const params = {}
    for (const [k, v] of Object.entries(filters))
      if (v !== '' && v !== null) params[k] = v
    const { data } = await api.get('/properties/', { params })
    items.value = data.results || data
  } finally {
    loading.value = false
  }
}

function reset() {
  Object.assign(filters, {
    operation_type: '', status: '', rooms: '',
    min_price: null, max_price: null, search: '',
  })
  load()
}

onMounted(async () => {
  const [o, s] = await Promise.all([
    api.get('/operation-types/'),
    api.get('/property-statuses/'),
  ])
  dict.operations = o.data.results || o.data
  dict.statuses = s.data.results || s.data
  await load()
})
</script>
