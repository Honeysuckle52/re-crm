<template>
  <div class="panel panel--light process-manager">
    <div class="surface-head process-manager__head">
      <div>
        <div class="surface-head__meta">Версионность процессов</div>
        <h2 class="h3">Схемы жизненного цикла</h2>
        <p class="muted process-manager__description">
          Новые заявки и задачи получают активную версию процесса, а старые записи сохраняют свою.
        </p>
      </div>
      <div class="row" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn--sm" :disabled="loading" @click="loadVersions">
          {{ loading ? 'Обновление…' : 'Обновить' }}
        </button>
        <button class="btn btn--accent btn--sm" @click="openCreate">
          Новая версия
        </button>
      </div>
    </div>

    <div class="table-wrap process-manager__table">
      <table class="table">
        <thead>
          <tr>
            <th>Процесс</th>
            <th>Область</th>
            <th>Версия</th>
            <th>Название</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in versions" :key="item.id">
            <td>{{ item.process_code_display }}</td>
            <td>{{ item.scope_code || 'default' }}</td>
            <td>v{{ item.version }}</td>
            <td>{{ item.name }}</td>
            <td>
              <span class="tag" :class="item.is_active ? 'tag--accent' : 'tag--muted'">
                {{ item.is_active ? 'Активна' : 'Черновик' }}
              </span>
            </td>
            <td class="process-manager__actions">
              <button class="btn btn--sm" @click="openEdit(item)">Редактировать</button>
              <button class="btn btn--sm" @click="openClone(item)">Клонировать</button>
              <button
                class="btn btn--sm btn--accent"
                :disabled="item.is_active"
                @click="activate(item)">
                Активировать
              </button>
              <button class="btn btn--sm btn--danger" @click="removeVersion(item)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!versions.length && !loading" class="empty">
      Версии процессов ещё не настроены.
    </div>
    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="dialogOpen" class="modal" @click.self="closeDialog">
      <div class="panel panel--light modal__card process-manager__dialog">
        <div class="row row--between" style="gap: 12px">
          <h3 class="h3">{{ editingId ? 'Редактирование версии' : 'Новая версия процесса' }}</h3>
          <button class="btn btn--sm" @click="closeDialog">Закрыть</button>
        </div>

        <div class="grid grid--2 process-manager__grid">
          <div class="field">
            <label>Процесс</label>
            <select v-model="form.process_code" class="select">
              <option value="request">Заявки</option>
              <option value="task">Задачи</option>
            </select>
          </div>
          <div class="field">
            <label>Область</label>
            <input
              v-model.trim="form.scope_code"
              class="input"
              :placeholder="form.process_code === 'request' ? 'request' : 'property_search'" />
          </div>
        </div>

        <div class="grid grid--2 process-manager__grid">
          <div class="field">
            <label>Название</label>
            <input v-model.trim="form.name" class="input" placeholder="Жизненный цикл заявки" />
          </div>
          <div class="field">
            <label>Версия</label>
            <input :value="editingVersionLabel" class="input" disabled />
          </div>
        </div>

        <div class="field">
          <label>Описание</label>
          <textarea v-model.trim="form.description" class="input" rows="2" />
        </div>

        <div class="field">
          <label>Схема процесса (JSON)</label>
          <textarea v-model="form.schemaText" class="input process-manager__schema" rows="14" />
        </div>

        <label class="process-manager__switch">
          <input v-model="form.is_active" type="checkbox" />
          <span>Сделать активной сразу после сохранения</span>
        </label>

        <div class="row" style="justify-content: flex-end; gap: 8px">
          <button class="btn btn--sm" @click="closeDialog">Отмена</button>
          <button class="btn btn--primary btn--sm" :disabled="saving" @click="saveVersion">
            {{ saving ? 'Сохранение…' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { unpackPaginated } from '../utils/paginated'

const toasts = useToastsStore()
const confirm = useConfirmStore()
const versions = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const dialogOpen = ref(false)
const editingId = ref(null)
const editingVersion = ref(null)

const form = reactive({
  process_code: 'request',
  scope_code: 'request',
  name: '',
  description: '',
  schemaText: '[]',
  is_active: true,
})

const editingVersionLabel = computed(() => {
  if (editingVersion.value == null) return 'будет назначена автоматически'
  return `v${editingVersion.value}`
})

function normalizeSchemaText(schema) {
  return JSON.stringify(schema ?? [], null, 2)
}

function resetForm () {
  editingId.value = null
  editingVersion.value = null
  form.process_code = 'request'
  form.scope_code = 'request'
  form.name = ''
  form.description = ''
  form.schemaText = '[]'
  form.is_active = true
}

function applyItem(item, { clone = false } = {}) {
  editingId.value = clone ? null : item?.id ?? null
  editingVersion.value = clone ? null : item?.version ?? null
  form.process_code = item?.process_code ?? 'request'
  form.scope_code = item?.scope_code ?? (form.process_code === 'request' ? 'request' : 'other')
  form.name = item?.name ?? ''
  form.description = item?.description ?? ''
  form.schemaText = normalizeSchemaText(item?.schema)
  form.is_active = clone ? false : (item?.is_active ?? true)
}

function openCreate () {
  resetForm()
  dialogOpen.value = true
}

function openEdit (item) {
  applyItem(item)
  dialogOpen.value = true
}

function openClone (item) {
  applyItem(item, { clone: true })
  dialogOpen.value = true
}

function closeDialog () {
  dialogOpen.value = false
  resetForm()
}

async function loadVersions () {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/process-versions/', {
      params: {
        page: 1,
        page_size: 200,
        ordering: 'process_code,scope_code,-version',
      },
    })
    versions.value = unpackPaginated(data).items
  } catch (err) {
    error.value = extractError(err, 'Не удалось загрузить версии процессов.')
  } finally {
    loading.value = false
  }
}

async function saveVersion () {
  saving.value = true
  error.value = ''
  try {
    const payload = {
      process_code: form.process_code,
      scope_code: form.scope_code.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      schema: JSON.parse(form.schemaText),
      is_active: form.is_active,
    }
    if (editingId.value) {
      await api.patch(`/process-versions/${editingId.value}/`, payload)
    } else {
      await api.post('/process-versions/', payload)
    }
    await loadVersions()
    closeDialog()
    toasts.success('Версия процесса сохранена')
  } catch (err) {
    error.value = extractError(err, 'Не удалось сохранить версию процесса.')
  } finally {
    saving.value = false
  }
}

async function activate (item) {
  error.value = ''
  try {
    await api.post(`/process-versions/${item.id}/activate/`)
    await loadVersions()
    toasts.success('Версия процесса активирована')
  } catch (err) {
    error.value = extractError(err, 'Не удалось активировать версию процесса.')
  }
}

async function removeVersion (item) {
  const approved = await confirm.ask({
    title: 'Удаление версии процесса',
    message: `Удалить версию ${item.name} v${item.version}?`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  error.value = ''
  try {
    await api.delete(`/process-versions/${item.id}/`)
    await loadVersions()
    toasts.success('Версия процесса удалена')
  } catch (err) {
    error.value = extractError(err, 'Не удалось удалить версию процесса.')
  }
}

onMounted(loadVersions)
</script>

<style scoped>
.process-manager {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.process-manager__description {
  margin: 6px 0 0;
}

.process-manager__table .table {
  min-width: 900px;
}

.process-manager__actions {
  text-align: right;
  white-space: nowrap;
}

.process-manager__actions .btn + .btn {
  margin-left: 8px;
}

.process-manager__dialog {
  width: min(980px, calc(100vw - 24px));
  max-width: min(980px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.process-manager__grid {
  gap: 12px;
}

.process-manager__schema {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
  line-height: 1.45;
}

.process-manager__switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text);
}

.tag--muted {
  color: var(--text-muted, rgba(31, 48, 61, 0.7));
  background: rgba(255, 255, 255, 0.62);
  border-color: rgba(31, 48, 61, 0.12);
}

@media (max-width: 960px) {
  .process-manager__dialog {
    width: min(100%, calc(100vw - 16px));
    max-width: min(100%, calc(100vw - 16px));
  }
}
</style>
