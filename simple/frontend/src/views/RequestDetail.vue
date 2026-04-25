<template>
  <section class="stack" v-if="request">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">ЗАЯВКА №{{ request.id }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ request.operation_type_name }} ·
            {{ request.client_username }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Создана {{ formatDate(request.created_at) }} ·
            <span class="tag" :class="statusClass">{{ request.status_name }}</span>
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button v-if="auth.isStaff && !request.agent"
                  class="btn btn--accent" @click="takeRequest">
            Взять в работу
          </button>
          <button v-if="request.can_close"
                  class="btn btn--danger" @click="closeRequest">
            Закрыть заявку
          </button>
        </div>
      </div>
    </div>

    <!-- Уведомления (тосты) -->
    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="'toast--' + toast.type">
        {{ toast.message }}
      </div>
    </Transition>

    <div class="grid grid--2">
      <!-- Параметры заявки -->
      <div class="panel panel--light">
        <h2 class="h3">Параметры заявки</h2>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Клиент" :value="request.client_username" />
          <InfoRow label="Агент" :value="request.agent_username || 'не назначен'" />
          <InfoRow label="Операция" :value="request.operation_type_name" />
          <InfoRow label="Тип недвижимости" :value="request.property_type || '—'" />
          <InfoRow label="Комнат" :value="request.rooms_count || '—'" />
          <InfoRow label="Бюджет"
            :value="formatMoney(request.min_price) + '–' + formatMoney(request.max_price) + ' ₽'" />
          <InfoRow label="Закрыта" :value="request.closed_at ? formatDate(request.closed_at) : '—'" />
        </div>
      </div>

      <!-- Основной объект + пожелания -->
      <div class="panel panel--light">
        <h2 class="h3">Желаемый объект</h2>
        <div v-if="request.property" class="stack" style="margin-top: 12px">
          <router-link :to="`/properties/${request.property}`" class="link">
            {{ request.property_title || 'Объект №' + request.property }}
          </router-link>
          <div class="muted">Клиент оставил заявку на конкретный объект.</div>
        </div>
        <div v-else class="muted" style="margin-top: 12px">
          Заявка на подбор: конкретный объект не указан — агент подбирает варианты.
        </div>

        <h2 class="h3" style="margin-top: 20px">Пожелания клиента</h2>
        <p style="white-space: pre-wrap; margin-top: 8px">
          {{ request.description || 'Пожелания не указаны.' }}
        </p>
      </div>
    </div>

    <!-- Подборка вариантов -->
    <div class="panel panel--light">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <h2 class="h3">Подборка вариантов ({{ request.matches?.length || 0 }})</h2>
        <div v-if="auth.isStaff" class="row" style="gap: 8px">
          <select class="select select--sm" v-model.number="attachPropertyId">
            <option :value="null" disabled>— выберите объект —</option>
            <option v-for="p in availableProperties" :key="p.id" :value="p.id">
              {{ p.title || 'Объект №' + p.id }} · {{ formatMoney(p.price) }} ₽
            </option>
          </select>
          <input class="input" v-model="attachNote"
                 placeholder="Комментарий агента" />
          <button class="btn btn--sm btn--accent" @click="attachProperty"
                  :disabled="!attachPropertyId">
            + Добавить
          </button>
        </div>
      </div>

      <div v-if="request.matches?.length" class="match-list" style="margin-top: 14px">
        <div v-for="m in request.matches" :key="m.id" class="match">
          <div class="stack" style="gap: 4px; flex: 1">
            <router-link :to="`/properties/${m.property}`" class="link">
              {{ m.property_title || 'Объект №' + m.property }}
            </router-link>
            <div class="muted" style="font-size: 13px">
              {{ formatMoney(m.property_price) }} ₽ · предложил {{ m.agent_username }}
            </div>
            <div v-if="m.agent_note" style="font-size: 13px">
              «{{ m.agent_note }}»
            </div>
            <div v-if="m.is_offered && !m.is_rejected" class="confirmed-badge">
              Подтверждён
            </div>
          </div>
          <div v-if="auth.isStaff" class="match-actions">
            <button class="btn btn--sm btn--accent"
                    :disabled="confirmingId === m.id"
                    @click="confirmProperty(m)"
                    title="Подтвердить выбор клиента (закроет задачи подбора и отправит письмо)">
              Подтвердить
            </button>
            <button class="btn btn--sm btn--danger"
                    @click="detachProperty(m)">Убрать</button>
          </div>
        </div>
      </div>
      <div v-else class="muted" style="margin-top: 12px">
        Варианты ещё не предложены.
      </div>
    </div>

    <!-- Задачи по заявке -->
    <div class="panel panel--light">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <h2 class="h3">Задачи по заявке ({{ requestTasks.length }})</h2>
        <router-link v-if="auth.isStaff" to="/tasks" class="btn btn--sm">
          Все задачи
        </router-link>
      </div>
      <div v-if="requestTasks.length" class="stack" style="margin-top: 12px">
        <div v-for="t in requestTasks" :key="t.id" class="task-row">
          <div class="stack" style="gap: 2px; flex: 1">
            <div class="row" style="gap: 8px; align-items: center">
              <b>{{ t.title }}</b>
              <span v-if="t.is_auto_closed" class="auto-badge" title="Закрыта автоматически">
                авто
              </span>
            </div>
            <div class="muted" style="font-size: 12px">
              <span class="tag tag--type">{{ t.task_type_display || t.task_type }}</span>
              Исполнитель: {{ t.assignee_username }} ·
              Срок: {{ t.due_date ? formatDate(t.due_date) : '—' }}
              <span v-if="t.is_overdue" class="tag" style="background: #fee; color: #c2554a">
                просрочено
              </span>
            </div>
            <div v-if="t.result" class="result-text">
              Результат: {{ t.result }}
            </div>
          </div>
          <span class="tag tag--accent">{{ t.status_name }}</span>
        </div>
      </div>
      <div v-else class="muted" style="margin-top: 12px">
        Задач пока нет.
      </div>
    </div>
  </section>
  <div v-else class="empty">Загрузка заявки…</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import InfoRow from '../components/InfoRow.vue'
import { useAuthStore } from '../store/auth'
// Общие форматтеры вынесены в utils/formatters.
import { formatMoney, formatDate } from '@/utils/formatters'
import {
  takeRequest as takeRequestAction,
  acceptRequestMatch,
} from '../api/tasks'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const request = ref(null)
const availableProperties = ref([])
const requestTasks = ref([])
const attachPropertyId = ref(null)
const attachNote = ref('')
const confirmingId = ref(null)

// Тост-уведомления
const toast = reactive({ show: false, message: '', type: 'success' })
function showToast(message, type = 'success') {
  toast.message = message
  toast.type = type
  toast.show = true
  setTimeout(() => { toast.show = false }, 5000)
}

const statusClass = computed(() => {
  const code = request.value?.status_code
  if (code === 'closed') return 'tag--panel'
  return 'tag--accent'
})

async function load () {
  const reqId = route.params.id
  const calls = [
    api.get(`/requests/${reqId}/`),
    api.get('/properties/'),
  ]
  if (auth.isStaff) {
    calls.push(api.get('/tasks/', { params: { request: reqId } })
      .catch(() => ({ data: [] })))
  }
  const [r, p, t] = await Promise.all(calls)
  request.value = r.data
  availableProperties.value = p.data.results || p.data
  if (t) {
    const all = t.data.results || t.data
    requestTasks.value = all.filter(x => x.request === Number(reqId))
  } else {
    requestTasks.value = []
  }
}

async function takeRequest () {
  const result = await takeRequestAction(route.params.id)
  if (!result.ok) {
    showToast(result.error || 'Не удалось взять заявку', 'error')
    return
  }
  showToast('Заявка взята в работу')
  await load()
}

async function closeRequest () {
  if (!confirm('Закрыть заявку?')) return
  try {
    await api.post(`/requests/${route.params.id}/close/`)
    showToast('Заявка закрыта')
    await load()
  } catch (err) {
    showToast(err.response?.data?.detail || 'Не удалось закрыть заявку', 'error')
  }
}

async function attachProperty () {
  if (!attachPropertyId.value) return
  try {
    await api.post(`/requests/${route.params.id}/attach_property/`, {
      property_id: attachPropertyId.value,
      agent_note: attachNote.value,
    })
    attachPropertyId.value = null
    attachNote.value = ''
    showToast('Объект добавлен в подборку')
    await load()
  } catch (err) {
    showToast(err.response?.data?.detail || 'Не удалось добавить объект', 'error')
  }
}

async function detachProperty (m) {
  if (!confirm('Убрать объект из подборки?')) return
  try {
    await api.post(`/requests/${route.params.id}/detach_property/`, {
      match_id: m.id,
    })
    showToast('Объект убран из подборки')
    await load()
  } catch (err) {
    showToast(err.response?.data?.detail || 'Не удалось убрать объект', 'error')
  }
}

async function confirmProperty (m) {
  confirmingId.value = m.id
  try {
    const result = await acceptRequestMatch(route.params.id, m.id)
    if (!result.ok) {
      showToast(result.error || 'Не удалось подтвердить вариант', 'error')
      return
    }
    showToast(result.data?.detail || 'Вариант подтверждён, задачи закрыты, письмо отправлено')
    await load()
  } finally {
    confirmingId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.link { color: var(--c-accent); font-weight: 500; }
.link:hover { text-decoration: underline; }
.match-list {
  display: flex; flex-direction: column; gap: 10px;
}
.match {
  display: flex; align-items: center; gap: 12px;
  background: var(--c-paper-2); padding: 12px 16px;
  border-radius: var(--r-sm);
}
.match-actions {
  display: flex; gap: 6px; flex-shrink: 0;
}
.task-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--c-paper-2);
  border-radius: var(--r-sm);
}
.select--sm, .input { font-size: 13px; }

/* Подтверждённый бейдж */
.confirmed-badge {
  display: inline-block;
  font-size: 11px; font-weight: 700;
  text-transform: uppercase;
  background: #c8e6c9; color: #2e7d32;
  padding: 2px 8px; border-radius: 4px;
  margin-top: 4px;
}

/* Автозакрытие */
.auto-badge {
  font-size: 10px; font-weight: 700;
  text-transform: uppercase;
  background: #e3f2fd; color: #1565c0;
  padding: 2px 6px; border-radius: 4px;
}

/* Тип задачи */
.tag--type {
  background: #e8f4f3; color: #1a5a52; font-size: 10px;
  margin-right: 6px;
}

/* Результат задачи */
.result-text {
  font-size: 12px; color: #546e7a;
  margin-top: 4px; font-style: italic;
}

/* Тосты */
.toast {
  position: fixed;
  top: 20px; right: 20px;
  z-index: 1000;
  padding: 14px 20px;
  border-radius: 8px;
  font-size: 14px; font-weight: 500;
  box-shadow: 0 4px 16px rgba(0,0,0,.15);
  max-width: 400px;
}
.toast--success { background: #0f3a33; color: #fff; }
.toast--error { background: #c2554a; color: #fff; }
.toast-enter-active, .toast-leave-active {
  transition: all .3s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0; transform: translateX(30px);
}
</style>
