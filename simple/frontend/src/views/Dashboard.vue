<template>
  <!--
    Дашборд занимает ровно одну высоту окна просмотра и не прокручивается.
    Контент разложен вертикально через flex; раздел «Последние объекты»
    вынесен на отдельную страницу /properties, чтобы здесь не появлялась
    прокрутка из-за галереи.
  -->
  <section class="dashboard">
    <!-- Hero -->
    <div class="hero hero--compact">
      <div class="hero__eyebrow">УЧЁТНАЯ СИСТЕМА АГЕНТСТВА НЕДВИЖИМОСТИ</div>
      <h1 class="hero__title hero__title--compact">РИЭЛТ</h1>
      <div class="hero__subtitle">УПРАВЛЕНИЕ ОБЪЕКТАМИ, ЗАЯВКАМИ И СДЕЛКАМИ</div>
      <div class="hero__actions">
        <router-link v-if="canEdit" to="/properties/new" class="btn btn--accent">
          + Новый объект
        </router-link>
        <router-link to="/requests" class="btn btn--ghost">
          Заявки клиентов
        </router-link>
        <router-link to="/properties" class="btn btn--ghost">
          Каталог объектов
        </router-link>
        <router-link v-if="auth.isManager" to="/admin" class="btn btn--accent">
          Админ-панель
        </router-link>
      </div>
      <div class="hero__callout">
        <h3>Что это?</h3>
        <p>
          Единая учётная система агентства недвижимости: объекты, клиенты,
          заявки, сделки и задачи сотрудников — в одном окне.
        </p>
      </div>
    </div>

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
    <div class="grid grid--2 dashboard__actions">
      <div class="panel">
        <span class="tag tag--panel">Быстрые действия</span>
        <h2 class="h2" style="color: #fff; margin-top: 10px">
          Подберите клиенту объект
        </h2>
        <p style="color: rgba(255,255,255,.8); font-size: 13px; margin: 6px 0 0">
          Создайте заявку с параметрами поиска — менеджер закрепит её за
          агентом и проведёт по воронке до сделки.
        </p>
        <router-link to="/requests" class="btn btn--accent"
                     style="margin-top: 12px">
          Перейти к заявкам →
        </router-link>
      </div>
      <div class="panel panel--light">
        <span class="tag tag--accent">Подсказки адресов</span>
        <h2 class="h2" style="margin-top: 10px">Адресы из реестра DaData</h2>
        <p class="muted" style="margin: 6px 0 0">
          Адреса хранятся иерархически: город → улица → дом → адрес.
          Индекс и координаты подставляются автоматически.
        </p>
        <router-link v-if="canEdit" to="/properties/new" class="btn btn--primary"
                     style="margin-top: 12px">
          Создать объект →
        </router-link>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import StatCard from '../components/StatCard.vue'
import { useAuthStore } from '../store/auth'
// Общий форматтер денег вынесен в utils/formatters; fallback '0' сохраняет
// прежнее поведение «нет суммы → 0».
import { formatMoney as fmtMoney } from '@/utils/formatters'

const auth = useAuthStore()
const stats = ref({})

const canEdit = computed(() => auth.user?.user_type === 'employee')

onMounted(async () => {
  const { data } = await api.get('/dashboard/stats/')
  stats.value = data
})

function formatMoney (v) { return fmtMoney(v, '0') }
</script>

<style scoped>
/*
  Дашборд должен укладываться в одну «экранную» высоту без прокрутки.
  Высота TopBar (~72px с отступами) и фиксированного Footer (~90px) уже
  учтены в глобальных паддингах .layout — здесь резервируем 220px под
  эти элементы и работаем с оставшимся пространством.
*/
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100dvh - 220px);
}

/* Компактный hero — меньше внутренних отступов и шрифт помельче, */
/* чтобы оставить место для статистики и action-панелей. */
.hero--compact { padding: 18px 24px; }
.hero--compact .hero__title--compact {
  font-size: clamp(36px, 5vw, 56px);
  margin: 10px 0 0;
}
.hero--compact .hero__subtitle { margin-top: 4px; }
.hero--compact .hero__actions { margin-top: 14px; }

/* Action-панели делим остаток высоты пополам по горизонтали. */
.dashboard__actions { flex: 0 0 auto; }
.dashboard__actions .panel {
  padding: 18px 22px;
}

/* На узких экранах снимаем жёсткую фиксацию высоты — естественная
   прокрутка безопаснее, чем обрезанный контент. */
@media (max-width: 1024px) {
  .dashboard { min-height: auto; }
}
</style>
