<template>
  <div v-if="count > 0" class="list-pagination">
    <div class="list-pagination__summary muted">
      Показано {{ rangeStart }}–{{ rangeEnd }} из {{ count }} {{ label }}
    </div>
    <div class="list-pagination__controls">
      <label class="list-pagination__size">
        <span>На странице</span>
        <select
          class="select select--sm"
          :value="pageSize"
          :disabled="disabled"
          @change="$emit('change-page-size', Number($event.target.value))"
        >
          <option v-for="size in pageSizeOptions" :key="size" :value="size">
            {{ size }}
          </option>
        </select>
      </label>
      <button
        type="button"
        class="btn btn--sm"
        :disabled="disabled || page <= 1"
        @click="$emit('change', page - 1)"
      >
        Назад
      </button>
      <span class="list-pagination__page">
        Страница {{ page }} из {{ totalPages }}
      </span>
      <button
        type="button"
        class="btn btn--sm"
        :disabled="disabled || page >= totalPages"
        @click="$emit('change', page + 1)"
      >
        Вперёд
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/utils/paginated'

const props = defineProps({
  count: {
    type: Number,
    required: true,
  },
  page: {
    type: Number,
    required: true,
  },
  visibleCount: {
    type: Number,
    required: true,
  },
  pageSize: {
    type: Number,
    default: DEFAULT_PAGE_SIZE,
  },
  label: {
    type: String,
    default: 'записей',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  pageSizeOptions: {
    type: Array,
    default: () => PAGE_SIZE_OPTIONS,
  },
})

defineEmits(['change', 'change-page-size'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.count / props.pageSize)))
const rangeStart = computed(() => (
  props.count ? ((props.page - 1) * props.pageSize) + 1 : 0
))
const rangeEnd = computed(() => (
  props.count
    ? Math.min(((props.page - 1) * props.pageSize) + props.visibleCount, props.count)
    : 0
))
</script>

<style scoped>
.list-pagination {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.list-pagination__controls {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.list-pagination__size {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--c-muted);
  font-size: 14px;
  font-weight: 600;
}

.list-pagination__size .select {
  min-width: 92px;
}

.list-pagination__page {
  min-width: 132px;
  text-align: center;
  color: var(--c-muted);
  font-size: 14px;
  font-weight: 600;
}

@media (max-width: 640px) {
  .list-pagination {
    align-items: stretch;
  }

  .list-pagination__controls {
    width: 100%;
    justify-content: space-between;
  }

  .list-pagination__size {
    width: 100%;
    justify-content: space-between;
  }

  .list-pagination__page {
    flex: 1 1 auto;
    min-width: 0;
  }
}
</style>
