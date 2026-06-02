<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Модерация</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            Подтверждение объектов клиентов
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Позвоните владельцу, проверьте данные и только после этого выпустите объект в общий каталог.
          </div>
        </div>
        <router-link to="/properties" class="btn btn--ghost">К общему каталогу</router-link>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Очередь</h2>
          <div class="muted">
            Показываются только объекты со статусом "На модерации".
            После одобрения объект станет виден всем пользователям.
          </div>
        </div>
      </div>

      <div v-if="loading" class="empty">Загрузка…</div>
      <div v-else-if="items.length" class="grid grid--2">
        <article v-for="item in items" :key="item.id" class="panel panel--light stack">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h3">{{ item.title || `Объект ${item.id}` }}</h3>
              <div class="muted">{{ item.full_address }}</div>
            </div>
            <span class="tag">На модерации</span>
          </div>
          <div class="stack">
            <div><b>Тип:</b> {{ item.operation_type_name }}</div>
            <div><b>Помещение:</b> {{ premisesLabel(item.premises_type) }}</div>
            <div><b>Цена:</b> {{ formatMoney(item.price) }}</div>
            <div><b>Площадь:</b> {{ item.area_total || '—' }} м²</div>
            <div><b>Описание:</b> {{ item.description || '—' }}</div>
          </div>
          <div class="panel panel--light moderation-contact">
            <div class="surface-head__meta">Контакт владельца</div>
            <div><b>Клиент:</b> {{ item.owner_username || '—' }}</div>
            <div><b>Телефон:</b> <a v-if="item.owner_phone" :href="`tel:${item.owner_phone}`">{{ item.owner_phone }}</a><span v-else>—</span></div>
            <div><b>Email:</b> <a v-if="item.owner_email" :href="`mailto:${item.owner_email}`">{{ item.owner_email }}</a><span v-else>—</span></div>
          </div>
          <div class="row" style="gap: 8px; flex-wrap: wrap">
            <router-link class="btn btn--sm" :to="`/properties/${item.id}`">Открыть карточку</router-link>
            <button class="btn btn--primary btn--sm" :disabled="processingId === item.id" @click="approve(item)">
              Одобрить после звонка
            </button>
            <button class="btn btn--danger btn--sm" :disabled="processingId === item.id" @click="reject(item)">
              Отклонить
            </button>
          </div>
        </article>
      </div>
      <div v-else class="empty">Очередь пуста.</div>
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
.moderation-contact {
  padding: 12px;
}
</style>
