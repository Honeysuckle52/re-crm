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
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 24px;
  border-radius: var(--r-md);
  border: 1px solid var(--c-border);
  background: var(--grad-card);
  box-shadow: var(--shadow-1);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.stat:hover {
  transform: translateY(-5px);
  background: var(--grad-card-soft);
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
  border-color: rgba(120, 216, 206, 0.24);
  background:
    linear-gradient(135deg, rgba(27, 77, 62, 0.94), rgba(46, 139, 87, 0.86)),
    linear-gradient(180deg, #0d3b3e 0%, #032b2b 100%);
}

.stat--accent .stat__label {
  color: rgba(239, 255, 253, 0.82);
}

.stat--accent .stat__value {
  color: #f4fffd;
  text-shadow: 0 0 18px rgba(120, 216, 206, 0.14);
}
</style>
