<template>
  <div class="panel panel--light template-manager">
    <div class="surface-head template-manager__head">
      <div>
        <div class="surface-head__meta">Шаблоны уведомлений</div>
        <h2 class="h3">Email-шаблоны</h2>
        <p class="muted template-manager__description">
          Редактируются через интерфейс и автоматически подхватываются очередью писем.
        </p>
      </div>
      <div class="row" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn--sm" :disabled="loading" @click="loadTemplates">
          {{ loading ? 'Обновление…' : 'Обновить' }}
        </button>
        <button class="btn btn--accent btn--sm" @click="openCreate">
          Новый шаблон
        </button>
      </div>
    </div>

    <div class="table-wrap template-manager__table">
      <table class="table">
        <thead>
          <tr>
            <th>Код</th>
            <th>Название</th>
            <th>Статус</th>
            <th>Обновлён</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in templates" :key="item.id">
            <td><code>{{ item.code }}</code></td>
            <td>{{ item.name }}</td>
            <td>
              <span class="tag" :class="item.is_active ? 'tag--accent' : 'tag--muted'">
                {{ item.is_active ? 'Активен' : 'Выключен' }}
              </span>
            </td>
            <td>{{ formatDate(item.updated_at) }}</td>
            <td class="template-manager__actions">
              <button class="btn btn--sm" @click="openEdit(item)">Редактировать</button>
              <button class="btn btn--sm btn--danger" @click="removeTemplate(item)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!templates.length && !loading" class="empty">
      Шаблоны ещё не настроены.
    </div>
    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="dialogOpen" class="modal" @click.self="closeDialog">
      <div class="panel panel--light modal__card template-manager__dialog">
        <div class="row row--between" style="gap: 12px">
          <h3 class="h3">{{ editingId ? 'Редактирование шаблона' : 'Новый шаблон' }}</h3>
          <button class="btn btn--sm" @click="closeDialog">Закрыть</button>
        </div>

        <div class="grid grid--2 template-manager__grid">
          <div class="field">
            <label>Код</label>
            <input v-model.trim="form.code" class="input" placeholder="request_taken" />
          </div>
          <div class="field">
            <label>Название</label>
            <input v-model.trim="form.name" class="input" placeholder="Заявка взята в работу" />
          </div>
        </div>

        <div class="field">
          <label>Описание</label>
          <textarea v-model.trim="form.description" class="input" rows="2" />
        </div>

        <div class="field">
          <label>Тема письма</label>
          <textarea v-model="form.subject_template" class="input" rows="2" />
        </div>

        <div class="field">
          <label>Текстовая версия</label>
          <textarea v-model="form.body_template" class="input" rows="8" />
        </div>

        <div class="field">
          <label>HTML-версия</label>
          <textarea v-model="form.html_template" class="input" rows="10" />
        </div>

        <label class="template-manager__switch">
          <input v-model="form.is_active" type="checkbox" />
          <span>Шаблон активен</span>
        </label>

        <div class="row" style="justify-content: flex-end; gap: 8px">
          <button class="btn btn--sm" @click="closeDialog">Отмена</button>
          <button class="btn btn--primary btn--sm" :disabled="saving" @click="saveTemplate">
            {{ saving ? 'Сохранение…' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { unpackPaginated } from '../utils/paginated'

const toasts = useToastsStore()
const confirm = useConfirmStore()
const templates = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const dialogOpen = ref(false)
const editingId = ref(null)

const form = reactive({
  code: '',
  name: '',
  description: '',
  subject_template: '',
  body_template: '',
  html_template: '',
  is_active: true,
})

function resetForm () {
  editingId.value = null
  form.code = ''
  form.name = ''
  form.description = ''
  form.subject_template = ''
  form.body_template = ''
  form.html_template = ''
  form.is_active = true
}

function applyTemplate(item) {
  editingId.value = item?.id ?? null
  form.code = item?.code ?? ''
  form.name = item?.name ?? ''
  form.description = item?.description ?? ''
  form.subject_template = item?.subject_template ?? ''
  form.body_template = item?.body_template ?? ''
  form.html_template = item?.html_template ?? ''
  form.is_active = item?.is_active ?? true
}

function closeDialog () {
  dialogOpen.value = false
  resetForm()
}

function openCreate () {
  resetForm()
  dialogOpen.value = true
}

function openEdit (item) {
  applyTemplate(item)
  dialogOpen.value = true
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU')
}

async function loadTemplates () {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/notification-templates/', {
      params: { page: 1, page_size: 200 },
    })
    templates.value = unpackPaginated(data).items
  } catch (err) {
    error.value = extractError(err, 'Не удалось загрузить шаблоны.')
  } finally {
    loading.value = false
  }
}

async function saveTemplate () {
  saving.value = true
  error.value = ''
  try {
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      subject_template: form.subject_template,
      body_template: form.body_template,
      html_template: form.html_template,
      is_active: form.is_active,
    }
    if (editingId.value) {
      await api.patch(`/notification-templates/${editingId.value}/`, payload)
    } else {
      await api.post('/notification-templates/', payload)
    }
    await loadTemplates()
    closeDialog()
    toasts.success('Шаблон сохранён')
  } catch (err) {
    error.value = extractError(err, 'Не удалось сохранить шаблон.')
  } finally {
    saving.value = false
  }
}

async function removeTemplate (item) {
  const approved = await confirm.ask({
    title: 'Удаление шаблона',
    message: `Удалить шаблон «${item.name}»?`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  error.value = ''
  try {
    await api.delete(`/notification-templates/${item.id}/`)
    await loadTemplates()
    toasts.success('Шаблон удалён')
  } catch (err) {
    error.value = extractError(err, 'Не удалось удалить шаблон.')
  }
}

onMounted(loadTemplates)
</script>

<style scoped>
.template-manager {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.template-manager__description {
  margin: 6px 0 0;
}

.template-manager__table .table {
  min-width: 760px;
}

.template-manager__actions {
  text-align: right;
  white-space: nowrap;
}

.template-manager__actions .btn + .btn {
  margin-left: 8px;
}

.template-manager__dialog {
  width: min(980px, calc(100vw - 24px));
  max-width: min(980px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.template-manager__grid {
  gap: 12px;
}

.template-manager__switch {
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
  .template-manager__dialog {
    width: min(100%, calc(100vw - 16px));
    max-width: min(100%, calc(100vw - 16px));
  }
}
</style>
