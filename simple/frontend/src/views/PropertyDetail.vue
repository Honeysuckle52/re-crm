<template>
  <section class="stack" v-if="property">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">{{ property.operation_type_name }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ property.title || 'Объект №' + property.id }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 4px">
            {{ property.full_address }}
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button v-if="!auth.isStaff"
                  class="btn btn--accent"
                  @click="showRequestForm = true">
            Оставить заявку
          </button>
          <router-link v-if="auth.isStaff"
                       :to="`/properties/${property.id}/edit`" class="btn btn--sm">
            Редактировать
          </router-link>
          <button v-if="auth.isStaff" class="btn btn--danger btn--sm"
                  @click="remove">Удалить</button>
        </div>
      </div>
    </div>

    <div v-if="false" class="kpi-strip">
      <article class="kpi-card">
        <span class="kpi-card__label">Статус</span>
        <strong class="kpi-card__value">{{ property.status_name || '—' }}</strong>
        <span class="kpi-card__meta">{{ property.operation_type_name || 'Тип операции не указан' }}</span>
      </article>
      <article class="kpi-card">
        <span class="kpi-card__label">Стоимость</span>
        <strong class="kpi-card__value">{{ priceLabel }}</strong>
        <span class="kpi-card__meta">
          {{ property.area_total ? property.area_total + ' м² общая площадь' : 'Площадь не указана' }}
        </span>
      </article>
      <article class="kpi-card">
        <span class="kpi-card__label">Фотографии</span>
        <strong class="kpi-card__value">{{ photosCount }}</strong>
        <span class="kpi-card__meta">Видимых: {{ visiblePhotosCount }}</span>
      </article>
      <article class="kpi-card kpi-card--accent">
        <span class="kpi-card__label">История</span>
        <strong class="kpi-card__value">{{ historyCount }}</strong>
        <span class="kpi-card__meta">Характеристик: {{ featuresCount }}</span>
      </article>
    </div>

    <div v-if="showRequestForm" class="modal" role="dialog"
         @click.self="showRequestForm = false">
      <form class="panel panel--light stack modal__card"
            @submit.prevent="submitRequest">
        <div class="row row--between">
          <h2 class="h3">Заявка на объект</h2>
          <button type="button" class="btn btn--sm btn--ghost"
                  style="color: var(--c-ink)"
                  @click="showRequestForm = false">×</button>
        </div>
        <div class="muted">
          Объект: <b>{{ property.title || 'Объект №' + property.id }}</b>.
          Агент свяжется с вами после получения заявки.
        </div>
        <div class="field">
          <label>Пожелания / комментарий</label>
          <textarea class="textarea" v-model="requestForm.description" rows="4"
                    placeholder="Удобное время для связи, условия осмотра и т. д.">
          </textarea>
        </div>
        <div v-if="requestError" class="error">{{ requestError }}</div>
        <div class="row" style="justify-content: flex-end; gap: 8px">
          <button type="button" class="btn btn--sm"
                  @click="showRequestForm = false">Отмена</button>
          <button type="submit" class="btn btn--accent">Отправить заявку</button>
        </div>
      </form>
    </div>

    <div class="panel panel--light">
      <div class="surface-head property-surface-head">
        <div>
          <div class="surface-head__meta">Медиа</div>
          <h2 class="h3">Фотографии</h2>
        </div>
        <label v-if="auth.isStaff" class="btn btn--sm">
          Загрузить фото
          <input type="file" accept="image/*" multiple @change="uploadPhotos" hidden />
        </label>
      </div>
      <div v-if="property.photos?.length" class="gallery">
        <div v-for="(ph, idx) in property.photos" :key="ph.id"
             class="gallery__item"
             :class="{ 'is-hidden': ph.is_hidden, 'is-cover': ph.is_cover }">
          <img :src="ph.image_url" :alt="property.title || 'Фото объекта'"
               class="gallery__img"
               @click="openLightbox(idx)" />
          <div class="gallery__badges">
            <span v-if="ph.is_cover" class="gallery__badge is-cover">Обложка</span>
            <span v-if="ph.is_hidden" class="gallery__badge is-hidden">Скрыто</span>
          </div>
          <div v-if="auth.isStaff" class="gallery__toolbar">
            <!-- Обложка -->
            <button class="gallery__btn"
                    :class="{ 'gallery__btn--active': ph.is_cover }"
                    :disabled="ph.is_cover"
                    :title="ph.is_cover ? 'Это текущая обложка' : 'Сделать обложкой'"
                    @click.stop="setCover(ph)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l2.9 6.26 6.77.54-5.19 4.4 1.71 6.63L12 16.5l-6.19 3.33 1.71-6.63L2.33 8.8l6.77-.54z"/>
              </svg>
            </button>
            <!-- Видимость -->
            <button class="gallery__btn"
                    :disabled="ph.is_cover"
                    :title="ph.is_hidden ? 'Показать клиенту' : 'Скрыть от клиента'"
                    @click.stop="toggleHidden(ph)">
              <svg v-if="!ph.is_hidden" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            </button>
            <!-- Удалить -->
            <button class="gallery__btn gallery__btn--danger"
                    title="Удалить фото"
                    @click.stop="removePhoto(ph)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
      <div v-if="!property.photos?.length" class="muted" style="margin-top: 8px">
        Фотографии ещё не загружены.
      </div>
    </div>

    <!-- Lightbox -->
    <Teleport to="body">
      <Transition name="lb">
        <div v-if="lightbox.open"
             class="lb-backdrop"
             @click.self="closeLightbox"
             tabindex="-1"
             ref="lbEl">
          <div class="lb-modal">
            <div class="lb-modal__header">
              <span class="lb-modal__counter">{{ lightbox.index + 1 }} / {{ property.photos.length }}</span>
              <button class="lb-close" @click="closeLightbox" title="Закрыть">✕</button>
            </div>
            <div class="lb-modal__body">
              <img :src="property.photos[lightbox.index]?.image_url"
                   :alt="property.title || 'Фото объекта'"
                   class="lb-img"
                   draggable="false" />
            </div>
            <div v-if="property.photos.length > 1" class="lb-modal__footer">
              <button class="lb-nav" @click="lightboxPrev" title="Предыдущее">&#8592;</button>
              <button class="lb-nav" @click="lightboxNext" title="Следующее">&#8594;</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <div class="grid grid--2">
      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Карточка объекта</div>
          <div class="surface-head__caption">{{ property.status_name }}</div>
        </div>
        <h2 class="h3">Параметры</h2>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Стоимость"        :value="formatMoney(property.price) + ' ₽'" />
          <InfoRow label="Стоимость за м²"  :value="property.price_per_sqm
                                                  ? formatMoney(property.price_per_sqm) + ' ₽' : '—'" />
          <InfoRow label="Общая площадь"    :value="property.area_total ? property.area_total + ' м²' : '—'" />
          <InfoRow label="Жилая площадь"    :value="property.area_living ? property.area_living + ' м²' : '—'" />
          <InfoRow label="Площадь кухни"    :value="property.area_kitchen ? property.area_kitchen + ' м²' : '—'" />
          <InfoRow label="Количество комнат":value="property.rooms_count || '—'" />
          <InfoRow label="Этаж / всего"     :value="(property.floor_number || '—') + ' / ' + (property.total_floors || '—')" />
          <InfoRow label="Статус"           :value="property.status_name" />
        </div>
      </div>

      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Описание и теги</div>
          <div class="surface-head__caption">Характеристик: {{ featuresCount }}</div>
        </div>
        <h2 class="h3">Описание</h2>
        <p style="white-space: pre-wrap">{{ property.description || 'Описание не заполнено.' }}</p>
        <h2 class="h3" style="margin-top: 16px">Характеристики</h2>
        <div v-if="property.feature_values?.length" class="row" style="flex-wrap: wrap; gap: 6px">
          <span v-for="fv in property.feature_values" :key="fv.feature"
                class="tag tag--accent">
            {{ fv.feature_name }}{{ fv.value ? ': ' + fv.value : '' }}
          </span>
        </div>
        <div v-else class="muted">Характеристики не заданы.</div>
      </div>
    </div>

    <div v-if="auth.isStaff" class="panel panel--light">
      <div class="surface-head property-surface-head">
        <div class="surface-head__meta">Управление</div>
        <div class="surface-head__caption">{{ property.status_name }}</div>
      </div>
      <div class="row row--between">
        <h2 class="h3">Смена статуса объекта</h2>
      </div>
      <div class="row property-status-actions" style="gap: 10px; flex-wrap: wrap; margin-top: 12px">
        <button v-for="s in allowedStatuses" :key="s.id"
                class="btn btn--sm"
                :class="{ 'btn--primary': s.id === property.status }"
                :disabled="s.id === property.status"
                @click="changeStatus(s.id)">
          {{ s.name }}
        </button>
      </div>
    </div>

    <div class="panel panel--light" v-if="history.length">
      <div class="surface-head property-surface-head">
        <div class="surface-head__meta">Журнал изменений</div>
        <div class="surface-head__caption">{{ historyCount }} записей</div>
      </div>
      <h2 class="h3">История изменений статуса</h2>
      <div class="table-wrap property-history-table">
        <table class="table">
          <thead><tr><th>Дата</th><th>Статус</th><th>Сотрудник</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td>{{ new Date(h.changed_at).toLocaleString('ru-RU') }}</td>
              <td>{{ h.status_name }}</td>
              <td>{{ h.changed_by_username }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <AuditLogPanel
      v-if="auth.isStaff && property"
      :params="{ property: property.id }"
      title="История объекта"
      caption="Журнал действий"
      empty-text="По объекту ещё нет записей журнала."
      :page-size="12"
    />
  </section>
  <div v-else class="empty">Загрузка объекта…</div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import AuditLogPanel from '../components/AuditLogPanel.vue'
import InfoRow from '../components/InfoRow.vue'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney as fmtMoney } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const route = useRoute(); const router = useRouter()
const auth = useAuthStore()
const confirm = useConfirmStore()
const toasts = useToastsStore()
const property = ref(null)
const statuses = ref([])
const history = ref([])

// Lightbox
const lbEl = ref(null)
const lightbox = reactive({ open: false, index: 0 })

function openLightbox (idx) {
  lightbox.index = idx
  lightbox.open = true
  nextTick(() => lbEl.value?.focus())
}
function closeLightbox () { lightbox.open = false }
function lightboxPrev () {
  lightbox.index = (lightbox.index - 1 + (property.value?.photos?.length || 1)) % (property.value?.photos?.length || 1)
}
function lightboxNext () {
  lightbox.index = (lightbox.index + 1) % (property.value?.photos?.length || 1)
}
function onKeydown (e) {
  if (!lightbox.open) return
  if (e.key === 'ArrowLeft') lightboxPrev()
  else if (e.key === 'ArrowRight') lightboxNext()
  else if (e.key === 'Escape') closeLightbox()
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const showRequestForm = ref(false)
const requestError = ref('')
const requestForm = reactive({ description: '' })

const photosCount = computed(() => property.value?.photos?.length || 0)
const visiblePhotosCount = computed(() => (
  property.value?.photos?.filter((photo) => !photo.is_hidden).length || 0
))
const featuresCount = computed(() => property.value?.feature_values?.length || 0)
const historyCount = computed(() => history.value.length)
const priceLabel = computed(() => (
  property.value?.price ? `${formatMoney(property.value.price)} ₽` : '—'
))
const allowedStatuses = computed(() => {
  const allowedIds = new Set(property.value?.allowed_status_ids || [])
  return statuses.value.filter((status) => allowedIds.has(status.id))
})

async function submitRequest () {
  requestError.value = ''
  try {
    await api.post('/requests/', {
      operation_type: property.value.operation_type,
      property: property.value.id,
      description: requestForm.description,
    })
    showRequestForm.value = false
    requestForm.description = ''
    router.push('/requests')
  } catch (err) {
    requestError.value = err.response?.data
      ? Object.values(err.response.data).flat().join(' ')
      : 'Не удалось отправить заявку.'
  }
}

async function load() {
  const [p, s, h] = await Promise.all([
    api.get(`/properties/${route.params.id}/`),
    api.get('/property-statuses/', {
      params: { page_size: LOOKUP_PAGE_SIZE },
    }),
    api.get(`/properties/${route.params.id}/history/`).catch(() => ({ data: [] })),
  ])
  property.value = p.data
  statuses.value = unpackPaginated(s.data).items
  history.value = h.data
}

async function changeStatus(id) {
  try {
    await api.post(`/properties/${route.params.id}/change_status/`,
                   { status_id: id })
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить статус объекта'))
  }
}

async function uploadPhotos(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  let uploaded = false
  try {
    for (const file of files) {
      const fd = new FormData()
      fd.append('image', file)
      await api.post(`/properties/${route.params.id}/upload_photo/`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      uploaded = true
    }
    await load()
  } catch (err) {
    if (uploaded) await load()
    toasts.error(extractError(
      err,
      uploaded
        ? 'Часть фотографий загружена, но операция завершилась с ошибкой'
        : 'Не удалось загрузить фотографии',
    ))
  } finally {
    e.target.value = ''
  }
}

async function removePhoto(photo) {
  const approved = await confirm.ask({
    title: 'Удаление фотографии',
    message: 'Удалить фотографию?',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  try {
    await api.delete(`/property-photos/${photo.id}/`)
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось удалить фотографию'))
  }
}

async function setCover (photo) {
  try {
    await api.post(`/property-photos/${photo.id}/set_cover/`)
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось установить обложку'))
  }
}

async function toggleHidden (photo) {
  try {
    await api.post(`/property-photos/${photo.id}/toggle_hidden/`)
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить видимость'))
  }
}

async function remove() {
  const approved = await confirm.ask({
    title: 'Удаление объекта',
    message: 'Вы уверены, что хотите удалить этот объект? Удаление невозможно, если к объекту привязаны заявки, сделки или просмотры.',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  try {
    await api.delete(`/properties/${route.params.id}/`)
    router.push('/properties')
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось удалить объект'))
  }
}

function formatMoney (v) { return fmtMoney(v, '0') }

onMounted(load)
</script>

<style scoped>
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.gallery__item {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-1);
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease;
}

.gallery__item:hover {
  transform: translateY(-5px);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-glow);
  border-color: var(--c-border-strong);
}

.gallery__item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.gallery__img {
  cursor: zoom-in;
  transition: transform 0.25s ease;
}

.gallery__item:hover .gallery__img {
  transform: scale(1.04);
}

/* ---- Lightbox ---- */
.lb-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(4, 12, 20, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  outline: none;
}

.lb-modal {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(80vw, 960px);
  max-height: 85vh;
  background: rgba(10, 24, 38, 0.88);
  border: 1px solid var(--c-border-strong, rgba(255,255,255,0.12));
  border-radius: 24px;
  box-shadow: 0 40px 120px rgba(0, 0, 0, 0.65);
  overflow: hidden;
}

.lb-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.lb-modal__counter {
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.4px;
}

.lb-modal__body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0;
}

.lb-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  user-select: none;
}

.lb-close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.lb-close:hover {
  background: rgba(255, 111, 134, 0.22);
  color: #fff;
  transform: rotate(90deg);
}

.lb-modal__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.lb-nav {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.lb-nav:hover {
  background: rgba(31, 163, 154, 0.22);
  color: #fff;
}

/* Transition */
.lb-enter-active,
.lb-leave-active {
  transition: opacity 0.2s ease;
}
.lb-enter-active .lb-modal,
.lb-leave-active .lb-modal {
  transition: transform 0.2s ease;
}
.lb-enter-from,
.lb-leave-to {
  opacity: 0;
}
.lb-enter-from .lb-modal {
  transform: scale(0.95) translateY(8px);
}
.lb-leave-to .lb-modal {
  transform: scale(0.95) translateY(8px);
}

.gallery__item.is-hidden img {
  filter: grayscale(0.85) opacity(0.42);
}

.gallery__item.is-cover {
  box-shadow: 0 0 0 2px rgba(99, 208, 197, 0.28), var(--shadow-glow);
}

.gallery__badges {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.gallery__badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(7, 19, 29, 0.64);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.gallery__badge.is-cover {
  border-color: rgba(99, 208, 197, 0.24);
  background: rgba(99, 208, 197, 0.18);
  color: #f0fffc;
}

.gallery__badge.is-hidden {
  border-color: rgba(255, 111, 134, 0.18);
  background: rgba(255, 111, 134, 0.14);
  color: #ffd7df;
}

.gallery__toolbar {
  position: absolute;
  bottom: 10px;
  right: 10px;
  display: flex;
  gap: 5px;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.gallery__item:hover .gallery__toolbar {
  opacity: 1;
  transform: translateY(0);
}

.gallery__btn {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(7, 19, 29, 0.72);
  color: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.gallery__btn:hover:not(:disabled) {
  background: rgba(31, 163, 154, 0.28);
  border-color: rgba(31, 163, 154, 0.3);
  color: #fff;
}

.gallery__btn--active {
  background: rgba(99, 208, 197, 0.2);
  border-color: rgba(99, 208, 197, 0.3);
  color: #63d0c5;
}

.gallery__btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.gallery__btn--danger:hover:not(:disabled) {
  background: rgba(255, 111, 134, 0.28);
  border-color: rgba(255, 111, 134, 0.3);
  color: #fff;
}

.modal {
  z-index: 80;
}

.modal__card {
  width: 100%;
  max-width: 520px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}

.property-surface-head {
  margin-bottom: 12px;
}

.property-status-actions {
  margin-top: 14px !important;
}

.property-history-table .table {
  min-width: 560px;
}
</style>
