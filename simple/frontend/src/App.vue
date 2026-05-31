<template>
  <div class="app-shell">
    <TopBar v-if="auth.isAuthenticated" />
    <NetworkBanner />
    <main class="layout">
      <router-view v-slot="{ Component, route }">
        <transition name="fade" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </transition>
      </router-view>
      <div v-if="viewError" class="panel panel--light app-error">
        <div class="surface-head">
          <div class="surface-head__meta">
            <h2 class="h3">Ошибка отображения страницы</h2>
            <div class="muted">Компонент маршрута упал при рендере. Состояние страницы было сброшено.</div>
          </div>
        </div>
        <p class="app-error__text">{{ viewError }}</p>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--accent" type="button" @click="retryCurrentRoute">
            Повторить открытие
          </button>
          <button class="btn" type="button" @click="clearViewError">
            Закрыть сообщение
          </button>
        </div>
      </div>
    </main>
    <ToastHost />
    <ConfirmHost />
    <AppFooter v-if="auth.isAuthenticated" />
  </div>
</template>

<script setup>
import { onErrorCaptured, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './store/auth'
import TopBar from './components/TopBar.vue'
import AppFooter from './components/AppFooter.vue'
import NetworkBanner from './components/NetworkBanner.vue'
import ConfirmHost from './components/ConfirmHost.vue'
import ToastHost from './components/ToastHost.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const viewError = ref('')

function clearViewError () {
  viewError.value = ''
}

async function retryCurrentRoute () {
  clearViewError()
  await router.replace({
    path: route.fullPath,
    query: { ...route.query },
    hash: route.hash,
  })
}

onErrorCaptured((err, _instance, info) => {
  console.error('Route render error:', err, info)
  viewError.value = err instanceof Error ? err.message : String(err || 'Unknown render error')
  return false
})
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
.app-shell > .layout { flex: 1 1 auto; min-width: 0; }
.app-shell > .footer { flex-shrink: 0; }

.app-error {
  margin: 18px auto 0;
  width: min(100%, 1180px);
}

.app-error__text {
  margin: 0 0 16px;
  color: var(--c-page-text);
  white-space: pre-wrap;
}
</style>
