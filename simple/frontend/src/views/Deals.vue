<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">СДЕЛКИ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">Журнал сделок</h1>
      <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
        Воронка продаж: от первого контакта до завершения сделки
      </div>
    </div>

    <!-- Фильтр по статусам -->
    <div class="panel panel--light">
      <div class="row" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn--sm"
                :class="{ 'btn--primary': statusFilter === '' }"
                @click="statusFilter = ''">
          Все ({{ deals.length }})
        </button>
        <button v-for="s in statuses" :key="s.id"
                class="btn btn--sm"
                :class="{ 'btn--primary': statusFilter === s.id }"
                @click="statusFilter = s.id">
          {{ s.name }} ({{ countByStatus(s.id) }})
        </button>
      </div>
    </div>

    <div class="panel panel--light">
      <table class="table">
        <thead>
          <tr>
            <th>Номер</th>
            <th>Объект</th>
            <th>Тип</th>
            <th>Стоимость, ₽</th>
            <th>Комиссия</th>
            <th>Статус</th>
            <th>Дата</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in filtered" :key="d.id">
            <td><b>{{ d.deal_number }}</b></td>
            <td>{{ d.property_title || 'Объект №' + d.property }}</td>
            <td><span class="tag tag--accent">{{ d.operation_type_name }}</span></td>
            <td>{{ formatMoney(d.price_final) }}</td>
            <td>
              {{ d.commission_percent || '—' }}%
              <span class="muted">
                ({{ d.commission_amount ? formatMoney(d.commission_amount) + ' ₽' : '—' }})
              </span>
            </td>
            <td>
              <span class="tag" :class="statusClass(d.status_name)">
                {{ d.status_name || '—' }}
              </span>
            </td>
            <td class="muted">
              {{ new Date(d.deal_date).toLocaleDateString('ru-RU') }}
            </td>
            <td>
              <select class="select select--sm" :value="d.status"
                      @change="changeStatus(d, $event.target.value)">
                <option disabled value="">Изменить статус</option>
                <option v-for="s in statuses" :key="s.id" :value="s.id">
                  {{ s.name }}
                </option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!filtered.length" class="empty">Сделок по выбранному статусу нет.</div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const deals = ref([])
const statuses = ref([])
const statusFilter = ref('')

function formatMoney(v) { return new Intl.NumberFormat('ru-RU').format(v || 0) }

const filtered = computed(() => {
  if (!statusFilter.value) return deals.value
  return deals.value.filter((d) => d.status === statusFilter.value)
})

function countByStatus(id) {
  return deals.value.filter((d) => d.status === id).length
}

function statusClass(name) {
  const n = (name || '').toLowerCase()
  if (n.includes('заверш')) return 'tag--accent'
  if (n.includes('отмен')) return 'tag--panel'
  return ''
}

async function changeStatus(deal, statusId) {
  if (!statusId) return
  await api.post(`/deals/${deal.id}/change_status/`, { status_id: Number(statusId) })
  await load()
}

async function load() {
  const [d, s] = await Promise.all([
    api.get('/deals/'),
    api.get('/deal-statuses/'),
  ])
  deals.value = d.data.results || d.data
  statuses.value = s.data.results || s.data
}

onMounted(load)
</script>
