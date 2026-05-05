<template>
  <div class="modal" @click.self="$emit('cancel')">
    <div class="panel panel--light modal__card stack">
      <div class="row row--between" style="gap: 12px">
        <div>
          <h2 class="h3">Закрытие заявки</h2>
          <div class="muted" style="margin-top: 6px">
            Заявка <span class="close-dialog__request">#{{ requestId }}</span>. Выберите итог обработки.
          </div>
        </div>
        <button type="button" class="btn btn--sm" @click="$emit('cancel')">×</button>
      </div>

      <div class="stack close-dialog__options">
        <button
          v-for="option in requestCloseOutcomes"
          :key="option.value"
          type="button"
          class="close-dialog__option"
          :class="{ 'is-active': selectedOutcome === option.value }"
          @click="selectedOutcome = option.value"
        >
          <span class="close-dialog__option-title">{{ option.label }}</span>
          <span class="close-dialog__option-text">{{ option.description }}</span>
        </button>
      </div>

      <div class="row close-dialog__footer">
        <button type="button" class="btn btn--sm" @click="$emit('cancel')">Отмена</button>
        <button
          type="button"
          class="btn btn--primary btn--sm"
          :disabled="loading"
          @click="submit"
        >
          {{ loading ? 'Закрываем…' : submitLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { requestCloseOutcomes } from '@/utils/requestClose'

const props = defineProps({
  requestId: {
    type: [Number, String],
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['cancel', 'submit'])

const selectedOutcome = ref('completed')

watch(
  () => props.requestId,
  () => {
    selectedOutcome.value = 'completed'
  },
)

const submitLabel = computed(() => (
  selectedOutcome.value === 'completed'
    ? 'Закрыть и создать сделку'
    : 'Закрыть заявку'
))

function submit () {
  emit('submit', selectedOutcome.value)
}
</script>

<style scoped>
.close-dialog__request {
  font-weight: 700;
}

.close-dialog__options {
  gap: 10px;
}

.close-dialog__option {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.04);
  text-align: left;
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.close-dialog__option:hover {
  transform: translateY(-1px);
  border-color: rgba(99, 208, 197, 0.35);
  box-shadow: 0 12px 24px rgba(5, 35, 31, 0.12);
}

.close-dialog__option.is-active {
  border-color: rgba(99, 208, 197, 0.48);
  background: rgba(99, 208, 197, 0.1);
  box-shadow: 0 14px 28px rgba(5, 35, 31, 0.16);
}

.close-dialog__option-title {
  font-weight: 700;
  color: var(--c-text);
}

.close-dialog__option-text {
  color: var(--c-muted);
  font-size: 14px;
  line-height: 1.5;
}

.close-dialog__footer {
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
