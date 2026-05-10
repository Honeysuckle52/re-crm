<template>
  <transition name="network-banner-fade">
    <div v-if="!isOnline" class="network-banner" role="status" aria-live="polite">
      <strong>Нет подключения к интернету.</strong>
      <span> Данные могут не загружаться, а отправка форм будет повторно доступна после восстановления сети.</span>
    </div>
  </transition>
</template>

<script setup>
import { useNetworkStatus } from '../composables/useNetworkStatus'

const { isOnline } = useNetworkStatus()
</script>

<style scoped>
.network-banner {
  position: sticky;
  top: 0;
  z-index: 70;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 24px;
  border-bottom: 1px solid rgba(123, 27, 27, 0.18);
  background:
    linear-gradient(180deg, rgba(255, 252, 247, 0.98), rgba(247, 239, 228, 0.98));
  color: #633c14;
  box-shadow: 0 10px 20px rgba(99, 60, 20, 0.08);
}

.network-banner strong {
  font-size: 14px;
  font-weight: 700;
}

.network-banner span {
  font-size: 14px;
  line-height: 1.5;
}

.network-banner-fade-enter-active,
.network-banner-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.network-banner-fade-enter-from,
.network-banner-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 768px) {
  .network-banner {
    padding: 10px 16px;
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
