<template>
  <section v-if="auth.isManager" class="stack">
    <div class="hero admin-hero">
      <div class="row row--between admin-hero__row" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">АДМИНИСТРИРОВАНИЕ</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            Панель администратора
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Управление сотрудниками, ролями и справочниками системы.
            Доступ разрешён только администраторам и менеджерам.
          </div>
        </div>
        <div class="admin-role-badge">
          <span class="tag tag--accent admin-role-pill">
            {{ auth.roleLabel }}
          </span>
        </div>
      </div>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light admin-panel">
        <div class="row row--between">
          <span class="tag tag--accent">Пользователи</span>
          <span class="muted">всего: {{ counters.total }}</span>
        </div>
        <h2 class="h2" style="margin-top: 8px">Назначение должностей</h2>
        <p class="muted" style="margin: 4px 0 12px">
          Открывает полный список пользователей с возможностью менять тип
          учётной записи и должность.
        </p>
        <div class="row" style="gap: 8px">
          <button class="btn btn--primary" @click="openAssign()">
            Назначить должность
          </button>
          <router-link to="/clients" class="btn">
            Открыть список →
          </router-link>
        </div>
      </div>

      <div class="panel admin-panel">
        <span class="tag tag--panel">Справочник</span>
        <h2 class="h2" style="color: #fff; margin-top: 8px">
          Должности сотрудников
        </h2>
        <p style="color: rgba(255,255,255,.75); margin: 4px 0 12px">
          Создавайте и редактируйте роли — администратор, менеджер, агент.
          Роли управляют правами доступа в системе.
        </p>
        <button class="btn btn--accent" @click="rolesOpen = true">
          Управлять ролями
        </button>
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head admin-section-head">
        <div>
          <div class="surface-head__meta">Команда агентства</div>
          <h2 class="h2">Сотрудники агентства</h2>
        </div>
        <div class="row" style="gap: 10px; flex-wrap: wrap">
          <div class="surface-head__caption">Показано: {{ employees.length }} из {{ counters.employees }}</div>
          <router-link to="/clients" class="btn btn--sm">Все →</router-link>
        </div>
      </div>
      <div class="table-wrap admin-table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Логин</th>
              <th>Почта</th>
              <th>Должность</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in employees" :key="u.id">
              <td><b>{{ u.username }}</b></td>
              <td>{{ u.email || '—' }}</td>
              <td>{{ u.role_name || '—' }}</td>
              <td style="text-align: right">
                <button class="btn btn--sm" @click="openAssign(u)">
                  Редактировать
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!employees.length" class="empty">Сотрудники ещё не назначены.</div>
    </div>

    <div v-if="assignOpen" class="modal" @click.self="assignOpen = false">
      <div class="panel panel--light modal__card stack">
        <div class="row row--between">
          <h2 class="h3">Назначение должности</h2>
          <button class="btn btn--sm" @click="assignOpen = false">×</button>
        </div>
        <div v-if="!assignUser" class="field">
          <label>Поиск пользователя</label>
          <input
            class="input"
            v-model="assignSearch"
            placeholder="Логин, почта или телефон" />
        </div>
        <div v-if="!assignUser" class="field">
          <label>Пользователь</label>
          <select class="select" v-model.number="assignUserId">
            <option :value="null" disabled>— выберите пользователя —</option>
            <option v-for="u in assignableUsers" :key="u.id" :value="u.id">
              {{ u.username }} — {{ u.email || 'без почты' }}
            </option>
          </select>
          <div class="muted" style="margin-top: 6px">
            Найдено: {{ assignableTotal }}
          </div>
        </div>
        <div v-else class="muted">
          Пользователь <b>{{ assignUser.username }}</b>.
        </div>
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
        <div class="row" style="justify-content: flex-end; gap: 8px">
          <button class="btn btn--sm" @click="assignOpen = false">Отмена</button>
          <button class="btn btn--primary btn--sm"
                  :disabled="assignLoading || (!assignUser && !assignUserId)"
                  @click="saveAssign">
            {{ assignLoading ? 'Сохранение…' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="rolesOpen" class="modal" @click.self="rolesOpen = false">
      <div class="panel panel--light modal__card stack">
        <div class="row row--between">
          <h2 class="h3">Справочник должностей</h2>
          <button class="btn btn--sm" @click="rolesOpen = false">×</button>
        </div>
        <div class="table-wrap admin-roles-wrap">
          <table class="table">
            <thead>
              <tr><th>Код</th><th>Название</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="r in roles" :key="r.id">
                <td><code>{{ r.code }}</code></td>
                <td>{{ r.name }}</td>
                <td style="text-align: right">
                  <button class="btn btn--sm btn--danger"
                          @click="removeRole(r)">
                    Удалить
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <form class="row admin-role-form" style="gap: 8px" @submit.prevent="createRole">
          <input class="input" v-model="newRole.code" placeholder="код (agent)"
                 style="flex: 0 0 140px" required />
          <input class="input" v-model="newRole.name" placeholder="название (Агент)"
                 style="flex: 1" required />
          <button class="btn btn--accent btn--sm" type="submit">Добавить</button>
        </form>
        <div v-if="rolesError" class="error">{{ rolesError }}</div>
      </div>
    </div>
  </section>

  <section v-else class="panel panel--light empty">
    <h2 class="h2">Доступ ограничен</h2>
    <p class="muted">
      Этот раздел доступен только администраторам и менеджерам агентства.
    </p>
    <router-link to="/" class="btn">На главную</router-link>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import api from '../api'
import { useAuthStore } from '../store/auth'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const employees = ref([])
const assignableUsers = ref([])
const assignableTotal = ref(0)
const roles = ref([])

const counters = reactive({
  total: 0,
  employees: 0,
  clients: 0,
  superusers: 0,
})

const assignOpen = ref(false)
const assignUser = ref(null)
const assignUserId = ref(null)
const assignLoading = ref(false)
const assignError = ref('')
const assignSearch = ref('')
const assignForm = reactive({ user_type: 'client', role_id: null })

function openAssign (u) {
  assignUser.value = u || null
  assignUserId.value = u?.id ?? null
  assignForm.user_type = u?.user_type || 'client'
  assignForm.role_id = u?.role ?? null
  assignSearch.value = ''
  assignError.value = ''
  assignOpen.value = true
  if (!u) {
    loadAssignableUsers()
  }
}

async function saveAssign () {
  assignLoading.value = true
  assignError.value = ''
  try {
    const id = assignUser.value?.id || assignUserId.value
    await api.post(`/users/${id}/assign_role/`, {
      user_type: assignForm.user_type,
      role_id: assignForm.user_type === 'employee'
        ? assignForm.role_id : null,
    })
    assignOpen.value = false
    await Promise.all([
      loadPreviewEmployees(),
      loadAssignableUsers(),
      loadCounters(),
    ])
  } catch (e) {
    assignError.value = e.response?.data?.detail
      || 'Не удалось сохранить. Проверьте права доступа.'
  } finally {
    assignLoading.value = false
  }
}

const rolesOpen = ref(false)
const rolesError = ref('')
const newRole = reactive({ code: '', name: '' })

async function createRole () {
  rolesError.value = ''
  try {
    await api.post('/user-roles/', {
      code: newRole.code, name: newRole.name,
    })
    newRole.code = ''; newRole.name = ''
    await loadRoles()
  } catch (e) {
    rolesError.value = e.response?.data
      ? Object.values(e.response.data).flat().join(' ')
      : 'Не удалось создать роль.'
  }
}

async function removeRole (r) {
  if (!confirm(`Удалить должность «${r.name}»?`)) return
  try {
    await api.delete(`/user-roles/${r.id}/`)
    await loadRoles()
  } catch (e) {
    rolesError.value = e.response?.data?.detail
      || 'Не удалось удалить.'
  }
}

async function fetchUserCount (params = {}) {
  const { data } = await api.get('/users/', {
    params: { page: 1, page_size: 1, ...params },
  })
  return Number(data?.count ?? (data?.results || data || []).length)
}

async function loadCounters () {
  const [total, employeesCount, clientsCount, superusersCount] = await Promise.all([
    fetchUserCount(),
    fetchUserCount({ user_type: 'employee' }),
    fetchUserCount({ user_type: 'client' }),
    fetchUserCount({ is_superuser: true }),
  ])
  counters.total = total
  counters.employees = employeesCount
  counters.clients = clientsCount
  counters.superusers = superusersCount
}

async function loadPreviewEmployees () {
  const { data } = await api.get('/users/', {
    params: { user_type: 'employee', page: 1, page_size: 8 },
  })
  const payload = unpackPaginated(data)
  employees.value = payload.items
}

async function loadAssignableUsers () {
  const params = { page: 1, page_size: LOOKUP_PAGE_SIZE }
  if (assignSearch.value.trim()) params.search = assignSearch.value.trim()
  const { data } = await api.get('/users/', { params })
  const payload = unpackPaginated(data)
  assignableUsers.value = payload.items
  assignableTotal.value = payload.count
}
async function loadRoles () {
  try {
    const { data } = await api.get('/user-roles/', {
      params: { page_size: LOOKUP_PAGE_SIZE },
    })
    roles.value = unpackPaginated(data).items
  } catch {
    roles.value = []
  }
}

let assignSearchTimer = null

watch(assignSearch, () => {
  if (!assignOpen.value || assignUser.value) return
  if (assignSearchTimer) clearTimeout(assignSearchTimer)
  assignSearchTimer = setTimeout(() => {
    loadAssignableUsers()
  }, 250)
})

onBeforeUnmount(() => {
  if (assignSearchTimer) clearTimeout(assignSearchTimer)
})

onMounted(async () => {
  await Promise.all([loadPreviewEmployees(), loadRoles(), loadCounters()])
})
</script>

<style scoped>
.admin-hero {
  position: relative;
  overflow: visible;
  background:
    linear-gradient(135deg, rgba(22, 88, 84, 0.92), rgba(18, 56, 53, 0.82)),
    radial-gradient(circle at top right, rgba(99, 208, 197, 0.12), transparent 24%);
  padding: 24px 28px;
}

.admin-hero__row {
  align-items: flex-start;
}

.admin-role-badge {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-left: auto;
}

.admin-role-pill {
  font-size: 13px;
  padding: 6px 14px;
}

.admin-panel {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.admin-panel > .tag {
  align-self: flex-start;
  width: fit-content;
  max-width: 100%;
}

.admin-panel:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-glow);
}

.modal {
  z-index: 80;
}

.modal__card {
  width: 100%;
  max-width: 560px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}

.admin-section-head {
  margin-bottom: 14px;
}

.admin-table-wrap .table {
  min-width: 720px;
}

.admin-roles-wrap .table {
  min-width: 460px;
}

.admin-role-form {
  flex-wrap: wrap;
}

code {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: var(--r-pill);
  border: 1px solid rgba(99, 208, 197, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: #effffd;
  font-size: 12px;
}

@media (max-width: 960px) {
  .admin-role-badge {
    justify-content: flex-start;
    margin-left: 0;
  }

  .admin-panel {
    min-height: auto;
  }
}
</style>
