<template>
  <div class="property-picker" role="presentation" @click.self="$emit('close')">
    <div class="panel panel--light property-picker__dialog" role="dialog" aria-modal="true">
      <div class="row row--between property-picker__head">
        <div>
          <h2 class="h3">{{ title }}</h2>
          <div class="muted" style="margin-top: 6px">
            Выберите объект из карточек ниже. Список можно прокручивать и фильтровать по поиску.
          </div>
        </div>
        <button type="button" class="btn btn--sm" @click="$emit('close')">×</button>
      </div>

      <div class="property-picker__toolbar">
        <input
          v-model="search"
          class="input property-picker__search"
          type="search"
          placeholder="Поиск по названию, адресу или ID..."
          @input="onSearch"
        />
        <button type="button" class="btn btn--sm btn--ghost" @click="resetSearch">
          Сбросить
        </button>
      </div>

      <div v-if="loading && !items.length" class="property-picker__state">
        Загрузка объектов…
      </div>
      <div v-else-if="error" class="error">{{ error }}</div>

      <div v-else class="property-picker__list">
        <button
          v-for="property in items"
          :key="property.id"
          type="button"
          class="property-picker__item"
          @click="selectProperty(property)"
        >
          <PropertyCard
            :property="property"
            :interactive="false"
            selectable
            :selected="String(property.id) === String(selectedId)"
            @select="selectProperty"
          />
        </button>
      </div>

      <div class="row property-picker__footer">
        <div class="muted">
          Показано {{ items.length }} из {{ totalCount }}
        </div>
        <button
          v-if="hasMore && !loading"
          type="button"
          class="btn btn--sm btn--accent"
          @click="loadMore"
        >
          Показать еще
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api'
import PropertyCard from './PropertyCard.vue'
import { unpackPaginated } from '@/utils/paginated'

const props = defineProps({
  title: { type: String, default: 'Выбор объекта' },
  selectedId: { type: [Number, String], default: null },
  params: { type: Object, default: () => ({}) },
  pageSize: { type: Number, default: 12 },
})

const emit = defineEmits(['close', 'select'])

const items = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const page = ref(1)
const totalCount = ref(0)

const hasMore = computed(() => items.value.length < totalCount.value)

let requestSeq = 0

function buildParams() {
  return {
    page: page.value,
    page_size: props.pageSize,
    ordering: '-created_at',
    search: search.value.trim(),
    ...props.params,
  }
}

async function load(reset = false) {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  if (reset) {
    items.value = []
    page.value = 1
  }

  try {
    const { data } = await api.get('/properties/', { params: buildParams() })
    if (seq !== requestSeq) return
    const payload = unpackPaginated(data)
    totalCount.value = payload.count
    items.value = reset ? payload.items : [...items.value, ...payload.items]
  } catch (err) {
    if (seq !== requestSeq) return
    error.value = err?.response?.data?.detail || 'Не удалось загрузить объекты.'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function onSearch() {
  load(true)
}

function resetSearch() {
  search.value = ''
  load(true)
}

function loadMore() {
  page.value += 1
  load(false)
}

function selectProperty(property) {
  emit('select', property)
  emit('close')
}

watch(
  () => props.params,
  () => load(true),
  { deep: true },
)

onMounted(() => {
  load(true)
})
</script>

<style scoped>
.property-picker {
  position: fixed;
  inset: 0;
  z-index: 130;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(7, 16, 22, 0.34);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.property-picker__dialog {
  width: min(100%, 1120px);
  max-height: min(82vh, 860px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
  border-radius: 24px;
  box-shadow: var(--shadow-glow);
}

.property-picker__head {
  gap: 12px;
}

.property-picker__toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.property-picker__search {
  flex: 1 1 320px;
}

.property-picker__state {
  padding: 12px 0;
  color: var(--c-page-muted);
}

.property-picker__list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  overflow: auto;
  padding-right: 4px;
  flex: 1 1 auto;
  min-height: 0;
}

.property-picker__item {
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
}

.property-picker__item :deep(.card) {
  height: 100%;
}

.property-picker__footer {
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

@media (max-width: 900px) {
  .property-picker__list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .property-picker {
    padding: 12px;
  }

  .property-picker__dialog {
    padding: 18px;
    border-radius: 20px;
    max-height: calc(100vh - 24px);
  }
}
</style>
