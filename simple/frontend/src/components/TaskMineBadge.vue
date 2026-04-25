<!--
  TaskMineBadge — компактный бейдж «ваша задача» / «вы выполняете».

  Используется в таблице /tasks и в виджете CurrentTaskWidget. Цвет и
  форма вписаны в существующую систему .tag — подчёркнуто-аккуратно,
  без «ярких пятен», чтобы не ломать дизайн.

  Props:
    - task:   объект Task из API (нужны assignee и status_code)
    - userId: id текущего пользователя (из auth.user.id)
    - mode:   'full' | 'dot' — полный текстовый бейдж или только точка.
-->
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

// Два состояния: «назначена мне» и «я выполняю прямо сейчас».
// Оба визуально отличаются — первая спокойная, вторая акцентная.
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
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .02em;
  line-height: 1;
  white-space: nowrap;
  border: 1px solid transparent;
}

.mine__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
}

/* Спокойный вариант — просто маркер принадлежности. */
.mine--assigned {
  background: rgba(15, 58, 51, .08);
  color: #0f3a33;
  border-color: rgba(15, 58, 51, .18);
}

/* Акцентный — сотрудник уже взял задачу в работу. */
.mine--active {
  background: #0f3a33;
  color: #fff;
  border-color: #0f3a33;
}
.mine--active .mine__dot {
  background: #7be0a6;
  box-shadow: 0 0 0 3px rgba(123, 224, 166, .25);
  animation: mine-pulse 1.6s ease-in-out infinite;
}

@keyframes mine-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.2); opacity: .75; }
}
</style>
