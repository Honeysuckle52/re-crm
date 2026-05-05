<template>
  <section class="stack properties-page">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Объекты</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            Каталог недвижимости
          </h1>
        </div>
        <router-link
          v-if="auth.user?.user_type === 'employee'"
          to="/properties/new"
          class="btn btn--accent">
          + Добавить объект
        </router-link>
      </div>
    </div>

    <div class="properties-shell">
      <aside class="panel panel--light properties-filter">
        <div class="properties-filter__head">
          <h2 class="h3">Фильтр объектов</h2>
          <div class="muted">
            Фильтр закреплён, а справа прокручивается только список объектов.
          </div>
        </div>

        <div class="grid properties-filter__grid">
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
              <option v-for="n in [1, 2, 3, 4, 5]" :key="n" :value="n">
                {{ n }}
              </option>
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
            <input
              class="input"
              v-model="filters.search"
              placeholder="Название или описание" />
          </div>
        </div>

        <div class="row properties-filter__actions">
          <button class="btn btn--sm" @click="reset">Сбросить</button>
          <button class="btn btn--primary btn--sm" @click="load">Применить</button>
        </div>
      </aside>

      <section class="properties-main">
        <div class="panel panel--light properties-main__head">
          <div class="properties-main__meta">
            <div class="hero__eyebrow properties-main__eyebrow">Каталог</div>
            <h2 class="h2">Найдено {{ items.length }} объектов</h2>
          </div>
          <div class="muted properties-main__caption">
            Просторная сетка, фильтр всегда под рукой и без лишнего сжатия по центру.
          </div>
        </div>

        <div class="panel panel--light properties-results">
          <div class="properties-results__body">
            <div v-if="loading" class="empty properties-empty">Загрузка…</div>
            <div v-else-if="items.length" class="properties-grid">
              <PropertyCard v-for="p in items" :key="p.id" :property="p" />
            </div>
            <div v-else class="empty properties-empty">
              Ничего не найдено по выбранным фильтрам.
            </div>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import PropertyCard from '../components/PropertyCard.vue'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()

const filters = reactive({
  operation_type: '',
  status: '',
  rooms: '',
  min_price: null,
  max_price: null,
  search: '',
})

const dict = reactive({ operations: [], statuses: [] })
const items = ref([])
const loading = ref(false)

async function load () {
  loading.value = true
  try {
    const params = {}
    for (const [k, v] of Object.entries(filters)) {
      if (v !== '' && v !== null) params[k] = v
    }
    const { data } = await api.get('/properties/', { params })
    items.value = data.results || data
  } finally {
    loading.value = false
  }
}

function reset () {
  Object.assign(filters, {
    operation_type: '',
    status: '',
    rooms: '',
    min_price: null,
    max_price: null,
    search: '',
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

<style scoped>
.properties-page {
  min-height: 0;
}

.properties-shell {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
  min-height: 0;
}

.properties-filter {
  position: sticky;
  top: 84px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.properties-filter__head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.properties-filter__grid {
  grid-template-columns: 1fr;
  gap: 14px;
}

.properties-filter__actions {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 2px;
}

.properties-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.properties-main__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.properties-main__meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.properties-main__eyebrow {
  align-self: flex-start;
  min-height: 28px;
  padding: 0 12px;
  font-size: 10px;
  letter-spacing: 0.08em;
}

.properties-main__caption {
  max-width: 420px;
  text-align: right;
}

.properties-results {
  min-height: calc(100vh - 232px);
  padding: 12px;
}

.properties-results__body {
  max-height: calc(100vh - 256px);
  overflow-y: auto;
  padding-right: 6px;
}

.properties-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
  align-content: start;
}

.properties-empty {
  min-height: 280px;
}

@media (max-width: 1080px) {
  .properties-shell {
    grid-template-columns: 320px minmax(0, 1fr);
  }
}

@media (max-width: 960px) {
  .properties-shell {
    grid-template-columns: 1fr;
  }

  .properties-filter {
    position: static;
    top: auto;
  }

  .properties-main__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .properties-main__caption {
    max-width: none;
    text-align: left;
  }

  .properties-results {
    min-height: auto;
  }

  .properties-results__body {
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .properties-filter__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .properties-filter__grid,
  .properties-grid {
    grid-template-columns: 1fr;
  }
}
</style>
