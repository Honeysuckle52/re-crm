<template>
  <section class="stack">
    <!-- Hero блок в духе мокапа -->
    <div class="hero">
      <div class="hero__eyebrow">CRM / ERP НЕДВИЖИМОСТИ</div>
      <h1 class="hero__title">SIMPLE</h1>
      <div class="hero__subtitle">УПРАВЛЕНИЕ ОБЪЕКТАМИ И ЗАЯВКАМИ</div>
      <div class="hero__actions">
        <router-link to="/properties/new" class="btn btn--accent">
          + Новый объект
        </router-link>
        <router-link to="/requests" class="btn btn--ghost">Заявки клиентов</router-link>
      </div>
      <div class="hero__callout">
        <h3>Что это?</h3>
        <p>
          Единая система агентства: листинги, сделки, клиенты и адресная база
          ФИАС — в одном месте, с токен-аутентификацией и API для интеграций.
        </p>
      </div>
    </div>

    <div class="scroll-hint">SKROLL ▾</div>

    <!-- Статистика -->
    <div class="grid grid--stats">
      <StatCard label="Объектов"       :value="stats.properties_total" />
      <StatCard label="Активных"       :value="stats.properties_active" accent />
      <StatCard label="Открытых заявок" :value="stats.requests_open" />
      <StatCard label="Сделок"         :value="stats.deals_total" />
      <StatCard label="Сумма сделок, ₽" :value="formatMoney(stats.deals_sum)" />
      <StatCard label="Клиентов"       :value="stats.clients_total" />
    </div>

    <!-- Две колонки «PERBEDAAN / Green Pea» -->
    <div class="grid grid--2">
      <div class="panel">
        <span class="tag tag--panel">Быстрые действия</span>
        <h2 class="h2" style="color: #fff; margin-top: 12px">Подберите клиенту объект</h2>
        <p style="color: rgba(255,255,255,.8); font-size: 14px">
          Создайте заявку с параметрами поиска — менеджер получит её в работу
          и закрепит за агентом. Все статусы отслеживаются в истории.
        </p>
        <router-link to="/requests" class="btn btn--accent" style="margin-top: 8px">
          Перейти к заявкам →
        </router-link>
      </div>
      <div class="panel panel--light">
        <span class="tag tag--accent">ФИАС интеграция</span>
        <h2 class="h2" style="margin-top: 12px">Адреса из справочника ФНС</h2>
        <p class="muted">
          Адреса хранятся иерархически (город → улица → дом → адрес) и
          синхронизируются с ФИАС по master-токену. Автодополнение при
          создании объекта или заявки.
        </p>
        <router-link to="/properties/new" class="btn btn--primary">
          Создать объект →
        </router-link>
      </div>
    </div>

    <!-- Последние объекты -->
    <section class="panel panel--light">
      <div class="row row--between" style="margin-bottom: 12px">
        <h2 class="h2">Последние объекты</h2>
        <router-link to="/properties" class="btn btn--sm">Все →</router-link>
      </div>
      <div v-if="lastProperties.length" class="grid grid--3">
        <PropertyCard v-for="p in lastProperties" :key="p.id" :property="p" />
      </div>
      <div v-else class="empty">Объектов пока нет. Создайте первый!</div>
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'
import StatCard from '../components/StatCard.vue'
import PropertyCard from '../components/PropertyCard.vue'

const stats = ref({})
const lastProperties = ref([])

onMounted(async () => {
  const [s, p] = await Promise.all([
    api.get('/dashboard/stats/'),
    api.get('/properties/', { params: { page: 1 } }),
  ])
  stats.value = s.data
  lastProperties.value = (p.data.results || p.data || []).slice(0, 6)
})

function formatMoney(v) {
  if (!v) return '0'
  return new Intl.NumberFormat('ru-RU').format(v)
}
</script>
