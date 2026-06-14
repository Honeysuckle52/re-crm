<template>
  <section class="stack moderation-page">
    <div class="hero moderation-hero">
      <div class="row row--between moderation-hero__row">
        <div>
          <div class="hero__eyebrow">Модерация</div>
          <h1 class="h2 moderation-hero__title">
            Подтверждение объектов клиентов
          </h1>
          <div class="moderation-hero__text">
            Позвоните владельцу, проверьте данные и только после этого выпустите объект
            в общий каталог.
          </div>
        </div>
        <router-link to="/properties" class="btn btn--ghost">К общему каталогу</router-link>
      </div>
    </div>

    <div class="panel panel--light moderation-shell">
      <div class="surface-head moderation-head">
        <div class="surface-head__meta">
          <h2 class="h3">Очередь</h2>
          <div class="muted">
            Показываются только объекты со статусом "На модерации".
            После одобрения объект станет виден всем пользователям.
          </div>
        </div>
        <span v-if="items.length" class="moderation-count">{{ items.length }} в проверке</span>
      </div>

      <div v-if="loading" class="empty">Загрузка...</div>
      <div v-else-if="items.length" class="grid grid--2 moderation-grid">
        <article v-for="item in items" :key="item.id" class="moderation-card">
          <div class="moderation-card__glow"></div>

          <div class="moderation-card__top">
            <div class="moderation-card__media">
              <img
                v-if="coverPhoto(item)"
                :src="coverPhoto(item)"
                :alt="item.title || `Объект ${item.id}`"
              >
              <div v-else class="moderation-card__placeholder">
                {{ premisesInitial(item.premises_type) }}
              </div>
            </div>

            <div class="moderation-card__intro">
              <div class="moderation-card__eyebrow">
                Объект #{{ item.id }}
                <span class="moderation-status">На модерации</span>
              </div>
              <h3 class="moderation-card__title">
                {{ item.title || `Объект ${item.id}` }}
              </h3>
              <div class="moderation-card__address">{{ item.full_address || 'Адрес не указан' }}</div>
            </div>
          </div>

          <div class="moderation-card__stats">
            <div class="moderation-stat">
              <span>Операция</span>
              <strong>{{ item.operation_type_name || '—' }}</strong>
            </div>
            <div class="moderation-stat">
              <span>Тип</span>
              <strong>{{ premisesLabel(item.premises_type) }}</strong>
            </div>
            <div class="moderation-stat">
              <span>Цена</span>
              <strong>{{ formatMoney(item.price) }}</strong>
            </div>
            <div class="moderation-stat">
              <span>Площадь</span>
              <strong>{{ item.area_total ? `${item.area_total} м²` : '—' }}</strong>
            </div>
          </div>

          <div class="moderation-description">
            <div class="moderation-description__label">Описание клиента</div>
            <p>{{ item.description || 'Описание не заполнено.' }}</p>
          </div>

          <div class="moderation-contact">
            <div class="moderation-contact__icon">☎</div>
            <div class="moderation-contact__body">
              <div class="moderation-contact__label">Контакт владельца</div>
              <div class="moderation-contact__name">{{ item.owner_username || 'Клиент не указан' }}</div>
              <div class="moderation-contact__links">
                <a v-if="item.owner_phone" :href="`tel:${item.owner_phone}`">{{ item.owner_phone }}</a>
                <span v-else>Телефон не указан</span>
                <a v-if="item.owner_email" :href="`mailto:${item.owner_email}`">{{ item.owner_email }}</a>
                <span v-else>Email не указан</span>
              </div>
            </div>
          </div>

          <div class="moderation-actions">
            <router-link class="btn btn--sm moderation-actions__details" :to="`/properties/${item.id}`">
              Открыть карточку
            </router-link>
            <button class="btn btn--primary btn--sm" :disabled="processingId === item.id" @click="approve(item)">
              Одобрить после звонка
            </button>
            <button class="btn btn--danger btn--sm" :disabled="processingId === item.id" @click="reject(item)">
              Отклонить
            </button>
          </div>
        </article>
      </div>
      <div v-else class="empty">Очередь пустая.</div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'
import { extractError, useToastsStore } from '../store/toasts'
import { propertyTypeLabel } from '@/utils/propertyTypes'

const toasts = useToastsStore()
const items = ref([])
const loading = ref(false)
const processingId = ref(null)

function premisesLabel(value) {
  return propertyTypeLabel(value) || value || '—'
}

function premisesInitial(value) {
  return premisesLabel(value).slice(0, 1).toUpperCase()
}

function coverPhoto(item) {
  const photos = Array.isArray(item.photos) ? item.photos : []
  return photos.find((photo) => photo.is_cover)?.image_url || photos[0]?.image_url || ''
}

function formatMoney(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(number)
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/properties/moderation/')
    items.value = Array.isArray(data) ? data : []
  } finally {
    loading.value = false
  }
}

async function approve(item) {
  processingId.value = item.id
  try {
    await api.post(`/properties/${item.id}/approve/`, {
      note: 'Менеджер подтвердил объект после звонка клиенту.',
    })
    toasts.success(`Объект ${item.id} одобрен и опубликован`)
    await load()
  } catch (e) {
    toasts.error(extractError(e, 'Не удалось одобрить объект'))
  } finally {
    processingId.value = null
  }
}

async function reject(item) {
  processingId.value = item.id
  try {
    await api.post(`/properties/${item.id}/reject/`, {
      note: 'Менеджер отклонил объект после проверки.',
    })
    toasts.info(`Объект ${item.id} отклонён`)
    await load()
  } catch (e) {
    toasts.error(extractError(e, 'Не удалось отклонить объект'))
  } finally {
    processingId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.moderation-page {
  background: transparent;
}

.moderation-hero {
  padding: 24px 28px;
}

.moderation-hero__row {
  flex-wrap: wrap;
  gap: 12px;
}

.moderation-hero__title {
  color: #fff;
  margin-top: 8px;
}

.moderation-hero__text {
  color: rgba(255,255,255,.75);
  font-size: 14px;
  margin-top: 6px;
  max-width: 760px;
}

.moderation-shell {
  background: var(--grad-card-soft);
  color: var(--c-text);
}

.moderation-head {
  align-items: flex-start;
  gap: 16px;
}

.moderation-count,
.moderation-status {
  align-items: center;
  background: rgba(120, 216, 206, .12);
  border: 1px solid rgba(120, 216, 206, .22);
  border-radius: var(--r-pill);
  color: #efffff;
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
  padding: 7px 12px;
  white-space: nowrap;
}

.moderation-grid {
  margin-top: 18px;
}

.moderation-card {
  background: var(--grad-card);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-1);
  color: var(--c-text);
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  padding: 18px;
  position: relative;
  transition: background .3s ease, box-shadow .3s ease, transform .3s ease;
}

.moderation-card:hover {
  background: var(--grad-card-soft);
  box-shadow: var(--shadow-glow-strong);
  transform: translateY(-3px);
}

.moderation-card::before,
.moderation-card__glow {
  display: none;
}

.moderation-card__top {
  display: grid;
  gap: 16px;
  grid-template-columns: 104px 1fr;
  position: relative;
  z-index: 1;
}

.moderation-card__media {
  aspect-ratio: 1;
  background: linear-gradient(180deg, rgba(255,255,255,.12), rgba(255,255,255,.06));
  border: 1px solid rgba(120, 216, 206, .18);
  border-radius: var(--r-sm);
  color: #efffff;
  display: grid;
  font-size: 36px;
  font-weight: 800;
  overflow: hidden;
  place-items: center;
}

.moderation-card__media img {
  height: 100%;
  object-fit: cover;
  width: 100%;
}

.moderation-card__intro {
  min-width: 0;
}

.moderation-card__eyebrow {
  align-items: center;
  color: var(--c-ink-soft);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 700;
  gap: 8px;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.moderation-status {
  letter-spacing: 0;
  padding: 5px 10px;
  text-transform: none;
}

.moderation-card__title {
  color: var(--c-text);
  font-size: clamp(20px, 2vw, 24px);
  line-height: 1.2;
  margin: 10px 0 8px;
}

.moderation-card__address {
  color: var(--c-ink-soft);
  font-size: 14px;
  line-height: 1.45;
}

.moderation-card__stats {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.moderation-stat,
.moderation-description,
.moderation-contact {
  background: rgba(255, 255, 255, .06);
  border: 1px solid rgba(120, 216, 206, .16);
  border-radius: var(--r-sm);
}

.moderation-stat {
  padding: 12px;
}

.moderation-stat span,
.moderation-description__label,
.moderation-contact__label {
  color: var(--c-muted);
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.moderation-stat strong {
  color: var(--c-text);
  display: block;
  font-size: 14px;
  margin-top: 5px;
}

.moderation-description {
  padding: 14px 16px;
}

.moderation-description p {
  color: var(--c-ink-soft);
  line-height: 1.55;
  margin: 8px 0 0;
}

.moderation-contact {
  align-items: center;
  display: grid;
  gap: 14px;
  grid-template-columns: 44px 1fr;
  padding: 14px;
}

.moderation-contact__icon {
  align-items: center;
  background: rgba(120, 216, 206, .14);
  border: 1px solid rgba(120, 216, 206, .22);
  border-radius: 16px;
  color: #efffff;
  display: flex;
  font-size: 20px;
  height: 44px;
  justify-content: center;
  width: 44px;
}

.moderation-contact__name {
  color: var(--c-text);
  font-weight: 800;
  margin-top: 4px;
}

.moderation-contact__links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 6px;
}

.moderation-contact__links a,
.moderation-contact__links span {
  color: var(--c-accent-2);
  font-size: 13px;
  font-weight: 700;
}

.moderation-actions {
  align-items: center;
  border-top: 1px solid rgba(120, 216, 206, .16);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 16px;
}

.moderation-actions__details {
  margin-right: auto;
}

@media (max-width: 920px) {
  .moderation-card__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .moderation-card {
    border-radius: var(--r-sm);
    padding: 14px;
  }

  .moderation-card__top,
  .moderation-card__stats,
  .moderation-contact {
    grid-template-columns: 1fr;
  }

  .moderation-card__media {
    max-height: 180px;
  }

  .moderation-contact__icon {
    display: none;
  }

  .moderation-actions .btn {
    width: 100%;
  }

  .moderation-actions__details {
    margin-right: 0;
  }
}
</style>
