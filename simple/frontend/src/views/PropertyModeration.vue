<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Модерация</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            Объекты клиентов на проверке
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Новые объекты клиентов сначала попадают сюда, а потом в общий каталог.
          </div>
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head">
        <div class="surface-head__meta">
          <h2 class="h3">Очередь</h2>
          <div class="muted">Показываются только объекты со статусом "На модерации".</div>
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
          </div>
          <div class="stack">
            <div><b>Тип:</b> {{ item.operation_type_name }}</div>
            <div><b>Помещение:</b> {{ item.premises_type }}</div>
            <div><b>Владелец:</b> {{ item.owner_username || '—' }}</div>
            <div><b>Цена:</b> {{ item.price }}</div>
          </div>
          <div class="row" style="gap: 8px; flex-wrap: wrap">
            <button class="btn btn--primary btn--sm" @click="approve(item)">Одобрить</button>
            <button class="btn btn--danger btn--sm" @click="archive(item)">Отклонить</button>
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
import { useToastsStore } from '../store/toasts'

const toasts = useToastsStore()
const items = ref([])
const loading = ref(false)
const statuses = ref({})

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
  await api.post(`/properties/${item.id}/change_status/`, { status_id: item.allowed_status_ids?.[0] })
  toasts.success(`Объект ${item.id} отправлен в работу`)
  await load()
}

async function archive(item) {
  await api.post(`/properties/${item.id}/change_status/`, { status_id: item.allowed_status_ids?.find((id) => id) })
  toasts.info(`Объект ${item.id} обработан`)
  await load()
}

onMounted(load)
</script>
