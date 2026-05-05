<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">ПОЛЬЗОВАТЕЛИ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">База пользователей</h1>
      <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
        Клиенты и сотрудники агентства. Назначение должностей доступно
        администратору или менеджеру.
      </div>
    </div>

    <div class="panel panel--light">
      <div class="surface-head clients-section-head">
        <div>
          <div class="surface-head__meta">Реестр пользователей</div>
          <h2 class="h3">Поиск и фильтрация</h2>
        </div>
        <div class="surface-head__caption">С ролями: {{ usersWithRoleCount }}</div>
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

      <div class="table-wrap clients-table-wrap">
        <table class="table">
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
            <tr v-for="u in filtered" :key="u.id">
              <td><b>{{ u.username }}</b></td>
              <td>{{ u.email || '—' }}</td>
              <td>{{ u.phone || '—' }}</td>
              <td>
                <span class="tag" :class="u.user_type === 'employee' ? 'tag--panel' : 'tag--accent'">
                  {{ u.user_type === 'employee' ? 'Сотрудник' : 'Клиент' }}
                </span>
              </td>
              <td>{{ u.role_name || '—' }}</td>
              <td class="muted">
                {{ new Date(u.created_at).toLocaleDateString('ru-RU') }}
              </td>
              <td v-if="auth.isManager">
                <button class="btn btn--sm" @click="openAssign(u)">Назначить</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!filtered.length" class="empty">Пользователи не найдены.</div>
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
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const users = ref([])
const roles = ref([])
const search = ref('')
const typeFilter = ref('')

const assignOpen = ref(false)
const assignUser = ref(null)
const assignLoading = ref(false)
const assignError = ref('')
const assignForm = reactive({ user_type: 'client', role_id: null })

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return users.value.filter((u) => {
    if (typeFilter.value && u.user_type !== typeFilter.value) return false
    if (!q) return true
    return (
      u.username?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      (u.phone || '').includes(q)
    )
  })
})

const usersWithRoleCount = computed(() => (
  users.value.filter((u) => u.role_name).length
))

async function load() {
  const [u, r] = await Promise.all([
    api.get('/users/'),
    api.get('/user-roles/').catch(() => ({ data: [] })),
  ])
  users.value = u.data.results || u.data
  roles.value = r.data.results || r.data
}

function openAssign(u) {
  assignUser.value = u
  assignForm.user_type = u.user_type || 'client'
  assignForm.role_id = u.role ?? null
  assignError.value = ''
  assignOpen.value = true
}

async function saveAssign() {
  assignLoading.value = true; assignError.value = ''
  try {
    await api.post(`/users/${assignUser.value.id}/assign_role/`, {
      user_type: assignForm.user_type,
      role_id: assignForm.user_type === 'employee' ? assignForm.role_id : null,
    })
    assignOpen.value = false
    await load()
  } catch (e) {
    assignError.value = e.response?.data?.detail
      || 'Не удалось сохранить. Проверьте права доступа.'
  } finally {
    assignLoading.value = false
  }
}

onMounted(load)
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
}

.clients-section-head + .row .input::placeholder {
  color: rgba(21, 56, 57, 0.64);
}

.clients-section-head + .row .select {
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.16);
  box-shadow: 0 10px 22px rgba(16, 55, 52, 0.08);
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
  box-shadow: 0 12px 26px rgba(16, 55, 52, 0.1);
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
}
</style>
