<template>
  <div
    class="data-fetch-panel"
    :class="{
      'data-fetch-panel--compact': compact,
      'data-fetch-panel--error': !!error,
      'data-fetch-panel--loading': loading && !error,
    }"
  >
    <div class="data-fetch-panel__copy">
      <strong>{{ headline }}</strong>
      <span>{{ description }}</span>
    </div>
    <div v-if="error" class="data-fetch-panel__actions">
      <button class="btn btn--sm" type="button" @click="$emit('retry')">
        {{ retryLabel }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  compact: {
    type: Boolean,
    default: false,
  },
  loadingTitle: {
    type: String,
    default: 'Загрузка данных',
  },
  loadingText: {
    type: String,
    default: 'Подождите, данные обновляются.',
  },
  errorTitle: {
    type: String,
    default: 'Не удалось загрузить данные',
  },
  retryLabel: {
    type: String,
    default: 'Повторить',
  },
})

defineEmits(['retry'])

const headline = computed(() => (
  props.error ? props.errorTitle : props.loadingTitle
))

const description = computed(() => (
  props.error || props.loadingText
))
</script>

<style scoped>
.data-fetch-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 24px;
  border: 1px solid rgba(120, 216, 206, 0.18);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  color: var(--c-text);
}

.data-fetch-panel--compact {
  padding: 14px 16px;
  border-radius: 20px;
}

.data-fetch-panel--error {
  border-color: rgba(194, 85, 74, 0.24);
  background: rgba(194, 85, 74, 0.08);
}

.data-fetch-panel--loading {
  border-color: rgba(120, 216, 206, 0.18);
  background: rgba(120, 216, 206, 0.08);
}

.data-fetch-panel__copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.data-fetch-panel__copy strong {
  font-size: 15px;
  line-height: 1.35;
}

.data-fetch-panel__copy span {
  color: var(--c-ink-soft);
  font-size: 14px;
  line-height: 1.5;
}

.data-fetch-panel__actions {
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .data-fetch-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .data-fetch-panel__actions .btn {
    width: 100%;
  }
}
</style>
