<template>
  <div class="app-shell">
    <TopBar v-if="auth.isAuthenticated" />
    <main class="layout">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <ToastHost />
    <AppFooter v-if="auth.isAuthenticated" />
    <CurrentTaskWidget v-if="auth.isAuthenticated && auth.isStaff" />
  </div>
</template>

<script setup>
import { useAuthStore } from './store/auth'
import TopBar from './components/TopBar.vue'
import AppFooter from './components/AppFooter.vue'
import CurrentTaskWidget from './components/CurrentTaskWidget.vue'
import ToastHost from './components/ToastHost.vue'

const auth = useAuthStore()
</script>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: clip;
}
.app-shell > .layout { flex: 1 0 auto; min-width: 0; }
.app-shell > .footer { flex-shrink: 0; }
</style>
