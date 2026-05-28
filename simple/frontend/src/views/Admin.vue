<template>
  <section class="stack">
    <div class="hero admin-hero">
      <div class="row row--between admin-hero__row" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">Администрирование</div>
          <h1 class="h2 admin-hero__title">Рабочий центр управления</h1>
          <div class="admin-hero__text">
            Все системные настройки, справочники и журнал действий перенесены в Django admin.
            Здесь остаются быстрые переходы к CRM-разделам и точка входа в системную панель.
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
            <div class="surface-head__meta">Системная панель</div>
            <h2 class="h2">Открыть Django admin</h2>
          </div>
          <span class="surface-head__caption">только для администратора</span>
        </div>
        <p class="muted admin-panel__text">
          В Django admin теперь находятся справочники, модели сотрудников, аудит и все
          системные операции, которые должны жить в единой админской консоли.
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
            <h2 class="h2 admin-panel__title">Рабочие разделы CRM</h2>
          </div>
        </div>
        <p class="admin-panel__text admin-panel__text--light">
          Пользователи, заявки и отчёты остаются в основном интерфейсе CRM, чтобы
          операционная работа не смешивалась с системным администрированием.
        </p>
        <div class="row admin-panel__actions" style="gap: 8px; flex-wrap: wrap">
          <router-link to="/clients" class="btn btn--ghost">Пользователи</router-link>
          <router-link to="/requests" class="btn btn--ghost">Заявки</router-link>
          <router-link to="/reports" class="btn btn--ghost">Отчёты</router-link>
        </div>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head admin-section-head">
        <div>
          <div class="surface-head__meta">Подсказка</div>
          <h2 class="h2">Что искать в Django admin</h2>
        </div>
      </div>
      <div class="dashboard__tips">
        <div class="dashboard__tip">
          <b>Справочники</b>
          <span>Типы операций, статусы, роли и адресные сущности собраны в одном месте.</span>
        </div>
        <div class="dashboard__tip">
          <b>Пользователи</b>
          <span>Управляйте сотрудниками, клиентскими профилями и назначениями ролей.</span>
        </div>
        <div class="dashboard__tip">
          <b>Журнал</b>
          <span>Просматривайте историю значимых действий и служебные записи системы.</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
</script>
