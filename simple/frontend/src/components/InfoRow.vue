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
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(120, 216, 206, 0.14);
}

.info-row:last-child {
  border-bottom: 0;
}

.info-row__label {
  color: var(--c-text-muted);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.info-row__value {
  text-align: right;
  font-weight: 700;
  font-size: 15px;
  line-height: 1.4;
  color: var(--c-text);
}
</style>
