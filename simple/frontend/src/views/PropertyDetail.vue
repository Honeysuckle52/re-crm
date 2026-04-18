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
        <div class="row" style="gap: 8px">
          <router-link :to="`/properties/${property.id}/edit`" class="btn btn--sm">
            Редактировать
          </router-link>
          <button class="btn btn--danger btn--sm" @click="remove">Удалить</button>
        </div>
      </div>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light">
        <h2 class="h3">Параметры</h2>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Цена"          :value="formatMoney(property.price) + ' ₽'" />
          <InfoRow label="Цена за м²"    :value="property.price_per_sqm
                                                  ? formatMoney(property.price_per_sqm) + ' ₽' : '—'" />
          <InfoRow label="Общая площадь" :value="property.area_total ? property.area_total + ' м²' : '—'" />
          <InfoRow label="Жилая площадь" :value="property.area_living ? property.area_living + ' м²' : '—'" />
          <InfoRow label="Кухня"         :value="property.area_kitchen ? property.area_kitchen + ' м²' : '—'" />
          <InfoRow label="Комнат"        :value="property.rooms_count || '—'" />
          <InfoRow label="Этаж"          :value="(property.floor_number || '—') + ' / ' + (property.total_floors || '—')" />
          <InfoRow label="Статус"        :value="property.status_name" />
        </div>
      </div>

      <div class="panel panel--light">
        <h2 class="h3">Описание</h2>
        <p style="white-space: pre-wrap">{{ property.description || 'Нет описания.' }}</p>
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

    <div class="panel panel--light">
      <div class="row row--between">
        <h2 class="h3">Смена статуса</h2>
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
      <h2 class="h3">История статусов</h2>
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
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import InfoRow from '../components/InfoRow.vue'

const route = useRoute(); const router = useRouter()
const property = ref(null)
const statuses = ref([])
const history = ref([])

async function load() {
  const [p, s, h] = await Promise.all([
    api.get(`/properties/${route.params.id}/`),
    api.get('/property-statuses/'),
    api.get(`/properties/${route.params.id}/history/`),
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

async function remove() {
  if (!confirm('Удалить объект?')) return
  await api.delete(`/properties/${route.params.id}/`)
  router.push('/properties')
}

function formatMoney(v) { return new Intl.NumberFormat('ru-RU').format(v || 0) }

onMounted(load)
</script>
