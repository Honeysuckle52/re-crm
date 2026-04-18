<template>
  <header class="topbar">
    <nav class="topbar__nav">
      <router-link to="/">Главная</router-link>
      <router-link to="/properties">Объекты</router-link>
      <router-link to="/requests">Заявки</router-link>
      <router-link to="/clients">Клиенты</router-link>
      <router-link to="/deals">Сделки</router-link>
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

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
