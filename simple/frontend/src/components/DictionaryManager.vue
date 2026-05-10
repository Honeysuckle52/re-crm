<template>
  <div class="panel panel--light dictionary-manager">
    <div class="surface-head dictionary-manager__head">
      <div>
        <div class="surface-head__meta">{{ eyebrow }}</div>
        <h3 class="h3">{{ title }}</h3>
        <p v-if="description" class="muted dictionary-manager__description">{{ description }}</p>
      </div>
      <button class="btn btn--sm" :disabled="loading" @click="loadItems">
        {{ loading ? 'Обновление…' : 'Обновить' }}
      </button>
    </div>

    <div class="table-wrap dictionary-manager__table">
      <table class="table">
        <thead>
          <tr>
            <th>Код</th>
            <th>Название</th>
            <th v-if="includeOrder">Порядок</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>
              <input
                v-model.trim="item.code"
                class="input input--sm"
                :placeholder="codePlaceholder" />
            </td>
            <td>
              <input
                v-model.trim="item.name"
                class="input input--sm"
                :placeholder="namePlaceholder" />
            </td>
            <td v-if="includeOrder">
              <input
                v-model.number="item.order"
                class="input input--sm dictionary-manager__order"
                type="number"
                min="0" />
            </td>
            <td class="dictionary-manager__actions">
              <button
                class="btn btn--sm"
                :disabled="savingId === item.id"
                @click="saveItem(item)">
                {{ savingId === item.id ? 'Сохранение…' : 'Сохранить' }}
              </button>
              <button
                class="btn btn--sm btn--danger"
                :disabled="savingId === item.id"
                @click="removeItem(item)">
                Удалить
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!items.length && !loading" class="empty dictionary-manager__empty">
      {{ emptyLabel }}
    </div>

    <form class="dictionary-manager__form" @submit.prevent="createItem">
      <input
        v-model.trim="newItem.code"
        class="input"
        :placeholder="codePlaceholder"
        required />
      <input
        v-model.trim="newItem.name"
        class="input"
        :placeholder="namePlaceholder"
        required />
      <input
        v-if="includeOrder"
        v-model.number="newItem.order"
        class="input dictionary-manager__order"
        type="number"
        min="0"
        placeholder="порядок" />
      <button class="btn btn--accent btn--sm" type="submit" :disabled="creating">
        {{ creating ? 'Добавление…' : 'Добавить' }}
      </button>
    </form>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { unpackPaginated } from '../utils/paginated'

const props = defineProps({
  endpoint: { type: String, required: true },
  title: { type: String, required: true },
  eyebrow: { type: String, default: 'Справочник' },
  description: { type: String, default: '' },
  emptyLabel: { type: String, default: 'Записей пока нет.' },
  codePlaceholder: { type: String, default: 'код' },
  namePlaceholder: { type: String, default: 'название' },
  includeOrder: { type: Boolean, default: false },
})

const toasts = useToastsStore()
const confirm = useConfirmStore()
const items = ref([])
const loading = ref(false)
const creating = ref(false)
const savingId = ref(null)
const error = ref('')
const newItem = reactive({
  code: '',
  name: '',
  order: 0,
})

function resetNewItem () {
  newItem.code = ''
  newItem.name = ''
  newItem.order = 0
}

function basePayload (item) {
  const payload = {
    code: item.code?.trim() || '',
    name: item.name?.trim() || '',
  }
  if (props.includeOrder) payload.order = Number(item.order || 0)
  return payload
}

async function loadItems () {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(props.endpoint, {
      params: { page: 1, page_size: 200 },
    })
    items.value = unpackPaginated(data).items
  } catch (err) {
    error.value = extractError(err, 'Не удалось загрузить справочник.')
  } finally {
    loading.value = false
  }
}

async function createItem () {
  creating.value = true
  error.value = ''
  try {
    await api.post(props.endpoint, basePayload(newItem))
    resetNewItem()
    await loadItems()
    toasts.success('Справочник обновлён')
  } catch (err) {
    error.value = extractError(err, 'Не удалось добавить запись.')
  } finally {
    creating.value = false
  }
}

async function saveItem (item) {
  savingId.value = item.id
  error.value = ''
  try {
    await api.patch(`${props.endpoint}${item.id}/`, basePayload(item))
    await loadItems()
    toasts.success('Изменения сохранены')
  } catch (err) {
    error.value = extractError(err, 'Не удалось сохранить запись.')
  } finally {
    savingId.value = null
  }
}

async function removeItem (item) {
  const approved = await confirm.ask({
    title: 'Удаление записи',
    message: `Удалить запись «${item.name}»?`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  savingId.value = item.id
  error.value = ''
  try {
    await api.delete(`${props.endpoint}${item.id}/`)
    await loadItems()
    toasts.success('Запись удалена')
  } catch (err) {
    error.value = extractError(err, 'Не удалось удалить запись.')
  } finally {
    savingId.value = null
  }
}

onMounted(loadItems)
</script>

<style scoped>
.dictionary-manager {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dictionary-manager__head {
  margin-bottom: 0;
}

.dictionary-manager__description {
  margin: 6px 0 0;
}

.dictionary-manager__table .table {
  min-width: 520px;
}

.dictionary-manager__actions {
  text-align: right;
  white-space: nowrap;
}

.dictionary-manager__actions .btn + .btn {
  margin-left: 8px;
}

.dictionary-manager__form {
  display: grid;
  grid-template-columns: minmax(140px, 180px) minmax(180px, 1fr) auto auto;
  gap: 10px;
  align-items: center;
}

.dictionary-manager__order {
  width: 112px;
  min-width: 112px;
  text-align: center;
}

.dictionary-manager__empty {
  margin-top: -4px;
}

@media (max-width: 960px) {
  .dictionary-manager__form {
    grid-template-columns: 1fr;
  }

  .dictionary-manager__actions {
    min-width: 180px;
  }
}
</style>
