<template>
  <header class="topbar">
    <nav class="topbar__nav">
      <router-link to="/">Сводка</router-link>
      <router-link to="/properties">Объекты</router-link>
      <router-link v-if="auth.isClient" to="/my-properties">Мои объекты</router-link>
      <router-link to="/requests">Заявки</router-link>
      <router-link v-if="canSeeTasks" to="/tasks">Задачи</router-link>
      <router-link v-if="canSeeDeals" to="/deals">Сделки</router-link>
      <a v-if="canSeeAdmin" :href="adminPanelHref" class="topbar__nav-admin">
        Админ-панель
      </a>
      <router-link to="/account">Аккаунт</router-link>
    </nav>
    <div class="topbar__user">
      <div class="topbar__user-avatar">{{ initial }}</div>
      <div class="topbar__user-meta">
        <b>{{ auth.displayName }}</b>
        <span>{{ auth.roleLabel }}</span>
      </div>
      <button class="btn btn--sm btn--ghost" @click="logout">Выход</button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()
const initial = computed(() => (auth.displayName?.[0] || '?').toUpperCase())

const canSeeDeals = computed(() => auth.isStaff || auth.isClient)
const canSeeTasks = computed(() => auth.isStaff)
const canSeeAdmin = computed(() => auth.isManager)
const adminPanelHref = computed(() => (auth.isAdmin ? '/admin/' : '/admin'))

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.topbar__nav-admin {
  background: linear-gradient(135deg, rgba(27, 77, 62, 0.98), rgba(46, 139, 87, 0.82));
  color: var(--c-text) !important;
  font-weight: 700;
  border: 1px solid rgba(120, 216, 206, 0.18);
  box-shadow: 0 10px 20px rgba(4, 24, 22, 0.18);
}

.topbar__nav-admin:hover {
  color: var(--c-text) !important;
  box-shadow: 0 12px 24px rgba(4, 24, 22, 0.22);
}
</style>
