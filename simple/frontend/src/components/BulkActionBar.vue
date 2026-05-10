<template>
  <div v-if="count > 0" class="bulk-bar">
    <div class="bulk-bar__meta">
      Выбрано <b>{{ count }}</b> {{ label }}
    </div>
    <div class="bulk-bar__actions">
      <slot />
      <button class="btn btn--sm" type="button" @click="$emit('clear')">
        Снять выбор
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  count: {
    type: Number,
    default: 0,
  },
  label: {
    type: String,
    default: 'записей',
  },
})

defineEmits(['clear'])
</script>

<style scoped>
.bulk-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 14px 16px;
  margin-bottom: 12px;
  border-radius: 18px;
  border: 1px solid rgba(21, 56, 57, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(230, 238, 242, 0.94));
  box-shadow: 0 12px 24px rgba(16, 55, 52, 0.08);
}

.bulk-bar__meta {
  color: var(--c-page-text);
  font-size: 14px;
}

.bulk-bar__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
