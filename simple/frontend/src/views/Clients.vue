<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">КЛИЕНТЫ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">База клиентов</h1>
    </div>

    <div class="panel panel--light">
      <div class="row row--between" style="margin-bottom: 12px">
        <input class="input" v-model="search"
               placeholder="Поиск по логину / email / телефону" style="flex: 1" />
      </div>
      <table class="table">
        <thead><tr>
          <th>Логин</th><th>Email</th><th>Телефон</th>
          <th>Тип</th><th>Роль</th><th>Создан</th>
        </tr></thead>
        <tbody>
          <tr v-for="u in filtered" :key="u.id">
            <td><b>{{ u.username }}</b></td>
            <td>{{ u.email }}</td>
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
          </tr>
        </tbody>
      </table>
      <div v-if="!filtered.length" class="empty">Клиентов не найдено.</div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const users = ref([])
const search = ref('')

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return users.value
  return users.value.filter(u =>
    u.username?.toLowerCase().includes(q) ||
    u.email?.toLowerCase().includes(q) ||
    (u.phone || '').includes(q)
  )
})

onMounted(async () => {
  const { data } = await api.get('/users/')
  users.value = data.results || data
})
</script>
