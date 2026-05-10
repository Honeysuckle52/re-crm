<template>
  <section v-if="isManagerPanel" class="stack">
    <div class="hero admin-hero">
      <div class="row row--between admin-hero__row" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">МОДЕРАТОРСКАЯ ПАНЕЛЬ</div>
          <h1 class="h2 admin-hero__title">Панель управления</h1>
          <div class="admin-hero__text">
            Для менеджера здесь оставлен быстрый доступ к пользователям и отчётам.
            Системные настройки, справочники, шаблоны, версии процессов и аудит
            перенесены в Django admin для администратора.
          </div>
        </div>
        <div class="admin-role-badge">
          <span class="tag tag--accent admin-role-pill">
            {{ auth.roleLabel }}
          </span>
        </div>
      </div>
    </div>

    <div class="grid grid--2 admin-grid">
      <div class="panel panel--light admin-panel">
        <div class="surface-head admin-section-head">
          <div>
            <div class="surface-head__meta">Пользователи</div>
            <h2 class="h2">Клиенты и сотрудники</h2>
          </div>
          <span class="surface-head__caption">всего: {{ counters.total }}</span>
        </div>
        <p class="muted admin-panel__text">
          Просмотр списка пользователей, назначение ролей и переход в полную
          карточку сотрудников и клиентов.
        </p>
        <div class="admin-stats">
          <div class="admin-stat">
            <strong>{{ counters.total }}</strong>
            <span>в системе</span>
          </div>
          <div class="admin-stat">
            <strong>{{ counters.employees }}</strong>
            <span>сотрудников</span>
          </div>
          <div class="admin-stat">
            <strong>{{ counters.clients }}</strong>
            <span>клиентов</span>
          </div>
        </div>
        <div class="row admin-panel__actions" style="gap: 8px; flex-wrap: wrap">
          <router-link to="/clients" class="btn btn--primary">
            Открыть пользователей
          </router-link>
          <router-link to="/clients" class="btn">
            Роли и назначение
          </router-link>
        </div>
      </div>

      <div class="panel admin-panel">
        <div class="surface-head admin-section-head">
          <div>
            <div class="surface-head__meta">Отчёты</div>
            <h2 class="h2 admin-panel__title">Сводки и выгрузки</h2>
          </div>
          <span class="surface-head__caption">CSV / Excel / PDF</span>
        </div>
        <p class="admin-panel__text admin-panel__text--light">
          Отчёты по сделкам и задачам с фильтрами по периоду, статусам и
          исполнителям. Экспорт доступен прямо из рабочего интерфейса.
        </p>
        <div class="admin-report-points">
          <div class="admin-report-point">
            <b>Сделки</b>
            <span>Статусы, суммы, исполнители и итоговые выгрузки.</span>
          </div>
          <div class="admin-report-point">
            <b>Задачи</b>
            <span>Нагрузка сотрудников, сроки и история исполнения.</span>
          </div>
        </div>
        <div class="row admin-panel__actions" style="gap: 8px; flex-wrap: wrap">
          <router-link to="/reports" class="btn btn--accent">
            Открыть отчёты
          </router-link>
          <router-link to="/reports" class="btn btn--ghost">
            Фильтры и экспорт
          </router-link>
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head admin-section-head">
        <div>
          <div class="surface-head__meta">Команда агентства</div>
          <h2 class="h2">Сотрудники в системе</h2>
        </div>
        <div class="row" style="gap: 10px; flex-wrap: wrap">
          <div class="surface-head__caption">
            показано: {{ employees.length }} из {{ counters.employees }}
          </div>
          <router-link to="/clients" class="btn btn--sm">Все →</router-link>
        </div>
      </div>
      <div class="table-wrap admin-table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Логин</th>
              <th>Почта</th>
              <th>Должность</th>
              <th>Тип</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in employees" :key="user.id">
              <td><b>{{ user.username }}</b></td>
              <td>{{ user.email || '—' }}</td>
              <td>{{ user.role_name || '—' }}</td>
              <td>{{ user.user_type === 'employee' ? 'Сотрудник' : 'Клиент' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!employees.length" class="empty">
        В системе пока нет назначенных сотрудников.
      </div>
    </div>
  </section>

  <section v-else-if="auth.isAdmin" class="stack">
    <div class="hero admin-hero">
      <div class="row row--between admin-hero__row" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">DJANGO ADMIN</div>
          <h1 class="h2 admin-hero__title">Системная админ-панель</h1>
          <div class="admin-hero__text">
            Для администратора системное управление перенесено в Django admin:
            справочники, статусы, шаблоны уведомлений, версии процессов,
            аудит, очередь писем и все ключевые сущности проекта.
          </div>
        </div>
        <div class="admin-role-badge">
          <span class="tag tag--accent admin-role-pill">
            {{ auth.roleLabel }}
          </span>
        </div>
      </div>
    </div>

    <div class="grid grid--2 admin-grid">
      <div class="panel panel--light admin-panel">
        <div class="surface-head admin-section-head">
          <div>
            <div class="surface-head__meta">Основная точка входа</div>
            <h2 class="h2">Открыть Django admin</h2>
          </div>
        </div>
        <p class="muted admin-panel__text">
          В системной панели доступны модели, справочники, шаблоны уведомлений,
          журнал действий, версии процессов и все администраторские операции.
        </p>
        <div class="row admin-panel__actions" style="gap: 8px; flex-wrap: wrap">
          <a href="/admin/" class="btn btn--primary">Перейти в Django admin</a>
          <router-link to="/reports" class="btn">Открыть отчёты</router-link>
        </div>
      </div>

      <div class="panel admin-panel">
        <div class="surface-head admin-section-head">
          <div>
            <div class="surface-head__meta">Операционный контур</div>
            <h2 class="h2 admin-panel__title">Рабочие страницы</h2>
          </div>
        </div>
        <p class="admin-panel__text admin-panel__text--light">
          Пользователи и отчёты остаются в основном интерфейсе CRM, чтобы
          административный и операционный контуры не смешивались.
        </p>
        <div class="row admin-panel__actions" style="gap: 8px; flex-wrap: wrap">
          <router-link to="/clients" class="btn btn--ghost">Пользователи</router-link>
          <router-link to="/reports" class="btn btn--ghost">Отчёты</router-link>
        </div>
      </div>
    </div>
  </section>

  <section v-else class="panel panel--light empty">
    <h2 class="h2">Доступ ограничен</h2>
    <p class="muted">
      Этот раздел доступен только менеджерам и администраторам агентства.
    </p>
    <router-link to="/" class="btn">На главную</router-link>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const employees = ref([])

const counters = reactive({
  total: 0,
  employees: 0,
  clients: 0,
})

const isManagerPanel = computed(() => auth.isManager && !auth.isAdmin)

async function fetchUserCount(params = {}) {
  const { data } = await api.get('/users/', {
    params: { page: 1, page_size: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadCounters() {
  const [total, employeesCount, clientsCount] = await Promise.all([
    fetchUserCount(),
    fetchUserCount({ user_type: 'employee' }),
    fetchUserCount({ user_type: 'client' }),
  ])
  counters.total = total
  counters.employees = employeesCount
  counters.clients = clientsCount
}

async function loadPreviewEmployees() {
  const { data } = await api.get('/users/', {
    params: { user_type: 'employee', page: 1, page_size: 8 },
  })
  employees.value = data?.results || data || []
}

onMounted(async () => {
  if (!isManagerPanel.value) return
  await Promise.all([loadCounters(), loadPreviewEmployees()])
})
</script>

<style scoped>
.admin-hero {
  background:
    linear-gradient(135deg, rgba(22, 88, 84, 0.92), rgba(18, 56, 53, 0.82)),
    radial-gradient(circle at top right, rgba(99, 208, 197, 0.12), transparent 24%);
  padding: 24px 28px;
}

.admin-hero__row {
  align-items: flex-start;
}

.admin-hero__title {
  color: #fff;
  margin-top: 8px;
}

.admin-hero__text {
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 14px;
  max-width: 760px;
  line-height: 1.6;
}

.admin-role-badge {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-left: auto;
}

.admin-role-pill {
  font-size: 13px;
  padding: 6px 14px;
}

.admin-grid {
  align-items: stretch;
}

.admin-panel {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.admin-panel__title {
  color: #fff;
}

.admin-panel__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
}

.admin-panel__text--light {
  color: rgba(255, 255, 255, 0.82);
}

.admin-panel__actions {
  margin-top: auto;
}

.admin-section-head {
  margin-bottom: 14px;
}

.admin-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 18px 0;
}

.admin-stat {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
}

.admin-stat strong {
  font-size: 24px;
  line-height: 1;
  color: var(--c-text-dark);
}

.admin-stat span {
  color: rgba(21, 56, 57, 0.78);
  font-size: 13px;
}

.admin-report-points {
  display: grid;
  gap: 12px;
  margin: 18px 0;
}

.admin-report-point {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid rgba(120, 216, 206, 0.14);
  background: rgba(255, 255, 255, 0.05);
}

.admin-report-point b {
  color: #fff;
  font-size: 14px;
}

.admin-report-point span {
  color: rgba(255, 255, 255, 0.78);
  font-size: 13px;
  line-height: 1.5;
}

.admin-table-wrap .table {
  min-width: 720px;
}

@media (max-width: 960px) {
  .admin-role-badge {
    justify-content: flex-start;
    margin-left: 0;
  }

  .admin-stats {
    grid-template-columns: 1fr;
  }
}
</style>
