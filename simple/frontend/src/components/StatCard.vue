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
  --stat-surface: linear-gradient(180deg, #124346 0%, #073434 100%);
  --stat-border: rgba(120, 216, 206, 0.2);
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 128px;
  padding: 22px 24px 24px;
  border-radius: 18px 28px 18px 28px;
  border: 1px solid var(--stat-border);
  background: var(--stat-surface);
  box-shadow: var(--shadow-1);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.stat::before,
.stat::after {
  content: '';
  position: absolute;
  width: 74px;
  height: 16px;
  border: 1px solid var(--stat-border);
  background: var(--stat-surface);
  z-index: -1;
}

.stat::before {
  top: -9px;
  left: 26px;
  border-bottom: 0;
  border-radius: 14px 14px 0 0;
}

.stat::after {
  right: 24px;
  bottom: -9px;
  border-top: 0;
  border-radius: 0 0 14px 14px;
}

.stat:nth-child(even)::before {
  right: 26px;
  left: auto;
}

.stat:nth-child(even)::after {
  right: auto;
  left: 24px;
}

.stat:hover {
  transform: translateY(-4px);
  background: linear-gradient(180deg, #165053 0%, #0a3d3f 100%);
  box-shadow: var(--shadow-glow-strong);
}

.stat__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}

.stat__value {
  font-size: clamp(30px, 3vw, 38px);
  font-weight: 800;
  line-height: 1.12;
  color: var(--c-text);
  letter-spacing: 0.01em;
}

.stat--accent {
  --stat-surface: linear-gradient(180deg, #124346 0%, #073434 100%);
  --stat-border: rgba(120, 216, 206, 0.2);
}

.stat--accent .stat__label {
  color: var(--c-text-muted);
}

.stat--accent .stat__value {
  color: var(--c-text);
  text-shadow: none;
}
</style>
