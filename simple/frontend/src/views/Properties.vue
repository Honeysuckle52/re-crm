<template>
  <section class="stack properties-page">
    <div class="hero properties-page__hero">
      <div class="row row--between properties-page__hero-top">
        <div>
          <div class="hero__eyebrow">Объекты</div>
          <h1 class="h2 properties-page__title">Каталог недвижимости</h1>
        </div>
        <div v-if="canManageProperties" class="row properties-hero__actions">
          <input
            ref="importInput"
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            class="properties-import__input"
            @change="handleImportFile" />
          <button class="btn btn--sm" :disabled="loading" @click="openImportDialog">
            Импорт CSV/XLSX
          </button>
          <router-link to="/properties/new" class="btn btn--accent">
            + Добавить объект
          </router-link>
        </div>
        <div v-else-if="auth.isClient && isMyProperties" class="row properties-hero__actions">
          <router-link to="/properties/new" class="btn btn--accent">
            + Подать заявку
          </router-link>
        </div>
      </div>
    </div>

    <div class="properties-shell">
      <aside class="panel panel--light properties-filter">
        <div class="properties-filter__sticky">
          <div class="surface-head properties-filter__head">
            <div class="surface-head__meta">
              <div class="hero__eyebrow properties-filter__eyebrow">Фильтр</div>
              <h2 class="h3">Фильтр объектов</h2>
            </div>
            <div class="surface-head__caption">
              Активно фильтров: {{ activeFilterCount }}
            </div>
          </div>

          <div class="properties-filter__sections">
            <section v-for="section in filterSections" :key="section.key" v-show="section.visible" class="properties-filter__section">
              <button class="properties-filter__section-toggle" type="button" @click="toggleSection(section.key)">
                <span>{{ section.title }}</span>
                <span class="properties-filter__section-mark">{{ sectionOpenState[section.key] ? '−' : '+' }}</span>
              </button>

              <div v-show="sectionOpenState[section.key]" class="properties-filter__section-body">
                <div v-if="section.key === 'main'" class="grid properties-filter__grid">
                  <div class="field">
                    <label>Тип операции</label>
                    <select class="select" v-model="filters.operation_type">
                      <option value="">Все</option>
                      <option v-for="item in dict.operations" :key="item.id" :value="item.id">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>

                  <div v-if="auth.isStaff" class="field">
                    <label>Статус</label>
                    <select class="select" v-model="filters.status">
                      <option value="">Все</option>
                      <option v-for="item in dict.statuses" :key="item.id" :value="item.id">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>

                  <div class="field">
                    <label>Тип объекта</label>
                    <select class="select" v-model="filters.premises_type">
                      <option value="">Все</option>
                      <option v-for="item in dict.propertyTypes" :key="item.id" :value="item.code">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>

                  <div class="field">
                    <label>Поиск</label>
                    <input class="input" v-model="filters.search" placeholder="Название или описание" />
                  </div>

                  <div v-if="showRoomsFilter" class="field">
                    <label>Цена от</label>
                    <input class="input" type="number" v-model.number="filters.min_price" />
                  </div>

                  <div class="field">
                    <label>Цена до</label>
                    <input class="input" type="number" v-model.number="filters.max_price" />
                  </div>

                  <div class="field">
                    <label>Площадь от</label>
                    <input class="input" type="number" v-model.number="filters.min_area" />
                  </div>

                  <div class="field">
                    <label>Площадь до</label>
                    <input class="input" type="number" v-model.number="filters.max_area" />
                  </div>
                </div>

                <div v-else-if="section.key === 'house'" class="grid properties-filter__grid">
                  <div v-if="canUseBuildingMaterial" class="field">
                    <label>Материал стен</label>
                    <select class="select" v-model="filters.building_material">
                      <option value="">Любой</option>
                      <option v-for="item in dict.buildingMaterials" :key="item.id" :value="item.id">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>

                  <div v-if="canUseYearBuilt" class="field">
                    <label>Год постройки от</label>
                    <input class="input" type="number" v-model.number="filters.year_built_from" />
                  </div>

                  <div v-if="canUseYearBuilt" class="field">
                    <label>Год постройки до</label>
                    <input class="input" type="number" v-model.number="filters.year_built_to" />
                  </div>

                  <div v-if="isHouse" class="field">
                    <label>Этажей в доме</label>
                    <select class="select" v-model="filters.total_floors">
                      <option value="">Любое</option>
                      <option value="1">1</option>
                      <option value="2">2</option>
                      <option value="3+">3+</option>
                    </select>
                  </div>
                </div>

                <div v-else-if="section.key === 'space'" class="grid properties-filter__grid">
                  <div class="field">
                    <label>Комнаты</label>
                    <div class="properties-filter__chip-row">
                      <button
                        v-for="room in roomOptions"
                        :key="room.value"
                        type="button"
                        class="btn btn--sm"
                        :class="{ 'btn--primary': filters.rooms === room.value }"
                        @click="filters.rooms = filters.rooms === room.value ? '' : room.value"
                      >
                        {{ room.label }}
                      </button>
                    </div>
                  </div>

                  <div v-if="propertyTypeHasFloor(selectedPremisesType)" class="field">
                    <label>Этаж</label>
                    <input class="input" type="number" v-model.number="filters.floor_number" />
                  </div>

                  <div class="field">
                    <label>Не первый этаж</label>
                    <label class="chip-check">
                      <input type="checkbox" v-model="filters.not_first_floor" />
                      Да
                    </label>
                  </div>

                  <div class="field">
                    <label>Не последний этаж</label>
                    <label class="chip-check">
                      <input type="checkbox" v-model="filters.not_last_floor" />
                      Да
                    </label>
                  </div>

                  <div v-if="canUseRenovationType" class="field">
                    <label>Тип ремонта</label>
                    <select class="select" v-model="filters.renovation_type">
                      <option value="">Любой</option>
                      <option v-for="item in dict.renovationTypes" :key="item.id" :value="item.id">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>

                  <div v-if="canUseBathroomType" class="field">
                    <label>Тип санузла</label>
                    <select class="select" v-model="filters.bathroom_type">
                      <option value="">Любой</option>
                      <option v-for="item in dict.bathroomTypes" :key="item.id" :value="item.id">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>
                </div>

                <div v-else-if="section.key === 'commercial'" class="grid properties-filter__grid">
                  <div class="field">
                    <label>Тип коммерческой недвижимости</label>
                    <select class="select" v-model="filters.commercial_type">
                      <option value="">Любой</option>
                      <option v-for="item in dict.commercialTypes" :key="item.id" :value="item.id">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>

                  <div class="field">
                    <label>Отдельный вход</label>
                    <label class="chip-check">
                      <input type="checkbox" v-model="filters.has_separate_entrance" />
                      Да
                    </label>
                  </div>

                  <div class="field">
                    <label>Первая линия</label>
                    <label class="chip-check">
                      <input type="checkbox" v-model="filters.is_first_line" />
                      Да
                    </label>
                  </div>

                  <div class="field">
                    <label>Витринные окна</label>
                    <label class="chip-check">
                      <input type="checkbox" v-model="filters.has_display_windows" />
                      Да
                    </label>
                  </div>

                  <div class="field">
                    <label>Парковочных мест от</label>
                    <input class="input" type="number" v-model.number="filters.min_parking_spaces" />
                  </div>
                </div>

                <div v-else-if="section.key === 'land'" class="grid properties-filter__grid">
                  <div class="field">
                    <label>Площадь участка от</label>
                    <input class="input" type="number" v-model.number="filters.min_land_area" />
                  </div>

                  <div v-if="isLand" class="field">
                    <label>Площадь участка до</label>
                    <input class="input" type="number" v-model.number="filters.max_land_area" />
                  </div>
                </div>

                <div v-else-if="section.key === 'amenities'" class="field">
                  <label>Удобства</label>
                  <div class="properties-filter__amenities">
                    <label v-for="item in dict.amenities" :key="item.id" class="chip-check">
                      <input type="checkbox" :value="item.id" v-model="filters.amenity_ids" />
                      {{ item.name }}
                    </label>
                  </div>
                </div>

              </div>
            </section>
          </div>

          <div class="row properties-filter__actions">
            <button class="btn btn--sm" @click="reset">Сбросить</button>
            <button class="btn btn--primary btn--sm" @click="applyFilters">Применить</button>
          </div>
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
            <button
              class="btn btn--sm btn--accent"
              :disabled="loading || !selectedPropertyCount"
              type="button"
              @click="openAttachToRequestDialog"
            >
              Прикрепить к заявке
            </button>
          </BulkActionBar>

          <div class="properties-results__body">
            <div v-if="loading" class="empty properties-empty">Загрузка…</div>
            <div v-else-if="items.length" class="properties-grid">
              <div
                v-for="property in items"
                :key="property.id"
                class="properties-grid__item"
                :class="{ 'is-selected': isPropertySelected(property) }"
              >
                <label v-if="auth.isStaff" class="properties-grid__check" @click.stop>
                  <input
                    type="checkbox"
                    :checked="isPropertySelected(property)"
                    @change="togglePropertySelection(property, $event.target.checked)" />
                </label>
                <PropertyCard :property="property" />
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

  <Teleport to="body">
    <div v-if="attachRequestDialogOpen" class="modal-overlay" @click.self="closeAttachToRequestDialog">
      <div class="modal properties-page__modal">
        <div class="surface-head">
          <div class="surface-head__meta">
            <h3 class="h3">Прикрепить объекты к заявке</h3>
            <div class="muted properties-page__modal-text">
              Выбрано {{ selectedPropertyCount }} объектов. Найдите заявку и подтвердите привязку.
            </div>
          </div>
        </div>

        <div class="stack properties-page__modal-stack">
          <RemoteLookupField
            v-model="attachRequestId"
            label="Заявка"
            placeholder="Найти заявку по номеру, клиенту или объекту"
            endpoint="/requests/"
            :params="{ ordering: '-updated_at' }"
            :map-option="mapRequestOption"
            no-results-text="Заявки не найдены."
            @select="selectedAttachRequestLabel = $event.label"
          />
          <div class="muted" v-if="selectedAttachRequestLabel">
            Выбрана: {{ selectedAttachRequestLabel }}
          </div>
        </div>

        <div class="row properties-page__modal-actions">
          <button type="button" class="btn" @click="closeAttachToRequestDialog">Отмена</button>
          <button
            type="button"
            class="btn btn--accent"
            :disabled="attachRequestLoading || !attachRequestId"
            @click="attachSelectedPropertiesToRequest"
          >
            {{ attachRequestLoading ? 'Прикрепление…' : 'Прикрепить' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { bulkArchiveProperties } from '../api/bulk'
import BulkActionBar from '../components/BulkActionBar.vue'
import ListPagination from '../components/ListPagination.vue'
import RemoteLookupField from '../components/RemoteLookupField.vue'
import PropertyCard from '../components/PropertyCard.vue'
import { useBulkSelection } from '../composables/useBulkSelection'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import {
  normalizePropertyType,
  propertyTypeHasFloor,
  propertyTypeIsCommercial,
  propertyTypeUsesRooms,
} from '@/utils/propertyTypes'

const auth = useAuthStore()
const route = useRoute()
const confirm = useConfirmStore()
const toasts = useToastsStore()
const canManageProperties = computed(() => auth.canCreatePropertyReport)
const isMyProperties = computed(() => route.name === 'client-properties')

function defaultFilters() {
  return {
    operation_type: '',
    status: '',
    premises_type: '',
    rooms: '',
    floor_number: '',
    total_floors: '',
    renovation_type: '',
    bathroom_type: '',
    building_material: '',
    commercial_type: '',
    has_separate_entrance: false,
    is_first_line: false,
    has_display_windows: false,
    min_parking_spaces: null,
    min_land_area: null,
    max_land_area: null,
    amenity_ids: [],
    year_built_from: '',
    year_built_to: '',
    not_last_floor: false,
    not_first_floor: false,
    min_area: null,
    max_area: null,
    min_price: null,
    max_price: null,
    search: '',
    owner: '',
  }
}

const filters = reactive({
  ...defaultFilters(),
})

const dict = reactive({
  operations: [],
  statuses: [],
  propertyTypes: [],
  renovationTypes: [],
  bathroomTypes: [],
  buildingMaterials: [],
  commercialTypes: [],
  amenities: [],
})
const items = ref([])
const loading = ref(false)
const importInput = ref(null)
const propertyPage = ref(1)
const propertyPageSize = ref(DEFAULT_PAGE_SIZE)
const propertyCount = ref(0)
const attachRequestDialogOpen = ref(false)
const attachRequestLoading = ref(false)
const attachRequestId = ref(null)
const selectedAttachRequestLabel = ref('')
const roomOptions = [
  { value: '0', label: 'Студия' },
  { value: '1', label: '1' },
  { value: '2', label: '2' },
  { value: '3', label: '3' },
  { value: '4', label: '4' },
  { value: '5+', label: '5+' },
]
const sectionOpenState = reactive({
  main: true,
  house: true,
  space: true,
  commercial: true,
  land: true,
  amenities: false,
})

const selectedPremisesType = computed(() => normalizePropertyType(filters.premises_type))
const isApartmentOrRoom = computed(() => ['apartment', 'room'].includes(selectedPremisesType.value))
const isHouse = computed(() => selectedPremisesType.value === 'house')
const isCommercial = computed(() => propertyTypeIsCommercial(selectedPremisesType.value))
const isLand = computed(() => selectedPremisesType.value === 'land')
const isGarage = computed(() => selectedPremisesType.value === 'garage')
const isResidential = computed(() => ['apartment', 'room', 'house'].includes(selectedPremisesType.value))
const canUseBuildingMaterial = computed(() => ['apartment', 'room', 'house'].includes(selectedPremisesType.value))
const canUseYearBuilt = computed(() => ['apartment', 'house', 'room'].includes(selectedPremisesType.value))
const canUseBathroomType = computed(() => ['apartment', 'room'].includes(selectedPremisesType.value))
const canUseRenovationType = computed(() => ['apartment', 'room', 'garage'].includes(selectedPremisesType.value))
const canUseLandArea = computed(() => ['house', 'land'].includes(selectedPremisesType.value))
const showRoomsFilter = computed(() => isResidential.value)
const filterSections = computed(() => ([
  { key: 'main', title: 'Основное', visible: true },
  { key: 'house', title: 'О доме', visible: canUseBuildingMaterial.value || canUseYearBuilt.value || isHouse.value },
  { key: 'space', title: 'О помещении', visible: isApartmentOrRoom.value || isHouse.value || isGarage.value },
  { key: 'commercial', title: 'Коммерческая', visible: isCommercial.value },
  { key: 'land', title: 'Участок', visible: canUseLandArea.value },
  { key: 'amenities', title: 'Удобства', visible: true },
]))
const activeFilterCount = computed(() => {
  let count = 0
  for (const [key, value] of Object.entries(filters)) {
    if (key === 'owner') continue
    if (Array.isArray(value) && value.length) count += 1
    else if (typeof value === 'boolean' && value) count += 1
    else if (value !== '' && value !== null && value !== undefined) count += 1
  }
  return count
})
const {
  selectedIds: selectedPropertyIds,
  selectedCount: selectedPropertyCount,
  allOnPageSelected: allPropertiesOnPageSelected,
  isSelected: isPropertySelected,
  toggleSelection: togglePropertySelection,
  togglePageSelection: togglePropertiesPageSelection,
  clearSelection: clearPropertySelection,
} = useBulkSelection(items)

function toggleSection(key) {
  sectionOpenState[key] = !sectionOpenState[key]
}

function serializeFilters() {
  const params = {}
  for (const [key, value] of Object.entries(filters)) {
    if (key === 'amenity_ids') {
      if (Array.isArray(value) && value.length) params[key] = value.join(',')
      continue
    }
    if (key === 'not_first_floor') {
      if (value) params.floor_number__gt = 1
      continue
    }
    if (key === 'not_last_floor') {
      if (value) params[key] = 'true'
      continue
    }
    if (typeof value === 'boolean') {
      if (value) params[key] = 'true'
      continue
    }
    if (value !== '' && value !== null && value !== undefined) {
      params[key] = key === 'premises_type' ? normalizePropertyType(value) : value
    }
  }
  return params
}

async function load() {
  loading.value = true
  try {
    const params = {
      page: propertyPage.value,
      page_size: propertyPageSize.value,
      ...serializeFilters(),
    }
    const { data } = await api.get('/properties/', { params })
    const payload = unpackPaginated(data)
    items.value = payload.items
    propertyCount.value = payload.count
  } finally {
    loading.value = false
  }
}

function syncRouteFilters() {
  Object.assign(filters, defaultFilters())
  filters.owner = isMyProperties.value ? 'me' : ''
  propertyPage.value = 1
  propertyPageSize.value = DEFAULT_PAGE_SIZE
  clearPropertySelection()
  items.value = []
  propertyCount.value = 0
}

function mapRequestOption(request) {
  return {
    id: request.id,
    label: `Заявка №${request.id}`,
    hint: [request.client_username, request.property_title, request.status_name]
      .filter(Boolean)
      .join(' · ') || 'Заявка',
  }
}

function openAttachToRequestDialog() {
  if (!selectedPropertyIds.value.length) return
  attachRequestDialogOpen.value = true
}

function closeAttachToRequestDialog() {
  attachRequestDialogOpen.value = false
  attachRequestId.value = null
  selectedAttachRequestLabel.value = ''
}

async function attachSelectedPropertiesToRequest() {
  if (!attachRequestId.value || !selectedPropertyIds.value.length) return
  attachRequestLoading.value = true
  try {
    const propertyIds = [...new Set(selectedPropertyIds.value)]
    const results = []
    for (const propertyId of propertyIds) {
      try {
        const { data } = await api.post(`/requests/${attachRequestId.value}/attach_property/`, {
          property_id: propertyId,
        })
        results.push(data)
      } catch (err) {
        const detail = err?.response?.data?.detail || `Не удалось прикрепить объект #${propertyId}`
        throw new Error(detail)
      }
    }
    toasts.success(`К заявке прикреплено объектов: ${results.length}.`)
    clearPropertySelection()
    closeAttachToRequestDialog()
  } catch (err) {
    toasts.error(err?.message || 'Не удалось прикрепить объекты к заявке')
  } finally {
    attachRequestLoading.value = false
  }
}

async function applyFilters() {
  if (propertyPage.value !== 1) {
    propertyPage.value = 1
    return
  }
  await load()
}

async function reset() {
  syncRouteFilters()
  if (propertyPage.value !== 1) {
    propertyPage.value = 1
    return
  }
  await load()
}

function setPropertyPage(page) {
  if (page < 1 || page === propertyPage.value) return
  propertyPage.value = page
}

function setPropertyPageSize(size) {
  if (!size || size === propertyPageSize.value) return
  propertyPageSize.value = size
}

function openImportDialog() {
  importInput.value?.click()
}

async function handleImportFile(event) {
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

async function archiveSelectedProperties() {
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
    toasts.warn(`Архивировано: ${archived}. Пропущено: ${errors.length + notFoundIds.length}.`)
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
  const [
    operations,
    statuses,
    propertyTypes,
    renovationTypes,
    bathroomTypes,
    buildingMaterials,
    commercialTypes,
    amenities,
  ] = await Promise.all([
    api.get('/operation-types/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/property-statuses/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/property-types/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/renovation-types/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/bathroom-types/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/building-materials/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/commercial-property-types/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
    api.get('/amenities/', { params: { page_size: LOOKUP_PAGE_SIZE } }),
  ])
  dict.operations = unpackPaginated(operations.data).items
  dict.statuses = unpackPaginated(statuses.data).items
  dict.propertyTypes = unpackPaginated(propertyTypes.data).items
  dict.renovationTypes = unpackPaginated(renovationTypes.data).items
  dict.bathroomTypes = unpackPaginated(bathroomTypes.data).items
  dict.buildingMaterials = unpackPaginated(buildingMaterials.data).items
  dict.commercialTypes = unpackPaginated(commercialTypes.data).items
  dict.amenities = unpackPaginated(amenities.data).items
  syncRouteFilters()
  await load()
})

watch(() => route.name, async () => {
  syncRouteFilters()
  await load()
})

watch(() => filters.premises_type, (value) => {
  const type = normalizePropertyType(value)
  if (!propertyTypeUsesRooms(type)) {
    filters.rooms = ''
  }
  if (!propertyTypeHasFloor(type)) {
    filters.floor_number = ''
    filters.not_first_floor = false
    filters.not_last_floor = false
  }
  if (!['apartment', 'room', 'house'].includes(type)) {
    filters.building_material = ''
  }
  if (!['apartment', 'house', 'room'].includes(type)) {
    filters.year_built_from = ''
    filters.year_built_to = ''
  }
  if (!['house', 'land'].includes(type)) {
    filters.min_land_area = null
    filters.max_land_area = null
  } else if (type === 'house') {
    filters.max_land_area = null
  }
  if (!['apartment', 'room'].includes(type)) {
    filters.bathroom_type = ''
  }
  if (!['apartment', 'room', 'garage'].includes(type)) {
    filters.renovation_type = ''
  }
  if (!propertyTypeUsesRooms(type)) {
    filters.rooms = ''
  }
  if (type !== 'house') {
    filters.total_floors = ''
  }
  if (!propertyTypeIsCommercial(type)) {
    filters.commercial_type = ''
    filters.has_separate_entrance = false
    filters.is_first_line = false
    filters.has_display_windows = false
    filters.min_parking_spaces = null
  }
})
</script>

<style scoped>
.properties-page {
  min-height: 0;
}

.properties-page__hero {
  padding: 24px 28px;
}

.properties-page__hero-top,
.properties-hero__actions {
  flex-wrap: wrap;
  gap: 8px;
}

.properties-page__title {
  margin-top: 8px;
  color: #fff;
}

.properties-import__input {
  display: none;
}

.properties-shell {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
  min-height: 0;
}

.properties-filter {
  position: sticky;
  top: 84px;
  padding: 0;
}

.properties-filter__sticky {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
}

.properties-filter__eyebrow {
  align-self: flex-start;
}

.properties-filter__sections {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.properties-filter__section {
  border-top: 1px solid var(--c-border);
  padding-top: 8px;
}

.properties-filter__section-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  background: transparent;
  border: none;
  color: var(--c-text);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.properties-filter__section-mark {
  font-size: 22px;
  line-height: 1;
  color: var(--c-accent-2);
}

.properties-filter__section-body {
  padding: 8px 0 6px;
}

.properties-filter__grid {
  grid-template-columns: 1fr;
  gap: 14px;
}

.properties-filter__grid > .field > .input,
.properties-filter__grid > .field > .select,
.properties-filter__grid > .field > .textarea {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)) !important;
  color: var(--c-page-text) !important;
  border-color: rgba(21, 56, 57, 0.16) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 10px 22px rgba(16, 55, 52, 0.08);
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

.properties-filter__chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.properties-filter__amenities {
  display: flex;
  max-height: 220px;
  flex-wrap: wrap;
  gap: 8px;
  overflow: auto;
  padding-right: 6px;
}

.properties-filter__actions {
  justify-content: flex-start;
  flex-wrap: wrap;
  padding-top: 8px;
  border-top: 1px solid var(--c-border);
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
}

.properties-results {
  min-height: calc(100vh - 232px);
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.properties-results__body {
  flex: 1 1 auto;
  max-height: calc(100vh - 256px);
  overflow-y: auto;
  padding-right: 6px;
}

.properties-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
  align-content: start;
  align-items: stretch;
}

.properties-grid__item {
  position: relative;
  display: flex;
  flex-direction: column;
}

.properties-grid__item :deep(.card--link) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.properties-grid__item.is-selected {
  transform: translateY(-2px);
}

.properties-grid__item.is-selected :deep(.property-card) {
  box-shadow: 0 16px 28px rgba(16, 55, 52, 0.16);
  border-color: rgba(21, 56, 57, 0.28);
}

.properties-grid__check {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  cursor: pointer;
}

.properties-grid__check input[type='checkbox'],
.bulk-toggle input[type='checkbox'] {
  appearance: none;
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 1.5px solid rgba(21, 56, 57, 0.22);
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
  display: block;
}

.properties-grid__check input[type='checkbox']:checked,
.bulk-toggle input[type='checkbox']:checked {
  background: var(--c-accent);
  border-color: var(--c-accent);
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 12 10' xmlns='http://www.w3.org/2000/svg'%3E%3Cpolyline points='1.5,5.5 4.5,8.5 10.5,1.5' fill='none' stroke='%23fff' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  background-size: 10px 10px;
}

.bulk-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--c-page-text);
  cursor: pointer;
}

.properties-empty {
  min-height: 280px;
}

.properties-page__modal {
  width: min(720px, calc(100vw - 32px));
}

.properties-page__modal-text {
  margin-top: 6px;
}

.properties-page__modal-stack {
  gap: 14px;
  margin-top: 18px;
}

.properties-page__modal-actions {
  gap: 10px;
  justify-content: flex-end;
  margin-top: 22px;
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

  .properties-results {
    min-height: auto;
  }

  .properties-results__body {
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }
}

@media (max-width: 640px) {
  .properties-grid,
  .properties-page__modal-actions {
    grid-template-columns: 1fr;
  }

  .properties-page__modal-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
