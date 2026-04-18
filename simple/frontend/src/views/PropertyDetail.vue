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

    <!-- Модальное окно подачи заявки клиентом -->
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

    <!-- Галерея фотографий -->
    <div class="panel panel--light">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <h2 class="h3">Фотографии</h2>
        <label v-if="auth.isStaff" class="btn btn--sm">
          Загрузить фото
          <input type="file" accept="image/*" multiple @change="uploadPhotos" hidden />
        </label>
      </div>
      <div v-if="property.photos?.length" class="gallery">
        <div v-for="ph in property.photos" :key="ph.id"
             class="gallery__item"
             :class="{ 'is-hidden': ph.is_hidden, 'is-cover': ph.is_cover }">
          <img :src="ph.image_url" :alt="property.title || 'Фото объекта'" />
          <div class="gallery__badges">
            <span v-if="ph.is_cover" class="gallery__badge is-cover">Обложка</span>
            <span v-if="ph.is_hidden" class="gallery__badge is-hidden">Скрыто</span>
          </div>
          <!-- Ручное управление альбомом: обложка, скрыть/показать, удалить.
               Доступно только сотрудникам. -->
          <div v-if="auth.isStaff" class="gallery__toolbar">
            <button class="gallery__btn"
                    :disabled="ph.is_cover"
                    :title="ph.is_cover ? 'Это текущая обложка' : 'Сделать обложкой'"
                    @click="setCover(ph)">★</button>
            <button class="gallery__btn"
                    :disabled="ph.is_cover"
                    :title="ph.is_hidden ? 'Показать клиенту' : 'Скрыть от клиента'"
                    @click="toggleHidden(ph)">
              {{ ph.is_hidden ? '◐' : '●' }}
            </button>
            <button class="gallery__btn gallery__btn--danger"
                    title="Удалить фото" @click="removePhoto(ph)">×</button>
          </div>
        </div>
      </div>
      <div v-else class="muted" style="margin-top: 8px">
        Фотографии ещё не загружены.
      </div>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light">
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
      <div class="row row--between">
        <h2 class="h3">Смена статуса объекта</h2>
      </div>
      <div class="row" style="gap: 10px; flex-wrap: wrap; margin-top: 12px">
        <button v-for="s in statuses" :key="s.id"
                class="btn btn--sm"
                :class="{ 'btn--primary': s.id === property.status }"
                @click="changeStatus(s.id)">
          {{ s.name }}
        </button>
      </div>
    </div>

    <div class="panel panel--light" v-if="history.length">
      <h2 class="h3">История изменений статуса</h2>
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
  </section>
  <div v-else class="empty">Загрузка объекта…</div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import InfoRow from '../components/InfoRow.vue'
import { useAuthStore } from '../store/auth'

const route = useRoute(); const router = useRouter()
const auth = useAuthStore()
const property = ref(null)
const statuses = ref([])
const history = ref([])

// --- подача заявки клиентом -------------------------------------------
const showRequestForm = ref(false)
const requestError = ref('')
const requestForm = reactive({ description: '' })

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
    api.get('/property-statuses/'),
    api.get(`/properties/${route.params.id}/history/`).catch(() => ({ data: [] })),
  ])
  property.value = p.data
  statuses.value = s.data.results || s.data
  history.value = h.data
}

async function changeStatus(id) {
  await api.post(`/properties/${route.params.id}/change_status/`,
                 { status_id: id })
  await load()
}

async function uploadPhotos(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  for (const file of files) {
    const fd = new FormData()
    fd.append('image', file)
    await api.post(`/properties/${route.params.id}/upload_photo/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }
  e.target.value = ''
  await load()
}

async function removePhoto(photo) {
  if (!confirm('Удалить фотографию?')) return
  await api.delete(`/property-photos/${photo.id}/`)
  await load()
}

// --- ручное управление альбомом ------------------------------------------
async function setCover (photo) {
  await api.post(`/property-photos/${photo.id}/set_cover/`)
  await load()
}

async function toggleHidden (photo) {
  try {
    await api.post(`/property-photos/${photo.id}/toggle_hidden/`)
    await load()
  } catch (err) {
    alert(err.response?.data?.detail || 'Не удалось изменить видимость.')
  }
}

async function remove() {
  if (!confirm('Удалить объект?')) return
  await api.delete(`/properties/${route.params.id}/`)
  router.push('/properties')
}

function formatMoney(v) { return new Intl.NumberFormat('ru-RU').format(v || 0) }

onMounted(load)
</script>

<style scoped>
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px; margin-top: 12px;
}
.gallery__item {
  position: relative; aspect-ratio: 4/3; overflow: hidden;
  border-radius: var(--r-sm); background: #f1f5f4;
}
.gallery__item img { width: 100%; height: 100%; object-fit: cover; display: block; }
.gallery__item.is-hidden img { filter: grayscale(.85) opacity(.5); }
.gallery__item.is-cover { outline: 3px solid var(--c-accent, #1fa39a); outline-offset: -3px; }

.gallery__badges {
  position: absolute; top: 6px; left: 6px;
  display: flex; gap: 4px; flex-wrap: wrap;
}
.gallery__badge {
  font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 999px;
  color: #fff; background: rgba(0,0,0,.55);
}
.gallery__badge.is-cover { background: var(--c-accent, #1fa39a); }
.gallery__badge.is-hidden { background: #7a6f68; }

.gallery__toolbar {
  position: absolute; top: 6px; right: 6px;
  display: flex; gap: 4px;
}
.gallery__btn {
  width: 26px; height: 26px; border-radius: 50%;
  border: none; background: rgba(0,0,0,.55); color: #fff;
  cursor: pointer; font-size: 14px; line-height: 1;
  display: grid; place-items: center;
}
.gallery__btn:hover:not(:disabled) { background: rgba(0,0,0,.78); }
.gallery__btn:disabled { opacity: .35; cursor: not-allowed; }
.gallery__btn--danger:hover:not(:disabled) { background: #9a3b32; }

.modal {
  position: fixed; inset: 0; z-index: 80;
  background: rgba(11, 37, 36, 0.55);
  display: grid; place-items: center;
  padding: 16px;
}
.modal__card {
  width: 100%; max-width: 520px;
  max-height: calc(100vh - 32px); overflow: auto;
}
</style>
