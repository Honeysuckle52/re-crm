<template>
  <span v-if="isMine" class="mine" :class="stateClass">
    <span class="mine__dot" aria-hidden="true"></span>
    <span v-if="mode === 'full'" class="mine__label">{{ label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: { type: Object, required: true },
  userId: { type: Number, default: null },
  mode: { type: String, default: 'full' },
})

const isMine = computed(
  () => props.userId != null && props.task?.assignee === props.userId,
)

const isActive = computed(() => props.task?.status_code === 'in_progress')

const stateClass = computed(() => (
  isActive.value ? 'mine--active' : 'mine--assigned'
))

const label = computed(() => (
  isActive.value ? 'выполняете' : 'ваша задача'
))
</script>

<style scoped>
.mine {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: .02em;
  line-height: 1.2;
  white-space: nowrap;
  border: 1px solid rgba(120, 216, 206, 0.16);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.mine__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
}

.mine--assigned {
  background: rgba(120, 216, 206, 0.12);
  color: #efffff;
  border-color: rgba(120, 216, 206, 0.22);
}

.mine--active {
  background: linear-gradient(135deg, rgba(46, 159, 152, 0.22), rgba(120, 216, 206, 0.18));
  color: #eafff7;
  border-color: rgba(120, 216, 206, 0.26);
  box-shadow: 0 0 18px rgba(120, 216, 206, 0.14);
}

.mine--active .mine__dot {
  background: var(--c-accent-2);
  box-shadow: 0 0 0 3px rgba(120, 216, 206, 0.16);
  animation: mine-pulse 1.6s ease-in-out infinite;
}

@keyframes mine-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.2); opacity: .75; }
}
</style>
