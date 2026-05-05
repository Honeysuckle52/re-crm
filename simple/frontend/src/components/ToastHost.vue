<template>
  <div class="toast-host" role="status" aria-live="polite">
    <transition-group name="toast">
      <div
        v-for="t in toasts.items"
        :key="t.id"
        class="toast"
        :class="`toast--${t.type}`"
        @mouseenter="cancelDismiss(t.id)"
        @mouseleave="scheduleDismiss(t.id)"
      >
        <div class="toast__body">
          <div v-if="t.title" class="toast__title">{{ t.title }}</div>
          <div class="toast__text">{{ t.text }}</div>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { onBeforeUnmount } from 'vue'
import { useToastsStore } from '../store/toasts'

const toasts = useToastsStore()
const dismissTimers = new Map()

function cancelDismiss(id) {
  const timerId = dismissTimers.get(id)
  if (!timerId) return
  window.clearTimeout(timerId)
  dismissTimers.delete(id)
}

function scheduleDismiss(id) {
  cancelDismiss(id)
  const timerId = window.setTimeout(() => {
    dismissTimers.delete(id)
    toasts.dismiss(id)
  }, 300)
  dismissTimers.set(id, timerId)
}

onBeforeUnmount(() => {
  dismissTimers.forEach((timerId) => window.clearTimeout(timerId))
  dismissTimers.clear()
})
</script>

<style scoped>
.toast-host {
  position: fixed;
  top: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 80;
  pointer-events: none;
  max-width: min(420px, calc(100vw - 32px));
}

.toast {
  pointer-events: auto;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  min-width: 260px;
  padding: 14px 16px;
  color: var(--c-text);
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-glow);
  font-size: 14px;
  line-height: 1.45;
  border-left-width: 4px;
}

.toast--info { border-left-color: var(--c-accent); }
.toast--success { border-left-color: var(--c-accent-2); }
.toast--warn { border-left-color: var(--c-warning); }
.toast--error { border-left-color: var(--c-danger); }

.toast__body {
  flex: 1;
  min-width: 0;
}

.toast__title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 4px;
}

.toast__text {
  color: var(--c-ink-soft);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(24px) translateY(-4px);
}
</style>
