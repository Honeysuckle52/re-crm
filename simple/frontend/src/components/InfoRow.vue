<template>
  <div class="info-row">
    <span class="info-row__label">{{ label }}</span>
    <span class="info-row__value">{{ value }}</span>
  </div>
</template>

<script setup>
defineProps({ label: String, value: [String, Number] })
</script>

<style scoped>
.info-row {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 16px; padding: 8px 0;
  border-bottom: 1px dashed rgba(0,0,0,.08);
}
.info-row:last-child { border-bottom: 0; }
.info-row__label { color: var(--c-ink-soft); font-size: 13px; }
.info-row__value { font-weight: 600; }
</style>
