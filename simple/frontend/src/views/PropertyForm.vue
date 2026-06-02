<template>
  <section class="stack property-form-page">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">{{ isEdit ? 'РЕДАКТИРОВАНИЕ' : 'НОВЫЙ ОБЪЕКТ' }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ isEdit ? 'Изменить объект' : 'Создать объект' }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Заполните карточку объекта, подготовьте адрес, медиа и описание для дальнейшей работы по заявкам.
          </div>
        </div>
        <button class="btn btn--ghost" type="button" @click="$router.back()">Назад</button>
      </div>
    </div>

    <div v-if="false" class="kpi-strip">
      <article class="kpi-card">
        <span class="kpi-card__label">Режим</span>
        <strong class="kpi-card__value">{{ formModeLabel }}</strong>
        <span class="kpi-card__meta">{{ isEdit ? 'Обновление существующей карточки' : 'Создание нового объекта в каталоге' }}</span>
      </article>
      <article class="kpi-card">
        <span class="kpi-card__label">Адрес</span>
        <strong class="kpi-card__value">{{ addressStateLabel }}</strong>
        <span class="kpi-card__meta">{{ addressPicked?.value || existingAddress || 'Выберите адрес из подсказок' }}</span>
      </article>
      <article class="kpi-card">
        <span class="kpi-card__label">Фотографии</span>
        <strong class="kpi-card__value">{{ photoCount }}</strong>
        <span class="kpi-card__meta">Обложка: {{ coverCount ? 'назначена' : 'не выбрана' }}</span>
      </article>
      <article class="kpi-card kpi-card--accent">
        <span class="kpi-card__label">Характеристики</span>
        <strong class="kpi-card__value">{{ selectedFeaturesCount }}</strong>
        <span class="kpi-card__meta">Отмечено параметров объекта</span>
      </article>
    </div>

    <form class="panel panel--light stack property-form" @submit.prevent="submit">
      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Карточка объекта</div>
          <h2 class="h3">Основные параметры</h2>
        </div>
        <div class="surface-head__caption">Базовые данные для каталога и дальнейшей работы по заявкам.</div>
      </div>
      <div class="grid grid--2 property-form__main-grid">
        <div class="field">
          <label>Заголовок</label>
          <input class="input" v-model="form.title" required
                 placeholder="Например: 2-комнатная на Ленина" />
        </div>
        <div class="field">
          <label>Тип операции</label>
          <select class="select" v-model.number="form.operation_type" required>
            <option v-for="o in dict.operations" :key="o.id" :value="o.id">
              {{ o.name }}
            </option>
          </select>
        </div>

        <div class="field">
          <label>Цена, ₽</label>
          <input class="input" type="number" step="0.01"
                 v-model.number="form.price" required />
        </div>
        <div class="field">
          <label>Цена за м²</label>
          <input class="input" type="number" step="0.01"
                 v-model.number="form.price_per_sqm" />
        </div>

        <div class="field">
          <label>Тип помещения</label>
          <select class="select" v-model="form.premises_type" required>
            <option value="apartment">Квартира</option>
            <option value="house">Дом</option>
            <option value="office">Офис</option>
            <option value="warehouse">Склад</option>
          </select>
        </div>
        <div class="field">
          <label>Количество комнат</label>
            <input class="input" type="number" v-model.number="form.rooms_count"
                   :disabled="isRoomsDisabled" :placeholder="isRoomsDisabled ? 'Не применяется' : ''" />
          </div>
          <div class="field">
            <label>Этаж / всего этажей</label>
            <div class="row property-form__floor-row">
            <input class="input" type="number" v-model.number="form.floor_number"
                   :disabled="isFloorDisabled" :placeholder="isFloorDisabled ? 'Не применяется' : 'Этаж'" />
            <input class="input" type="number" v-model.number="form.total_floors"
                   :disabled="isTotalFloorsDisabled" :placeholder="isTotalFloorsDisabled ? 'Не применяется' : 'Всего'" />
            </div>
            <div v-if="floorRestrictionHint" class="muted" style="font-size: 12px; margin-top: 4px">
              {{ floorRestrictionHint }}
            </div>
          </div>

        <div class="field">
          <label>Общая площадь, м²</label>
          <input class="input" type="number" step="0.01"
                 v-model.number="form.area_total" />
        </div>
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Локация</div>
          <h2 class="h3">Адрес</h2>
        </div>
        <div class="surface-head__caption">Подсказки адресов подставляются через DaData.</div>
      </div>
      <p class="muted">
        Начните вводить адрес — подсказки подгружаются из сервиса DaData.
        Выберите нужную строку, и поля будут заполнены автоматически.
      </p>
      <AddressAutocomplete
        v-model="addressQuery"
        label="Поиск по адресу"
        placeholder="Город, улица, дом, квартира…"
        @pick="onAddressPick"
      />
      <div v-if="addressPicked" class="row" style="gap: 12px; flex-wrap: wrap">
        <span class="tag tag--accent">{{ addressPicked.value }}</span>
        <span v-if="addressPicked.postal_code" class="tag">
          Индекс: {{ addressPicked.postal_code }}
        </span>
        <span v-if="addressPicked.geo_lat && addressPicked.geo_lon" class="tag">
          {{ addressPicked.geo_lat.toFixed(4) }}, {{ addressPicked.geo_lon.toFixed(4) }}
        </span>
      </div>
      <div v-else-if="existingAddress" class="muted">
        Текущий адрес: {{ existingAddress }}
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Медиа</div>
          <h2 class="h3">Фотографии</h2>
        </div>
        <div class="surface-head__caption">Можно загружать файлы и добавлять внешние ссылки на изображения.</div>
      </div>
      <p class="muted">
        После создания объекта карты со спутниковыми снимками подгружаются
        автоматически из 2GIS по указанному адресу. Вы также можете загрузить
        собственные фотографии или добавить ссылки на изображения — они
        сохранятся вместе с картами из 2GIS.
      </p>
      <div class="grid grid--3" v-if="photos.length">
        <div v-for="(p, i) in photos" :key="p.id || ('new-' + i)"
             class="photo-tile">
          <img :src="p.image_url || p.preview || p.url" alt="Фото объекта" />
          <div class="photo-tile__overlay">
            <label class="tag tag--panel" style="cursor: pointer">
              <input type="checkbox" v-model="p.is_cover"
                     @change="setCover(p)" style="display: none" />
              {{ p.is_cover ? 'Обложка' : 'Сделать обложкой' }}
            </label>
            <button class="btn btn--danger btn--sm" type="button"
                    @click="removePhoto(p, i)">
              Удалить
            </button>
          </div>
        </div>
      </div>
      <div v-else class="empty property-form__photos-empty">
        Фотографии пока не добавлены.
      </div>
      <div class="row property-form__photos-actions" style="gap: 12px; flex-wrap: wrap">
        <label class="btn btn--sm" style="cursor: pointer">
          Загрузить файл
          <input type="file" accept="image/*" multiple
                 style="display: none" @change="onFilesSelected" />
        </label>
        <div class="row property-form__photo-url" style="gap: 8px; flex: 1; min-width: 240px">
          <input class="input" v-model="newPhotoUrl"
                 placeholder="или вставьте ссылку на изображение" />
          <button class="btn btn--sm" type="button" @click="addPhotoByUrl">
            Добавить ссылку
          </button>
        </div>
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Контент карточки</div>
          <h2 class="h3">Описание</h2>
        </div>
        <div class="surface-head__caption">Текст используется в карточке объекта и в работе агента с клиентом.</div>
      </div>
      <div class="field">
        <label>Описание объекта</label>
        <textarea class="textarea" v-model="form.description" rows="5"
                  placeholder="Расскажите об объекте: состояние, инфраструктура, транспорт…">
        </textarea>
      </div>

      <div v-if="error" class="error">{{ error }}</div>
      <div class="row" style="justify-content: flex-end; gap: 8px">
        <button class="btn" type="button" @click="$router.back()">Отмена</button>
        <button class="btn btn--accent" :disabled="loading" type="submit">
          {{ loading ? 'Сохранение…' : (isEdit ? 'Сохранить' : 'Создать') }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import AddressAutocomplete from '../components/AddressAutocomplete.vue'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { extractError, useToastsStore } from '../store/toasts'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import {
  propertyTypeUsesFloor,
  propertyTypeUsesRooms,
  propertyTypeUsesTotalFloors,
} from '@/utils/propertyTypes'

const route = useRoute()
const router = useRouter()
const toasts = useToastsStore()
const isEdit = computed(() => !!route.params.id)

function defaultForm() {
  return {
    title: '', operation_type: 1, status: 1,
    premises_type: 'apartment',
    address: null,
    price: null, price_per_sqm: null,
    area_total: null,
    rooms_count: null, floor_number: null, total_floors: null,
    description: '',
  }
}

const form = reactive(defaultForm())

const dict = reactive({ operations: [] })
const addressQuery = ref('')
const addressPicked = ref(null)
const existingAddress = ref('')
const photos = ref([])
const pendingFiles = ref([])
const removedPhotoIds = ref([])
const newPhotoUrl = ref('')
const loading = ref(false)
const error = ref('')
const propertyBaseline = ref('')
const propertyDraftRestored = ref(false)
let initSeq = 0

const formModeLabel = computed(() => (
  isEdit.value ? 'Редактирование' : 'Создание'
))
const addressStateLabel = computed(() => {
  if (addressPicked.value) return 'Выбран'
  if (existingAddress.value) return 'Сохранён'
  return 'Не указан'
})
const selectedFeaturesCount = computed(() => 0)
const isRoomsDisabled = computed(() => !propertyTypeUsesRooms(form.premises_type))
const isFloorDisabled = computed(() => !propertyTypeUsesFloor(form.premises_type))
const isTotalFloorsDisabled = computed(() => !propertyTypeUsesTotalFloors(form.premises_type))
const floorRestrictionHint = computed(() => {
  if (form.premises_type === 'warehouse') return 'Для склада этажи и комнаты не указываются.'
  if (form.premises_type === 'house') return 'Для дома укажите только общее количество этажей.'
  return ''
})
const photoCount = computed(() => photos.value.length)
const coverCount = computed(() => photos.value.filter((photo) => photo.is_cover).length)
const propertyDirtySnapshot = computed(() => JSON.stringify(buildPropertyDirtyState()))
const isPropertyDirty = computed(() => propertyDirtySnapshot.value !== propertyBaseline.value)

function onAddressPick(r) {
  addressPicked.value = r
}

function onFilesSelected(e) {
  const files = Array.from(e.target.files || [])
  for (const file of files) {
    const preview = URL.createObjectURL(file)
    const photo = { file, preview, is_cover: false, _new: true }
    photos.value.push(photo)
    pendingFiles.value.push(photo)
  }
  e.target.value = ''
}

function addPhotoByUrl() {
  const u = newPhotoUrl.value.trim()
  if (!u) return
  photos.value.push({ url: u, image_url: u, is_cover: false, _new: true, _fromUrl: true })
  newPhotoUrl.value = ''
}

function setCover(target) {
  photos.value.forEach(p => { p.is_cover = (p === target) })
}

function revokePreview (photo) {
  if (photo?.preview?.startsWith('blob:')) {
    URL.revokeObjectURL(photo.preview)
  }
}

function removePhoto(p, index) {
  if (p.id) removedPhotoIds.value.push(p.id)
  pendingFiles.value = pendingFiles.value.filter((item) => item !== p)
  revokePreview(p)
  photos.value.splice(index, 1)
}

function buildPropertyDraftData() {
  return {
    form: { ...form },
    addressQuery: addressQuery.value,
    addressPicked: addressPicked.value,
    newPhotoUrl: newPhotoUrl.value,
    photoUrls: photos.value
      .filter((photo) => photo._new && photo._fromUrl && photo.url)
      .map((photo) => ({
        url: photo.url,
        is_cover: !!photo.is_cover,
      })),
  }
}

function buildPropertyDirtyState() {
  return {
    ...buildPropertyDraftData(),
    photos: photos.value.map((photo) => ({
      id: photo.id ?? null,
      url: photo.url || photo.image_url || null,
      is_cover: !!photo.is_cover,
      is_new: !!photo._new,
      file_name: photo.file?.name || null,
      file_size: photo.file?.size || null,
    })),
    removedPhotoIds: [...removedPhotoIds.value],
  }
}

function isPropertyDraftEmpty(draft) {
  const formData = draft?.form || {}
  const hasFormValue = Object.entries(formData)
    .filter(([key]) => !['operation_type', 'status', 'address'].includes(key))
    .some(([, value]) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== '' && value !== null && value !== undefined
    })

  return !(
    hasFormValue
    || !!draft?.addressQuery
    || !!draft?.addressPicked
    || !!draft?.newPhotoUrl
    || (draft?.photoUrls || []).length
  )
}

function formatPropertyValidationError(data) {
  const labels = {
    title: 'Название',
    operation_type: 'Тип операции',
    status: 'Статус',
    premises_type: 'Тип помещения',
    price: 'Цена',
    price_per_sqm: 'Цена за м²',
    area_total: 'Площадь',
    rooms_count: 'Количество комнат',
    floor_number: 'Этаж',
    total_floors: 'Количество этажей',
    address: 'Адрес',
  }

  if (!data || typeof data !== 'object') return ''
  const parts = []
  for (const [key, value] of Object.entries(data)) {
    const title = labels[key] || key
    const message = Array.isArray(value) ? value.filter(Boolean).join(' ') : String(value || '')
    if (message) parts.push(`${title}: ${message}`)
  }
  return parts.join(' ')
}

function applyPropertyDraft(draft) {
  Object.assign(form, defaultForm(), draft?.form || {})
  addressQuery.value = draft?.addressQuery || ''
  addressPicked.value = draft?.addressPicked || null
  newPhotoUrl.value = draft?.newPhotoUrl || ''
  photos.value.forEach(revokePreview)
  photos.value = (draft?.photoUrls || []).map((photo) => ({
    url: photo.url,
    image_url: photo.url,
    is_cover: !!photo.is_cover,
    _new: true,
    _fromUrl: true,
  }))
  pendingFiles.value = []
  removedPhotoIds.value = []
}

function syncPropertyBaseline() {
  propertyBaseline.value = propertyDirtySnapshot.value
}

function resetPropertyFormState () {
  Object.assign(form, defaultForm())
  addressQuery.value = ''
  addressPicked.value = null
  existingAddress.value = ''
  photos.value.forEach(revokePreview)
  photos.value = []
  pendingFiles.value = []
  removedPhotoIds.value = []
  newPhotoUrl.value = ''
  error.value = ''
  propertyDraftRestored.value = false
}

async function ensureOperationTypesLoaded () {
  if (dict.operations.length) return
  const { data } = await api.get('/operation-types/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  dict.operations = unpackPaginated(data).items
}

async function initializeForm () {
  const seq = ++initSeq
  loading.value = true
  resetPropertyFormState()

  try {
    await ensureOperationTypesLoaded()
    if (seq !== initSeq) return

    if (isEdit.value) {
      const { data } = await api.get(`/properties/${route.params.id}/`)
      if (seq !== initSeq) return
      Object.assign(form, {
        title: data.title,
        operation_type: data.operation_type,
        status: data.status,
        premises_type: data.premises_type || 'apartment',
        address: data.address,
        price: data.price,
        price_per_sqm: data.price_per_sqm,
        area_total: data.area_total,
        rooms_count: data.rooms_count,
        floor_number: data.floor_number,
        total_floors: data.total_floors,
        description: data.description,
      })
      existingAddress.value = data.full_address || ''
      photos.value = (data.photos || []).map((photo) => ({ ...photo }))
      syncPropertyBaseline()
    } else {
      syncPropertyBaseline()
    }
  } catch (e) {
    if (seq !== initSeq) return
    error.value = extractError(e, 'Failed to initialize property form.')
  } finally {
    if (seq === initSeq) {
      loading.value = false
    }
  }
}

const { clearDraft: clearPropertyDraft } = useDraftPersistence({
  key: 'property-form:create',
  enabled: () => !isEdit.value,
  getData: buildPropertyDraftData,
  applyData: (draft) => {
    propertyDraftRestored.value = true
    applyPropertyDraft(draft)
    toasts.info('Черновик объекта восстановлен')
  },
  isEmpty: isPropertyDraftEmpty,
})

useUnsavedChangesGuard({
  enabled: () => isPropertyDirty.value,
  isDirty: () => isPropertyDirty.value,
  message: 'Есть несохранённые изменения в карточке объекта. Покинуть страницу?',
})

async function uploadPhotos(propertyId) {
  for (const p of pendingFiles.value) {
    const fd = new FormData()
    fd.append('property', propertyId)
    fd.append('image', p.file)
    fd.append('is_cover', p.is_cover ? 'true' : 'false')
    await api.post('/property-photos/', fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  }
  pendingFiles.value = []

  for (const p of photos.value.filter(x => x._new && x._fromUrl)) {
    await api.post('/property-photos/', {
      property: propertyId,
      url: p.url,
      is_cover: p.is_cover,
    })
  }

  for (const id of removedPhotoIds.value) {
    await api.delete(`/property-photos/${id}/`)
  }
  removedPhotoIds.value = []

  const selectedExistingCover = photos.value.find((photo) => photo.is_cover && photo.id)
  if (selectedExistingCover) {
    await api.post(`/property-photos/${selectedExistingCover.id}/set_cover/`)
  }
}

async function submit() {
  loading.value = true; error.value = ''
  try {
    const payload = {
      title: form.title,
      operation_type: form.operation_type,
      status: form.status,
      premises_type: form.premises_type,
      price: form.price,
      price_per_sqm: form.price_per_sqm,
      area_total: form.area_total,
      rooms_count: isRoomsDisabled.value ? null : form.rooms_count,
      floor_number: isFloorDisabled.value ? null : form.floor_number,
      total_floors: isTotalFloorsDisabled.value ? null : form.total_floors,
      description: form.description,
    }
    if (addressPicked.value) {
      payload.address_data = addressPicked.value
    } else if (form.address) {
      payload.address = form.address
    } else if (!isEdit.value) {
      throw new Error('Выберите адрес из подсказок.')
    }

    const url = isEdit.value
      ? `/properties/${route.params.id}/` : '/properties/'
    const method = isEdit.value ? 'put' : 'post'
    const { data } = await api[method](url, payload)

    await uploadPhotos(data.id)
    clearPropertyDraft()
    syncPropertyBaseline()
    router.push(`/properties/${data.id}`)
  } catch (e) {
    error.value = extractError(e, 'Не удалось сохранить объект.')
    const data = e.response?.data
    if (typeof data === 'object' && data) {
      const formatted = formatPropertyValidationError(data)
      if (formatted) error.value = formatted
      else error.value = extractError(e, 'Не удалось сохранить объект.')
    } else {
      error.value = e.message || 'Не удалось сохранить объект.'
    }
  } finally {
    loading.value = false
  }
}

watch(() => `${route.name || ''}:${route.params.id || 'new'}`, () => {
  void initializeForm()
}, { immediate: true })
watch(() => form.premises_type, (value) => {
  if (!propertyTypeUsesRooms(value)) {
    form.rooms_count = null
  }
  if (!propertyTypeUsesFloor(value)) {
    form.floor_number = null
  }
  if (!propertyTypeUsesTotalFloors(value)) {
    form.total_floors = null
  }
})

onBeforeUnmount(() => {
  photos.value.forEach(revokePreview)
})
</script>

<style scoped>
.property-form-page {
  min-height: 0;
}

.property-form__section-head {
  margin-bottom: 2px;
}

.property-form__main-grid {
  gap: 16px;
}
.property-form__main-grid > .field > .select {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.16);
  color-scheme: light;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 10px 22px rgba(16, 55, 52, 0.08);
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
  padding-right: 42px;
}


.property-form__floor-row {
  gap: 10px;
}

.chip-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border-radius: var(--r-pill);
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  color: var(--c-ink-soft);
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease, background 0.3s ease, color 0.3s ease;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.chip-check:hover {
  transform: translateY(-2px);
  border-color: var(--c-border-strong);
  box-shadow: 0 10px 20px rgba(31, 163, 154, 0.08);
}

.chip-check input {
  accent-color: var(--c-accent);
}

.chip-check:has(input:checked) {
  background: linear-gradient(135deg, rgba(31, 163, 154, 0.18), rgba(99, 208, 197, 0.16));
  color: #effffd;
  border-color: rgba(99, 208, 197, 0.28);
  box-shadow: 0 0 18px rgba(99, 208, 197, 0.12);
}

.photo-tile {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: var(--shadow-1);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.photo-tile:hover {
  transform: translateY(-5px);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-glow);
}

.photo-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-tile__overlay {
  position: absolute;
  inset: auto 0 0 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px;
  background: linear-gradient(to top, rgba(7, 19, 29, 0.86), transparent);
}

.property-form__photos-empty {
  min-height: 140px;
}

.property-form__photos-actions {
  align-items: stretch;
}

.property-form__photo-url {
  width: 100%;
}

@media (max-width: 720px) {
  .property-form__floor-row,
  .property-form__photos-actions,
  .property-form__photo-url {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
