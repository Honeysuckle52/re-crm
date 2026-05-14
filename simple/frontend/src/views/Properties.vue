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
          v-if="false"
          to="/properties/new"
          class="btn btn--accent">
          + Добавить объект
        </router-link>
        <div v-if="auth.isStaff" class="row properties-hero__actions" style="gap: 8px; flex-wrap: wrap">
          <input
            ref="importInput"
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            class="properties-import__input"
            @change="handleImportFile" />
          <button class="btn btn--sm" :disabled="loading" @click="openImportDialog">
            Импорт CSV/XLSX
          </button>
          <button class="btn btn--sm" :disabled="loading" @click="exportProperties('csv')">
            Экспорт CSV
          </button>
          <button class="btn btn--sm" :disabled="loading" @click="exportProperties('xlsx')">
            Экспорт XLSX
          </button>
          <button class="btn btn--sm" :disabled="loading" @click="exportProperties('json')">
            Экспорт JSON
          </button>
          <router-link to="/properties/new" class="btn btn--accent">
            + Добавить объект
          </router-link>
        </div>
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
          <button class="btn btn--primary btn--sm" @click="applyFilters">Применить</button>
        </div>
      </aside>

      <section class="properties-main">
        <div class="panel panel--light properties-main__head">
          <div class="properties-main__meta">
            <div class="hero__eyebrow properties-main__eyebrow">Каталог</div>
            <h2 class="h2">Найдено {{ propertyCount }} объектов</h2>
          </div>
        </div>

        <div v-if="auth.isStaff && items.length" class="properties-selection">
          <label class="bulk-toggle">
            <input
              type="checkbox"
              :checked="allPropertiesOnPageSelected"
              @change="togglePropertiesPageSelection($event.target.checked)" />
            <span>Выбрать все карточки на странице</span>
          </label>
        </div>

        <div class="panel panel--light properties-results">
          <BulkActionBar
            v-if="auth.isStaff"
            :count="selectedPropertyCount"
            label="объектов"
            @clear="clearPropertySelection"
          >
            <button
              class="btn btn--sm btn--primary"
              :disabled="loading"
              type="button"
              @click="archiveSelectedProperties"
            >
              В архив
            </button>
          </BulkActionBar>
          <div class="properties-results__body">
            <div v-if="loading" class="empty properties-empty">Загрузка…</div>
            <div v-else-if="items.length" class="properties-grid">
              <div
                v-for="p in items"
                :key="p.id"
                class="properties-grid__item"
                :class="{ 'is-selected': isPropertySelected(p) }"
              >
                <label v-if="auth.isStaff" class="properties-grid__check" @click.stop>
                  <input
                    type="checkbox"
                    :checked="isPropertySelected(p)"
                    @change="togglePropertySelection(p, $event.target.checked)" />
                </label>
                <PropertyCard :property="p" />
              </div>
            </div>
            <div v-else class="empty properties-empty">
              Ничего не найдено по выбранным фильтрам.
            </div>
          </div>
          <ListPagination
            v-if="propertyCount > items.length"
            :count="propertyCount"
            :page="propertyPage"
            :visible-count="items.length"
            :page-size="propertyPageSize"
            label="объектов"
            :disabled="loading"
            @change="setPropertyPage"
            @change-page-size="setPropertyPageSize"
          />
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import api from '../api'
import { bulkArchiveProperties } from '../api/bulk'
import { exportEntityData } from '../api/exports'
import BulkActionBar from '../components/BulkActionBar.vue'
import ListPagination from '../components/ListPagination.vue'
import PropertyCard from '../components/PropertyCard.vue'
import { useBulkSelection } from '../composables/useBulkSelection'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const confirm = useConfirmStore()
const toasts = useToastsStore()

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
const importInput = ref(null)
const propertyPage = ref(1)
const propertyPageSize = ref(DEFAULT_PAGE_SIZE)
const propertyCount = ref(0)
const {
  selectedIds: selectedPropertyIds,
  selectedCount: selectedPropertyCount,
  allOnPageSelected: allPropertiesOnPageSelected,
  isSelected: isPropertySelected,
  toggleSelection: togglePropertySelection,
  togglePageSelection: togglePropertiesPageSelection,
  clearSelection: clearPropertySelection,
} = useBulkSelection(items)

async function load () {
  loading.value = true
  try {
    const params = {
      page: propertyPage.value,
      page_size: propertyPageSize.value,
    }
    for (const [k, v] of Object.entries(filters)) {
      if (v !== '' && v !== null) params[k] = v
    }
    const { data } = await api.get('/properties/', { params })
    const payload = unpackPaginated(data)
    items.value = payload.items
    propertyCount.value = payload.count
  } finally {
    loading.value = false
  }
}

function exportParams () {
  const params = {}
  for (const [k, v] of Object.entries(filters)) {
    if (v !== '' && v !== null) params[k] = v
  }
  return params
}

async function applyFilters () {
  if (propertyPage.value !== 1) {
    propertyPage.value = 1
    return
  }
  await load()
}

async function reset () {
  Object.assign(filters, {
    operation_type: '',
    status: '',
    rooms: '',
    min_price: null,
    max_price: null,
    search: '',
  })
  if (propertyPage.value !== 1) {
    propertyPage.value = 1
    return
  }
  await load()
}

function setPropertyPage (page) {
  if (page < 1 || page === propertyPage.value) return
  propertyPage.value = page
}

function setPropertyPageSize (size) {
  if (!size || size === propertyPageSize.value) return
  propertyPageSize.value = size
}

function openImportDialog () {
  importInput.value?.click()
}

async function handleImportFile (event) {
  const file = event.target?.files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  loading.value = true
  try {
    const { data } = await api.post('/properties/import-csv/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    toasts.success(`Импорт завершён: создано ${data.created}, обновлено ${data.updated}.`)
    if (propertyPage.value !== 1) {
      propertyPage.value = 1
    } else {
      await load()
    }
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось импортировать файл'))
  } finally {
    loading.value = false
    if (event.target) event.target.value = ''
  }
}

async function exportProperties (format) {
  loading.value = true
  try {
    await exportEntityData(
      '/properties/export/',
      format,
      exportParams(),
      `properties.${format}`,
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось выгрузить каталог объектов'))
  } finally {
    loading.value = false
  }
}

async function archiveSelectedProperties () {
  if (!selectedPropertyIds.value.length) return
  const approved = await confirm.ask({
    title: 'Архивирование объектов',
    message: `Архивировать выбранные объекты (${selectedPropertyIds.value.length})?`,
    confirmLabel: 'В архив',
    danger: true,
  })
  if (!approved) return

  loading.value = true
  const result = await bulkArchiveProperties([...selectedPropertyIds.value])
  loading.value = false
  if (!result.ok) {
    toasts.error(result.error || 'Не удалось архивировать выбранные объекты')
    return
  }

  clearPropertySelection()
  const { archived, errors, not_found_ids: notFoundIds = [] } = result.data
  await load()
  if (errors?.length || notFoundIds.length) {
    toasts.warn(
      `Архивировано: ${archived}. Пропущено: ${errors.length + notFoundIds.length}.`,
    )
    return
  }
  toasts.success(`В архив переведено объектов: ${archived}.`)
}

watch(propertyPage, async () => {
  await load()
})

watch(propertyPageSize, async () => {
  if (propertyPage.value !== 1) {
    propertyPage.value = 1
    return
  }
  await load()
})

onMounted(async () => {
  const [o, s] = await Promise.all([
    api.get('/operation-types/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/property-statuses/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
  ])
  dict.operations = unpackPaginated(o.data).items
  dict.statuses = unpackPaginated(s.data).items
  await load()
})
</script>

<style scoped>
.properties-page {
  min-height: 0;
}

.properties-import__input {
  display: none;
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

.properties-filter__grid > .field > .input,
.properties-filter__grid > .field > .select {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.16);
  color-scheme: light;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 10px 22px rgba(16, 55, 52, 0.08);
}

.properties-filter__grid > .field > .input::placeholder {
  color: rgba(21, 56, 57, 0.56);
}

.properties-filter__grid > .field > .select {
  background-image:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)),
    linear-gradient(45deg, transparent 50%, rgba(21, 56, 57, 0.62) 50%),
    linear-gradient(135deg, rgba(21, 56, 57, 0.62) 50%, transparent 50%);
  background-position:
    0 0,
    calc(100% - 24px) calc(50% - 3px),
    calc(100% - 18px) calc(50% - 3px);
  background-size:
    100% 100%,
    6px 6px,
    6px 6px;
  background-repeat: no-repeat;
}

.properties-filter__grid > .field > .input:hover,
.properties-filter__grid > .field > .select:hover {
  border-color: rgba(21, 56, 57, 0.24);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 12px 24px rgba(16, 55, 52, 0.1);
}

.properties-filter__grid > .field > .input:focus,
.properties-filter__grid > .field > .select:focus {
  border-color: rgba(21, 56, 57, 0.28);
  box-shadow:
    0 0 0 1px rgba(21, 56, 57, 0.16),
    0 0 0 5px rgba(230, 238, 242, 0.92),
    0 12px 24px rgba(16, 55, 52, 0.12);
}

.properties-filter__grid > .field > .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
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

.properties-selection {
  display: flex;
  align-items: center;
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

.properties-grid__item {
  position: relative;
}

.properties-grid__item.is-selected {
  transform: translateY(-2px);
}

.properties-grid__item.is-selected :deep(.property-card) {
  box-shadow: 0 16px 28px rgba(16, 55, 52, 0.16);
  border-color: rgba(21, 56, 57, 0.28);
}

/* ---- custom checkbox wrapper (card corner) ---- */
.properties-grid__check {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  cursor: pointer;
}

/* Hide native input, keep it accessible */
.properties-grid__check input[type="checkbox"] {
  appearance: none;
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 1.5px solid rgba(21, 56, 57, 0.22);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  cursor: pointer;
  display: block;
  transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
  box-shadow: 0 2px 8px rgba(16, 55, 52, 0.10);
}

.properties-grid__check input[type="checkbox"]:hover {
  border-color: rgba(21, 56, 57, 0.42);
  background: rgba(255, 255, 255, 0.96);
}

.properties-grid__check input[type="checkbox"]:checked {
  background: var(--c-accent, #2e9f98);
  border-color: var(--c-accent, #2e9f98);
  box-shadow: 0 2px 10px rgba(46, 159, 152, 0.32);
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 12 10' xmlns='http://www.w3.org/2000/svg'%3E%3Cpolyline points='1.5,5.5 4.5,8.5 10.5,1.5' fill='none' stroke='%23fff' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  background-size: 10px 10px;
}

/* ---- bulk-toggle (select all) ---- */
.bulk-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--c-page-text);
  cursor: pointer;
}

.bulk-toggle input[type="checkbox"] {
  appearance: none;
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1.5px solid rgba(21, 56, 57, 0.22);
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
  display: block;
  flex-shrink: 0;
  transition: border-color 0.18s ease, background 0.18s ease;
}

.bulk-toggle input[type="checkbox"]:hover {
  border-color: rgba(21, 56, 57, 0.42);
}

.bulk-toggle input[type="checkbox"]:checked {
  background: var(--c-accent, #2e9f98);
  border-color: var(--c-accent, #2e9f98);
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 12 10' xmlns='http://www.w3.org/2000/svg'%3E%3Cpolyline points='1.5,5.5 4.5,8.5 10.5,1.5' fill='none' stroke='%23fff' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  background-size: 9px 9px;
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
