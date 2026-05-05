<template>
  <div class="toast-host" role="status" aria-live="polite">
    <transition-group name="toast">
      <div v-for="t in toasts.items" :key="t.id"
           class="toast" :class="`toast--${t.type}`">
        <div class="toast__body">
          <div v-if="t.title" class="toast__title">{{ t.title }}</div>
          <div class="toast__text">{{ t.text }}</div>
        </div>
        <button class="toast__close" type="button"
                @click="toasts.dismiss(t.id)"
                aria-label="Закрыть уведомление">x</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToastsStore } from '../store/toasts'

const toasts = useToastsStore()
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

.toast__close {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(7, 52, 52, 0.86);
  color: var(--c-text-muted);
  font-size: 16px;
  line-height: 1.1;
  text-transform: lowercase;
  transition: all 0.3s ease;
}

.toast__close:hover {
  background: var(--grad-control);
  color: var(--c-accent-2);
  box-shadow: 0 0 16px rgba(120, 216, 206, 0.12);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.24s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(24px) translateY(-4px);
}
</style>
