<template>
  <div class="stat" :class="{ 'stat--accent': accent }">
    <div class="stat__label">{{ label }}</div>
    <div class="stat__value">{{ value ?? '—' }}</div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  accent: Boolean,
})
</script>

<style scoped>
.stat {
  background: var(--c-paper); border-radius: var(--r-md);
  padding: 20px 22px; box-shadow: var(--shadow-1);
  display: flex; flex-direction: column; gap: 8px;
}
.stat__label {
  font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--c-ink-soft); font-weight: 600;
}
.stat__value { font-size: 30px; font-weight: 700; color: var(--c-panel); }
.stat--accent { background: var(--c-panel); color: #fff; }
.stat--accent .stat__label { color: rgba(255,255,255,.7); }
.stat--accent .stat__value { color: #fff; }
</style>
