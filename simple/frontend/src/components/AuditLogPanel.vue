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
        <div v-if="fieldChanges(entry).length" class="audit-log__diff">
          <div
            v-for="change in fieldChanges(entry)"
            :key="change.key"
            class="audit-log__diff-row"
          >
            <span class="audit-log__diff-label">{{ change.label }}</span>
            <span class="audit-log__diff-value audit-log__diff-value--old">
              {{ formatDiffValue(change.old) }}
            </span>
            <span class="audit-log__diff-arrow">→</span>
            <span class="audit-log__diff-value audit-log__diff-value--new">
              {{ formatDiffValue(change.new) }}
            </span>
          </div>
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

function fieldChanges (entry) {
  const changes = entry?.metadata?.field_changes || {}
  return Object.entries(changes).map(([key, value]) => ({
    key,
    label: value?.label || key,
    old: value?.old,
    new: value?.new,
  }))
}

function formatDiffValue (value) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) {
    return value.map(formatDiffValue).join(', ')
  }
  if (typeof value === 'object') {
    if ('label' in value && 'id' in value) {
      return `${value.label} (#${value.id})`
    }
    if ('label' in value) {
      return value.label
    }
    return JSON.stringify(value)
  }
  return String(value)
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

.audit-log__diff {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(21, 56, 57, 0.12);
}

.audit-log__diff-row {
  display: grid;
  grid-template-columns: minmax(120px, 180px) minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  font-size: 13px;
  color: var(--c-page-text);
}

.audit-log__diff-label {
  font-weight: 700;
}

.audit-log__diff-arrow {
  color: rgba(21, 56, 57, 0.52);
}

.audit-log__diff-value {
  min-width: 0;
  word-break: break-word;
}

.audit-log__diff-value--old {
  color: #8a5d56;
}

.audit-log__diff-value--new {
  color: #295f54;
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

  .audit-log__diff-row {
    grid-template-columns: 1fr;
  }
}
</style>
