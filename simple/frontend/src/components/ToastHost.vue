<template>
  <!-- Стек тостов в правом верхнем углу. z-index выше, чем у виджета,
       чтобы уведомления не перекрывались. -->
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
                aria-label="Закрыть уведомление">×</button>
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
  top: 16px; right: 16px;
  display: flex; flex-direction: column; gap: 10px;
  z-index: 80;
  pointer-events: none;
  max-width: min(420px, calc(100vw - 32px));
}
.toast {
  pointer-events: auto;
  display: flex; gap: 12px; align-items: flex-start;
  background: #ffffff;
  color: #1e2a28;
  border-radius: 10px;
  border: 1px solid #e3e9e7;
  box-shadow: 0 10px 26px rgba(16, 24, 23, .14),
              0 2px 6px rgba(16, 24, 23, .06);
  padding: 12px 14px;
  font-size: 13px; line-height: 1.4;
  min-width: 240px;
  border-left-width: 4px;
}
.toast--info    { border-left-color: #1fa39a; }
.toast--success { border-left-color: #2ea56d; }
.toast--warn    { border-left-color: #d69b2f; }
.toast--error   { border-left-color: #c2554a; }

.toast__body { flex: 1; min-width: 0; }
.toast__title { font-weight: 700; font-size: 13px; margin-bottom: 2px; }
.toast__text  { color: #3d4e4c; }

.toast__close {
  border: none; background: transparent; cursor: pointer;
  color: #8aa5a0; font-size: 18px; line-height: 1;
  padding: 2px 4px; border-radius: 4px;
}
.toast__close:hover { background: #eef4f2; color: #1e2a28; }

.toast-enter-active, .toast-leave-active { transition: all .22s ease; }
.toast-enter-from { opacity: 0; transform: translateX(20px); }
.toast-leave-to   { opacity: 0; transform: translateX(20px); }
</style>
