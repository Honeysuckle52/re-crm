<template>
  <div class="app-shell">
    <TopBar v-if="auth.isAuthenticated" />
    <NetworkBanner />
    <main class="layout">
      <router-view v-slot="{ Component, route }">
        <component
          v-if="Component && !viewError"
          :is="Component"
          :key="`${route.fullPath}:${routeViewNonce}`"
        />
        <div
          v-else-if="viewError"
          class="panel panel--light app-error"
        >
          <div class="surface-head">
            <div class="surface-head__meta">
              <h2 class="h3">Page render error</h2>
              <div class="muted">The route component crashed during render. The page state was reset.</div>
            </div>
          </div>
          <p class="app-error__text">{{ viewError }}</p>
          <div class="row" style="gap: 8px; flex-wrap: wrap">
            <button class="btn btn--accent" type="button" @click="retryCurrentRoute">
              Retry page
            </button>
            <button class="btn" type="button" @click="clearViewError">
              Dismiss
            </button>
          </div>
        </div>
        <div
          v-else
          class="panel panel--light app-error"
        >
          <div class="surface-head">
            <div class="surface-head__meta">
              <h2 class="h3">Route component missing</h2>
              <div class="muted">The route matched, but RouterView did not receive a page component.</div>
            </div>
          </div>
          <p class="app-error__text">Path: {{ route.fullPath }}</p>
        </div>
      </router-view>
    </main>
    <ToastHost />
    <ConfirmHost />
    <AppFooter v-if="auth.isAuthenticated" />
  </div>
</template>

<script setup>
import { onErrorCaptured, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './store/auth'
import TopBar from './components/TopBar.vue'
import AppFooter from './components/AppFooter.vue'
import NetworkBanner from './components/NetworkBanner.vue'
import ConfirmHost from './components/ConfirmHost.vue'
import ToastHost from './components/ToastHost.vue'

const auth = useAuthStore()
const route = useRoute()
const viewError = ref('')
const routeViewNonce = ref(0)

function clearViewError () {
  viewError.value = ''
}

function retryCurrentRoute () {
  routeViewNonce.value += 1
  clearViewError()
}

watch(() => route.fullPath, () => {
  clearViewError()
})

onErrorCaptured((err, _instance, info) => {
  console.error('Route render error:', err, info)
  viewError.value = err instanceof Error ? err.message : String(err || 'Unknown render error')
  return false
})
</script>

<style>
.fade-enter-active, .fade-leave-active {
  transition: opacity .2s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: clip;
}

.app-shell > .layout {
  flex: 1 1 auto;
  min-width: 0;
  padding-top: 40px; /* Отступ для диагностической панели */
}

.app-shell > .footer {
  flex-shrink: 0;
}

.app-error {
  margin: 18px auto 0;
  width: min(100%, 1180px);
}

.app-error__text {
  margin: 0 0 16px;
  color: var(--c-page-text);
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
}

/* Стили для диагностики */
.layout {
  position: relative;
}

.layout::after {
  content: '';
  position: fixed;
  bottom: 10px;
  right: 10px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #0f0;
  z-index: 9999;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
</style>