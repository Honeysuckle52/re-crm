<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">ПОЛЬЗОВАТЕЛИ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">База пользователей</h1>
    </div>

    <div class="panel panel--light">
      <div class="surface-head clients-section-head">
        <div>
          <div class="surface-head__meta">Реестр пользователей</div>
          <h2 class="h3">Поиск и фильтрация</h2>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--sm" :disabled="exportingUsers" @click="exportUsers('csv')">CSV</button>
          <button class="btn btn--sm" :disabled="exportingUsers" @click="exportUsers('xlsx')">XLSX</button>
          <button class="btn btn--sm" :disabled="exportingUsers" @click="exportUsers('json')">JSON</button>
        </div>
      </div>

      <div class="row" style="gap: 10px; flex-wrap: wrap; margin-bottom: 12px">
        <input class="input" v-model="search"
               placeholder="Поиск по логину, почте или телефону" style="flex: 1; min-width: 240px" />
        <select class="select" v-model="typeFilter" style="max-width: 200px">
          <option value="">Все</option>
          <option value="client">Клиенты</option>
          <option value="employee">Сотрудники</option>
        </select>
      </div>

      <DataFetchPanel
        v-if="usersLoadError && users.length"
        class="table-state"
        compact
        :error="usersLoadError"
        error-title="Список пользователей загружен не полностью"
        @retry="reloadUsersScreen"
      />

      <DataFetchPanel
        v-else-if="loadingUsers && users.length"
        class="table-state"
        compact
        loading
        loading-title="Обновление пользователей"
        loading-text="Подтягиваем актуальную выборку по пользователям."
      />

      <DataFetchPanel
        v-if="loadingUsers && !users.length"
        loading
        loading-title="Загрузка пользователей"
        loading-text="Подтягиваем список пользователей и роли."
      />

      <DataFetchPanel
        v-else-if="usersLoadError && !users.length"
        :error="usersLoadError"
        error-title="Не удалось загрузить пользователей"
        @retry="reloadUsersScreen"
      />

      <div v-else class="table-wrap table-wrap--cards clients-table-wrap">
        <table class="table table--responsive-cards">
          <thead>
            <tr>
              <th>Логин</th>
              <th>Почта</th>
              <th>Телефон</th>
              <th>Тип</th>
              <th>Должность</th>
              <th>Создан</th>
              <th v-if="auth.isManager"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td data-label="Логин"><b>{{ u.username }}</b></td>
              <td>{{ u.email || '—' }}</td>
              <td>{{ u.phone || '—' }}</td>
              <td>
                <span class="tag" :class="u.user_type === 'employee' ? 'tag--panel' : 'tag--accent'">
                  {{ u.user_type === 'employee' ? 'Сотрудник' : 'Клиент' }}
                </span>
              </td>
              <td>{{ u.role_name || '—' }}</td>
              <td class="muted">
                {{ formatDate(u.created_at) }}
              </td>
              <td v-if="auth.isManager" class="table-actions-cell" data-label="Действия">
                <button class="btn btn--sm" @click="openAssign(u)">Назначить</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!users.length" class="empty">Пользователи не найдены.</div>

      <ListPagination
        v-if="totalUsers > users.length"
        :count="totalUsers"
        :page="userPage"
        :visible-count="users.length"
        :page-size="userPageSize"
        label="пользователей"
        @change="setUserPage"
        @change-page-size="setUserPageSize"
      />
    </div>

    <div v-if="assignOpen" class="modal" @click.self="assignOpen = false">
      <div class="panel panel--light modal__card stack">
        <div class="row row--between">
          <h2 class="h3">Назначение должности</h2>
          <button class="btn btn--sm" @click="assignOpen = false">×</button>
        </div>
        <p class="muted">
          Пользователь <b>{{ assignUser?.username }}</b>.
          Установите тип учётной записи и должность.
        </p>
        <div class="field">
          <label>Тип учётной записи</label>
          <select class="select" v-model="assignForm.user_type">
            <option value="client">Клиент</option>
            <option value="employee">Сотрудник</option>
          </select>
        </div>
        <div class="field" v-if="assignForm.user_type === 'employee'">
          <label>Должность</label>
          <select class="select" v-model.number="assignForm.role_id">
            <option :value="null">— без должности —</option>
            <option v-for="r in roles" :key="r.id" :value="r.id">
              {{ r.name }}
            </option>
          </select>
        </div>
        <div v-if="assignError" class="error">{{ assignError }}</div>
        <div class="row" style="justify-content: flex-end; gap: 8px; margin-top: 12px">
          <button class="btn btn--sm" @click="assignOpen = false">Отмена</button>
          <button class="btn btn--primary btn--sm" @click="saveAssign" :disabled="assignLoading">
            {{ assignLoading ? 'Сохранение…' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import api from '../api'
import { exportEntityData } from '../api/exports'
import DataFetchPanel from '../components/DataFetchPanel.vue'
import ListPagination from '../components/ListPagination.vue'
import { useAuthStore } from '../store/auth'
import { DEFAULT_PAGE_SIZE, LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import { formatDate } from '@/utils/formatters'
import { extractError, useToastsStore } from '../store/toasts'

const auth = useAuthStore()
const toasts = useToastsStore()
const users = ref([])
const roles = ref([])
const search = ref('')
const typeFilter = ref('')
const totalUsers = ref(0)
const userPage = ref(1)
const userPageSize = ref(DEFAULT_PAGE_SIZE)
const exportingUsers = ref(false)
const loadingUsers = ref(false)
const usersLoadError = ref('')

const assignOpen = ref(false)
const assignUser = ref(null)
const assignLoading = ref(false)
const assignError = ref('')
const assignForm = reactive({ user_type: 'client', role_id: null })

async function loadUsers() {
  loadingUsers.value = true
  usersLoadError.value = ''
  try {
    const { data } = await api.get('/users/', { params: listParams() })
    const payload = unpackPaginated(data)
    users.value = payload.items
    totalUsers.value = payload.count
  } catch (err) {
    usersLoadError.value = extractError(err, 'Не удалось загрузить пользователей')
    toasts.error(usersLoadError.value)
  } finally {
    loadingUsers.value = false
  }
}

async function loadRoles() {
  try {
    const response = await api.get('/user-roles/', {
      params: { page_size: LOOKUP_PAGE_SIZE },
    })
    roles.value = unpackPaginated(response.data).items
  } catch (err) {
    roles.value = []
    toasts.error(extractError(err, 'Не удалось загрузить роли пользователей'))
  }
}

function listParams () {
  const params = {
    page: userPage.value,
    page_size: userPageSize.value,
  }
  if (search.value.trim()) params.search = search.value.trim()
  if (typeFilter.value) params.user_type = typeFilter.value
  return params
}

function userExportParams () {
  const params = listParams()
  delete params.page
  delete params.page_size
  return params
}

function setUserPage (page) {
  if (page < 1 || page === userPage.value) return
  userPage.value = page
}

function setUserPageSize (size) {
  if (!size || size === userPageSize.value) return
  userPageSize.value = size
}

function openAssign(u) {
  assignUser.value = u
  assignForm.user_type = u.user_type || 'client'
  assignForm.role_id = u.role ?? null
  assignError.value = ''
  assignOpen.value = true
}

async function exportUsers (format) {
  exportingUsers.value = true
  try {
    await exportEntityData(
      '/users/export/',
      format,
      userExportParams(),
      `users.${format}`,
    )
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось выгрузить пользователей'))
  } finally {
    exportingUsers.value = false
  }
}

async function saveAssign() {
  assignLoading.value = true; assignError.value = ''
  try {
    await api.post(`/users/${assignUser.value.id}/assign_role/`, {
      user_type: assignForm.user_type,
      role_id: assignForm.user_type === 'employee' ? assignForm.role_id : null,
    })
    assignOpen.value = false
    await loadUsers()
  } catch (e) {
    assignError.value = e.response?.data?.detail
      || 'Не удалось сохранить. Проверьте права доступа.'
  } finally {
    assignLoading.value = false
  }
}

async function reloadUsersScreen() {
  await Promise.all([loadUsers(), loadRoles()])
}

let filtersTimer = null

watch([search, typeFilter], () => {
  if (filtersTimer) clearTimeout(filtersTimer)
  filtersTimer = setTimeout(async () => {
    userPage.value = 1
    await loadUsers()
  }, 250)
})

watch(userPage, async () => {
  await loadUsers()
})

watch(userPageSize, async () => {
  if (userPage.value !== 1) {
    userPage.value = 1
    return
  }
  await loadUsers()
})

onBeforeUnmount(() => {
  if (filtersTimer) clearTimeout(filtersTimer)
})

onMounted(async () => {
  await reloadUsersScreen()
})
</script>

<style scoped>
.clients-section-head {
  margin-bottom: 14px;
}

.clients-section-head + .row .input {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.16);
  box-shadow: 0 10px 22px rgba(16, 55, 52, 0.08);
  border-radius: 24px;
}

.clients-section-head + .row .input::placeholder {
  color: rgba(21, 56, 57, 0.64);
}

.clients-section-head + .row .select {
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.16);
  border-radius: 24px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 10px 22px rgba(16, 55, 52, 0.08);
  background-image:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)),
    linear-gradient(45deg, transparent 50%, rgba(21, 56, 57, 0.62) 50%),
    linear-gradient(135deg, rgba(21, 56, 57, 0.62) 50%, transparent 50%);
  background-position:
    0 0,
    calc(100% - 24px) calc(50% - 3px),
    calc(100% - 18px) calc(50% - 3px);
  background-size:
    100% 100%,
    6px 6px,
    6px 6px;
  background-repeat: no-repeat;
}

.clients-section-head + .row .input:hover,
.clients-section-head + .row .select:hover {
  border-color: rgba(21, 56, 57, 0.26);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 12px 26px rgba(16, 55, 52, 0.1);
}

.clients-section-head + .row .input:focus,
.clients-section-head + .row .select:focus {
  border-color: rgba(46, 139, 87, 0.42);
  box-shadow:
    0 0 0 1px rgba(46, 139, 87, 0.18),
    0 0 0 5px rgba(120, 216, 206, 0.18),
    0 12px 24px rgba(16, 55, 52, 0.12);
}

.clients-table-wrap .table {
  min-width: 980px;
}

.clients-table-wrap {
  min-height: 420px;
}

.clients-table-wrap .tag,
.clients-table-wrap .tag--accent,
.clients-table-wrap .tag--panel {
  justify-content: center;
  min-width: 126px;
  min-height: 40px;
  padding: 8px 16px;
  border-radius: var(--r-pill);
  border: 1px solid rgba(21, 56, 57, 0.16);
  background: var(--grad-control-light);
  color: var(--c-page-text);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.2;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 8px 18px rgba(16, 55, 52, 0.08);
}

.clients-table-wrap .btn--sm {
  min-width: 126px;
}

.modal {
  z-index: 1000;
}

.modal__card {
  width: min(480px, 100%);
  max-height: calc(100vh - 32px);
  overflow: auto;
}

@media (max-width: 720px) {
  .clients-table-wrap .table {
    min-width: 860px;
  }

  .clients-table-wrap .table td:nth-child(2)::before {
    content: 'Почта';
  }

  .clients-table-wrap .table td:nth-child(3)::before {
    content: 'Телефон';
  }

  .clients-table-wrap .table td:nth-child(4)::before {
    content: 'Тип';
  }

  .clients-table-wrap .table td:nth-child(5)::before {
    content: 'Должность';
  }

  .clients-table-wrap .table td:nth-child(6)::before {
    content: 'Создан';
  }

  .clients-table-wrap .btn--sm {
    min-width: 0;
    width: 100%;
  }
}
</style>
