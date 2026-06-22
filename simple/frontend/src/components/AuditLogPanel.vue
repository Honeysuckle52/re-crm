<template>
  <section class="panel panel--light">
    <div class="surface-head audit-log__head">
      <div>
        <div class="surface-head__meta">{{ title }}</div>
        <div v-if="caption" class="surface-head__caption">{{ caption }}</div>
      </div>
    </div>

    <div v-if="loading" class="muted">Загружаем журнал действий…</div>
    <div v-else-if="errorText" class="audit-log__error">{{ errorText }}</div>
    <div v-else-if="!entries.length" class="muted">{{ emptyText }}</div>
    <div v-else class="audit-log__list">
      <article v-for="entry in entries" :key="entry.id" class="audit-log__item">
        <div class="audit-log__item-head">
          <div class="audit-log__meta">
            <span class="audit-log__badge">{{ entry.action_label || entry.action_code || 'Событие' }}</span>
            <span v-if="entry.entity_type_display" class="muted">{{ entry.entity_type_display }}</span>
            <span v-if="entry.actor_username" class="muted">{{ entry.actor_username }}</span>
          </div>
          <time class="audit-log__time">{{ formatDateTime(entry.created_at) }}</time>
        </div>
        <div class="audit-log__message">{{ entry.message || 'Без описания' }}</div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { listAuditLogs } from '@/api/audit'
import { formatDate } from '@/utils/formatters'

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
const isMounted = ref(true) // Добавляем флаг

const paramsKey = computed(() => JSON.stringify(props.params || {}))

function formatDateTime (value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU')
}

async function load () {
  // Проверяем, жив ли компонент
  if (!isMounted.value) return

  const params = { ...(props.params || {}) }
  if (!Object.keys(params).length) {
    if (isMounted.value) {
      entries.value = []
      errorText.value = ''
    }
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const payload = await listAuditLogs({
      ...params,
      page_size: props.pageSize,
    })
    if (isMounted.value) {
      entries.value = payload.items
    }
  } catch {
    if (isMounted.value) {
      entries.value = []
      errorText.value = 'Не удалось загрузить журнал действий.'
    }
  } finally {
    if (isMounted.value) {
      loading.value = false
    }
  }
}

// Сохраняем ссылку на watcher
let stopWatcher = null

// Создаем watcher с возможностью остановки
stopWatcher = watch(paramsKey, () => {
  load()
}, { immediate: true })

// Останавливаем watcher при размонтировании
onBeforeUnmount(() => {
  isMounted.value = false
  if (stopWatcher) {
    stopWatcher()
    stopWatcher = null
  }
})
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
