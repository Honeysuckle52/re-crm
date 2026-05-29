<template>
  <section class="dashboard">
    <div class="hero hero--compact">
      <div class="hero__eyebrow">CRM агентства недвижимости</div>
      <h1 class="hero__title hero__title--compact">РИЭЛТ</h1>
      <div class="hero__subtitle">
        Объекты, заявки, задачи и сделки в одном рабочем контуре
      </div>
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
        <a v-if="auth.isManager" :href="adminPanelHref" class="btn btn--primary">
          Системная панель
        </a>
      </div>
      <div class="hero__callout">
        <h3>Текущий рабочий фокус</h3>
        <p>
          Открывайте заявки, распределяйте задачи, ведите сделки и контролируйте
          загрузку сотрудников без переключения между разрозненными инструментами.
        </p>
      </div>
    </div>

    <div class="grid grid--4 dashboard__showcase">
      <article
        v-for="card in showcaseCards"
        :key="card.title"
        class="card dashboard__showcase-card"
      >
        <span class="tag tag--panel">{{ card.badge }}</span>
        <h3 class="dashboard__showcase-title">{{ card.title }}</h3>
        <p class="dashboard__showcase-text">{{ card.text }}</p>
        <router-link :to="card.to" class="btn btn--ghost btn--sm">
          {{ card.cta }}
        </router-link>
      </article>
    </div>

    <div class="grid grid--2 dashboard__content">
      <div class="panel dashboard__panel dashboard__panel--accent">
        <div class="surface-head dashboard-panel-head">
          <div>
            <div class="surface-head__meta">Быстрые действия</div>
            <h2 class="h2 dashboard__title">Работа с входящим потоком</h2>
          </div>
        </div>
        <p class="dashboard__text">
          Создавайте новые объекты, открывайте заявки клиентов и быстро
          переходите к основным рабочим контурам команды.
        </p>
        <div class="dashboard__actions">
          <router-link to="/requests" class="btn btn--accent">
            Открыть заявки
          </router-link>
          <router-link to="/properties" class="btn btn--ghost">
            Смотреть объекты
          </router-link>
        </div>
      </div>

      <div class="panel panel--light dashboard__panel">
        <div class="surface-head dashboard-panel-head">
          <div>
            <div class="surface-head__meta">Система и данные</div>
            <h2 class="h2 dashboard__title">Подсказки по работе</h2>
          </div>
        </div>
        <div class="dashboard__tips">
          <div class="dashboard__tip">
            <b>Каталог объектов</b>
            <span>
              Используйте широкий каталог и закреплённый фильтр для быстрого
              подбора вариантов.
            </span>
          </div>
          <div class="dashboard__tip">
            <b>Заявки и задачи</b>
            <span>
              Сначала разбирайте нераспределённые заявки, затем переводите
              процесс в задачи и подборку.
            </span>
          </div>
          <div class="dashboard__tip">
            <b>Сделки и договоры</b>
            <span>
              Контролируйте статусы и PDF-договоры прямо из журнала сделок.
            </span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const adminPanelHref = computed(() => (auth.isAdmin ? '/admin/' : '/admin'))

const showcaseCards = [
  {
    badge: 'Каталог',
    title: 'Объекты в работе',
    text: 'Поддерживайте базу недвижимости, быстро фильтруйте карточки и открывайте нужный объект без лишних переходов.',
    cta: 'Открыть каталог',
    to: '/properties',
  },
  {
    badge: 'Воронка',
    title: 'Заявки клиентов',
    text: 'Собирайте входящий поток, закрепляйте менеджеров и переводите обращения в следующий рабочий этап.',
    cta: 'Перейти к заявкам',
    to: '/requests',
  },
  {
    badge: 'Процесс',
    title: 'Задачи команды',
    text: 'Держите под рукой активные поручения, сроки и текущую загрузку сотрудников в одном рабочем блоке.',
    cta: 'Открыть задачи',
    to: '/tasks',
  },
  {
    badge: 'Финализация',
    title: 'Сделки и договоры',
    text: 'Контролируйте этапы закрытия, документы и финальную стоимость сделки через отдельный журнал.',
    cta: 'Смотреть сделки',
    to: '/deals',
  },
]

const canEdit = computed(() => auth.user?.user_type === 'employee')
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero--compact {
  padding: 24px 28px;
}

.hero--compact .hero__eyebrow {
  min-height: 28px;
  padding: 0 12px;
  font-size: 11px;
  letter-spacing: 0.16em;
}

.hero--compact .hero__title--compact {
  font-size: clamp(42px, 5vw, 64px);
  margin: 12px 0 0;
}

.hero--compact .hero__subtitle {
  display: block;
  min-height: 0;
  margin-top: 10px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 15px;
  line-height: 1.5;
  color: rgba(234, 245, 243, 0.84);
}

.hero--compact .hero__actions {
  margin-top: 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero--compact .hero__callout {
  margin-top: 22px;
  max-width: 760px;
}

.dashboard__showcase {
  align-items: stretch;
}

.dashboard__showcase-card {
  min-height: 240px;
  justify-content: space-between;
  gap: 16px;
  padding: 22px;
}

.dashboard__showcase-title {
  margin: 0;
  font-size: 20px;
  line-height: 1.15;
  font-weight: 700;
  color: var(--c-text);
}

.dashboard__showcase-text {
  margin: 0;
  color: rgba(234, 245, 243, 0.82);
  font-size: 14px;
}

.dashboard__content {
  align-items: stretch;
}

.dashboard__panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 100%;
}

.dashboard__panel--accent {
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
}

.dashboard-panel-head {
  margin-bottom: 2px;
}

.dashboard__title {
  margin-top: 4px;
  margin-bottom: 0;
}

.dashboard__text {
  margin: 0;
  color: rgba(255, 255, 255, 0.84);
  font-size: 14px;
}

.dashboard__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: auto;
}

.dashboard__tips {
  display: grid;
  gap: 12px;
}

.dashboard__tip {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 24px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, rgba(13, 59, 62, 0.9), rgba(3, 43, 43, 0.96));
  transition: transform 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
}

.dashboard__tip:hover {
  transform: translateY(-3px);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  box-shadow: var(--shadow-1);
}

.dashboard__tip b {
  font-size: 14px;
  color: var(--c-text);
}

.dashboard__tip span {
  color: rgba(234, 245, 243, 0.84);
  font-size: 14px;
  line-height: 1.55;
}

@media (max-width: 1024px) {
  .dashboard {
    min-height: auto;
  }

  .dashboard__showcase {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .hero--compact .hero__actions {
    width: 100%;
  }

  .hero--compact .hero__actions .btn {
    width: 100%;
    justify-content: center;
  }

  .dashboard__showcase {
    grid-template-columns: 1fr;
  }
}
</style>
