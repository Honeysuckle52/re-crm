<template>
  <div>
    <TopBar v-if="auth.isAuthenticated" />
    <main class="layout">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <AppFooter v-if="auth.isAuthenticated" />
  </div>
</template>

<script setup>
import { useAuthStore } from './store/auth'
import TopBar from './components/TopBar.vue'
import AppFooter from './components/AppFooter.vue'

const auth = useAuthStore()
</script>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
