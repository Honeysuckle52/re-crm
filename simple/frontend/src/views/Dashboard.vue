<template>
  <section class="stack">
    <!-- Вступительный блок -->
    <div class="hero">
      <div class="hero__eyebrow">УЧЁТНАЯ СИСТЕМА АГЕНТСТВА НЕДВИЖИМОСТИ</div>
      <h1 class="hero__title">РИЭЛТ</h1>
      <div class="hero__subtitle">УПРАВЛЕНИЕ ОБЪЕКТАМИ, ЗАЯВКАМИ И СДЕЛКАМИ</div>
      <div class="hero__actions">
        <router-link v-if="canEdit" to="/properties/new" class="btn btn--accent">
          + Новый объект
        </router-link>
        <router-link to="/requests" class="btn btn--ghost">
          Заявки клиентов
        </router-link>
      </div>
      <div class="hero__callout">
        <h3>Что это?</h3>
        <p>
          Единая учётная система агентства недвижимости: объекты, клиенты,
          заявки, сделки и задачи сотрудников — в одном окне, с подсказками
          адресов и журналом операций.
        </p>
      </div>
    </div>

    <div class="scroll-hint">ПРОКРУТКА ▾</div>

    <!-- Статистика -->
    <div class="grid grid--stats">
      <StatCard label="Объектов"        :value="stats.properties_total" />
      <StatCard label="Активных"        :value="stats.properties_active" accent />
      <StatCard label="Открытых заявок" :value="stats.requests_open" />
      <StatCard label="Сделок"          :value="stats.deals_total" />
      <StatCard label="Сумма сделок, ₽" :value="formatMoney(stats.deals_sum)" />
      <StatCard label="Клиентов"        :value="stats.clients_total" />
      <StatCard v-if="stats.tasks_open !== undefined"
                label="Задач в работе" :value="stats.tasks_open" />
    </div>

    <!-- Две колонки — быстрые действия -->
    <div class="grid grid--2">
      <div class="panel">
        <span class="tag tag--panel">Быстрые действия</span>
        <h2 class="h2" style="color: #fff; margin-top: 12px">
          Подберите клиенту объект
        </h2>
        <p style="color: rgba(255,255,255,.8); font-size: 14px">
          Создайте заявку с параметрами поиска — менеджер закрепит её за
          агентом и проведёт по воронке до сделки. История статусов
          хранится автоматически.
        </p>
        <router-link to="/requests" class="btn btn--accent"
                     style="margin-top: 8px">
          Перейти к заявкам →
        </router-link>
      </div>
      <div class="panel panel--light">
        <span class="tag tag--accent">Подсказки адресов</span>
        <h2 class="h2" style="margin-top: 12px">Адресы из реестра DaData</h2>
        <p class="muted">
          Адреса хранятся иерархически: город → улица → дом → адрес.
          При создании объекта работает автодополнение по открытому сервису
          подсказок, индекс и координаты подставляются автоматически.
        </p>
        <router-link v-if="canEdit" to="/properties/new" class="btn btn--primary">
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
      <div v-else class="empty">
        Объектов пока нет. Создайте первый, чтобы начать работу.
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import StatCard from '../components/StatCard.vue'
import PropertyCard from '../components/PropertyCard.vue'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const stats = ref({})
const lastProperties = ref([])

const canEdit = computed(() => auth.user?.user_type === 'employee')

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
