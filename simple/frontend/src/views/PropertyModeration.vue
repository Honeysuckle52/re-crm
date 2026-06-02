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

const toasts = useToastsStore()
const items = ref([])
const loading = ref(false)
const processingId = ref(null)

const premisesLabels = {
  apartment: 'Квартира',
  house: 'Дом',
  office: 'Офис',
  warehouse: 'Склад',
}

function premisesLabel(value) {
  return premisesLabels[value] || value || '—'
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
  background:
    radial-gradient(circle at top right, rgba(120, 216, 206, .16), transparent 32%),
    var(--grad-card-soft);
  color: var(--c-text);
  overflow: hidden;
}

.moderation-shell .muted {
  color: var(--c-ink-soft);
}

.moderation-head {
  align-items: flex-start;
  gap: 16px;
}

.moderation-count {
  border: 1px solid rgba(15, 23, 42, .12);
  border-radius: 999px;
  color: #1f2937;
  font-size: 12px;
  font-weight: 800;
  padding: 8px 12px;
  white-space: nowrap;
}

.moderation-grid {
  margin-top: 18px;
}

.moderation-card {
  background:
    radial-gradient(circle at 88% 8%, rgba(120, 216, 206, .18), transparent 34%),
    linear-gradient(145deg, #124346 0%, #0d3b3e 52%, #073434 100%);
  border: 1px solid rgba(120, 216, 206, .24);
  border-radius: 28px;
  box-shadow: 0 22px 60px rgba(15, 23, 42, .10);
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: hidden;
  padding: 18px;
  position: relative;
}

.moderation-card::before {
  background: linear-gradient(90deg, #f59e0b, #14b8a6, #2563eb);
  content: "";
  height: 5px;
  inset: 0 0 auto;
  position: absolute;
}

.moderation-card__glow {
  background: rgba(20, 184, 166, .10);
  border-radius: 999px;
  filter: blur(18px);
  height: 100px;
  position: absolute;
  right: -35px;
  top: 46px;
  width: 100px;
}

.moderation-card__top {
  display: grid;
  gap: 16px;
  grid-template-columns: 112px 1fr;
  position: relative;
  z-index: 1;
}

.moderation-card__media {
  aspect-ratio: 1;
  background: linear-gradient(135deg, #0f172a, #334155);
  border-radius: 22px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .2);
  color: #fff;
  display: grid;
  font-size: 40px;
  font-weight: 900;
  overflow: hidden;
  place-items: center;
}

.moderation-card__media img {
  height: 100%;
  object-fit: cover;
  width: 100%;
}

.moderation-card__placeholder {
  opacity: .9;
}

.moderation-card__intro {
  min-width: 0;
}

.moderation-card__eyebrow {
  align-items: center;
  color: rgba(234, 245, 243, .72);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 800;
  gap: 8px;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.moderation-status {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 999px;
  color: #c2410c;
  letter-spacing: 0;
  padding: 4px 9px;
  text-transform: none;
}

.moderation-card__title {
  color: #fff;
  font-size: clamp(20px, 2vw, 26px);
  line-height: 1.05;
  margin: 10px 0 8px;
}

.moderation-card__address {
  color: rgba(234, 245, 243, .78);
  font-size: 14px;
  line-height: 1.45;
}

.moderation-card__stats {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.moderation-stat {
  background: rgba(255, 255, 255, .10);
  border: 1px solid rgba(120, 216, 206, .18);
  border-radius: 18px;
  padding: 12px;
}

.moderation-stat span,
.moderation-description__label,
.moderation-contact__label {
  color: rgba(234, 245, 243, .70);
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.moderation-stat strong {
  color: #fff;
  display: block;
  font-size: 14px;
  margin-top: 5px;
}

.moderation-description {
  background: rgba(255, 255, 255, .08);
  border: 1px dashed rgba(120, 216, 206, .30);
  border-radius: 20px;
  padding: 14px 16px;
}

.moderation-description p {
  color: rgba(244, 251, 250, .86);
  line-height: 1.55;
  margin: 8px 0 0;
}

.moderation-contact {
  align-items: center;
  background: rgba(255, 255, 255, .10);
  border: 1px solid rgba(120, 216, 206, .22);
  border-radius: 22px;
  display: grid;
  gap: 14px;
  grid-template-columns: 44px 1fr;
  padding: 14px;
}

.moderation-contact__icon {
  align-items: center;
  background: #0f766e;
  border-radius: 16px;
  color: #fff;
  display: flex;
  font-size: 20px;
  height: 44px;
  justify-content: center;
  width: 44px;
}

.moderation-contact__name {
  color: #fff;
  font-weight: 900;
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
  color: #78d8ce;
  font-size: 13px;
  font-weight: 700;
}

.moderation-actions {
  align-items: center;
  border-top: 1px solid rgba(120, 216, 206, .20);
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
    border-radius: 22px;
    padding: 14px;
  }

  .moderation-card__top {
    grid-template-columns: 1fr;
  }

  .moderation-card__media {
    max-height: 180px;
  }

  .moderation-card__stats,
  .moderation-contact {
    grid-template-columns: 1fr;
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
