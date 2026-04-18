<template>
  <header class="topbar">
    <nav class="topbar__nav">
      <router-link to="/">Сводка</router-link>
      <router-link to="/properties">Объекты</router-link>
      <router-link to="/requests">Заявки</router-link>
      <router-link v-if="canSeeTasks" to="/tasks">Задачи</router-link>
      <router-link v-if="canSeeDeals" to="/deals">Сделки</router-link>
      <router-link v-if="canSeeClients" to="/clients">Пользователи</router-link>
      <router-link v-if="canSeeAdmin" to="/admin" class="topbar__nav-admin">
        Админ-панель
      </router-link>
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

const canSeeClients = computed(() => auth.isStaff)
const canSeeDeals   = computed(() => auth.isStaff)
const canSeeTasks   = computed(() => auth.isStaff)
// Админ-панель видят только администраторы и менеджеры.
const canSeeAdmin   = computed(() => auth.isManager)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.topbar__nav-admin {
  background: var(--c-accent);
  color: #fff !important;
  font-weight: 600;
}
.topbar__nav-admin:hover { background: var(--c-accent); opacity: .92; }
</style>
