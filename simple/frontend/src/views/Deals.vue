<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">СДЕЛКИ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">Журнал сделок</h1>
    </div>

    <div class="panel panel--light">
      <table class="table">
        <thead><tr>
          <th>№ сделки</th><th>Объект</th><th>Тип</th>
          <th>Цена, ₽</th><th>Комиссия</th><th>Дата</th>
        </tr></thead>
        <tbody>
          <tr v-for="d in deals" :key="d.id">
            <td><b>{{ d.deal_number }}</b></td>
            <td>{{ d.property_title || 'Объект #' + d.property }}</td>
            <td><span class="tag tag--accent">{{ d.operation_type_name }}</span></td>
            <td>{{ formatMoney(d.price_final) }}</td>
            <td>
              {{ d.commission_percent || '—' }}%
              <span class="muted">
                ({{ d.commission_amount ? formatMoney(d.commission_amount) + ' ₽' : '—' }})
              </span>
            </td>
            <td class="muted">
              {{ new Date(d.deal_date).toLocaleDateString('ru-RU') }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!deals.length" class="empty">Сделок пока нет.</div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const deals = ref([])
function formatMoney(v) { return new Intl.NumberFormat('ru-RU').format(v || 0) }

onMounted(async () => {
  const { data } = await api.get('/deals/')
  deals.value = data.results || data
})
</script>
