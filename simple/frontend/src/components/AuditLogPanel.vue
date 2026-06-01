<template>
  <div class="panel panel--light">
    <div class="surface-head audit-log__head">
      <div>
        <div v-if="caption" class="surface-head__meta">{{ caption }}</div>
        <h2 class="h3">{{ title }}</h2>
      </div>
      <div v-if="entries.length" class="surface-head__caption">
        {{ entries.length }} записей
      </div>
    </div>

    <div v-if="loading" class="muted" style="margin-top: 12px">
      Загрузка истории…
    </div>
    <div v-else-if="errorText" class="audit-log__error">
      {{ errorText }}
    </div>
    <div v-else-if="entries.length" class="audit-log__list">
      <article v-for="entry in entries" :key="entry.id" class="audit-log__item">
        <div class="audit-log__item-head">
          <div class="audit-log__meta">
            <span class="audit-log__badge">{{ entry.action_label }}</span>
            <span class="muted">
              {{ entry.actor_username || 'Система' }}
            </span>
          </div>
          <time class="audit-log__time">
            {{ formatDateTime(entry.created_at) }}
          </time>
        </div>
        <div class="audit-log__message">
          {{ entry.message || entry.action_label }}
        </div>
      </article>
    </div>
    <div v-else class="muted" style="margin-top: 12px">
      {{ emptyText }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { listAuditLogs } from '@/api/audit'

const props = defineProps({
  params: {
    type: Object,
    required: true,
  },
  title: {
    type: String,
    default: 'Журнал действий',
  },
  caption: {
    type: String,
    default: '',
  },
  emptyText: {
    type: String,
    default: 'Записей в журнале пока нет.',
  },
  pageSize: {
    type: Number,
    default: 10,
  },
})

const entries = ref([])
const loading = ref(false)
const errorText = ref('')

const paramsKey = computed(() => JSON.stringify(props.params || {}))

function formatDateTime (value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU')
}

async function load () {
  const params = { ...(props.params || {}) }
  if (!Object.keys(params).length) {
    entries.value = []
    errorText.value = ''
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const payload = await listAuditLogs({
      ...params,
      page_size: props.pageSize,
    })
    entries.value = payload.items
  } catch {
    entries.value = []
    errorText.value = 'Не удалось загрузить журнал действий.'
  } finally {
    loading.value = false
  }
}

watch(paramsKey, () => {
  load()
}, { immediate: true })
</script>

<style scoped>
.audit-log__head {
  margin-bottom: 12px;
}

.audit-log__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.audit-log__item {
  padding: 14px 16px;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.05);
}

.audit-log__item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.audit-log__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.audit-log__badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--grad-control-light);
  border: 1px solid rgba(21, 56, 57, 0.16);
  color: var(--c-page-text);
  font-size: 12px;
  font-weight: 700;
}

.audit-log__time {
  color: var(--c-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.audit-log__message {
  margin-top: 8px;
  color: var(--c-text);
  line-height: 1.5;
}

.audit-log__error {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid rgba(194, 85, 74, 0.18);
  background: rgba(255, 111, 134, 0.1);
  color: #7b4741;
}

@media (max-width: 720px) {
  .audit-log__item-head {
    flex-direction: column;
  }

  .audit-log__time {
    white-space: normal;
  }

}
</style>
