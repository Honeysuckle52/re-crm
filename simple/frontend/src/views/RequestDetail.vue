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
          </div>
          <div v-if="auth.isStaff" class="row" style="gap: 6px; flex-wrap: wrap">
            <!-- Ключевая точка автоматизации:
                 Accept match → бэк отправляет событие request_client_matched,
                 которое в signals.py закрывает связанные задачи
                 (поиск клиентов / подбор объектов), пишет статистику
                 сотрудника и запускает письмо клиенту. -->
            <button class="btn btn--sm btn--accent"
                    :disabled="busyMatchId === m.id"
                    title="Подтвердить: клиенту подходит этот вариант. Запустит цепочку автоматических действий."
                    @click="acceptMatch(m)">
              {{ busyMatchId === m.id ? 'Обрабатываем…' : 'Подтвердить' }}
            </button>
            <button class="btn btn--sm btn--danger"
                    :disabled="busyMatchId === m.id"
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
            <b>{{ t.title }}</b>
            <div class="muted" style="font-size: 12px">
              Исполнитель: {{ t.assignee_username }} ·
              Срок: {{ t.due_date ? formatDate(t.due_date) : '—' }}
              <span v-if="t.is_overdue" class="tag" style="background: #fee; color: #c2554a">
                просрочено
              </span>
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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import InfoRow from '../components/InfoRow.vue'
import { useAuthStore } from '../store/auth'
import { useWorkloadStore } from '../store/workload'
import { useToasts } from '../store/toasts'
import { takeRequest as apiTakeRequest,
         acceptRequestMatch } from '../api/tasks'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const workload = useWorkloadStore()
const toasts = useToasts()

const request = ref(null)
const availableProperties = ref([])
const requestTasks = ref([])
const attachPropertyId = ref(null)
const attachNote = ref('')
const busyMatchId = ref(null)

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
  const res = await apiTakeRequest(route.params.id)
  if (!res.ok) {
    toasts.error(res.error || 'Не удалось взять заявку.')
    return
  }
  toasts.success('Заявка взята в работу')
  await load()
}

async function closeRequest () {
  if (!confirm('Закрыть заявку?')) return
  try {
    await api.post(`/requests/${route.params.id}/close/`)
    toasts.info('Заявка закрыта, связанные задачи завершены автоматически')
    workload.bumpAfterAction()
    await load()
  } catch (err) {
    toasts.error(err.response?.data?.detail || 'Не удалось закрыть заявку.')
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
    toasts.success('Вариант добавлен в подборку')
    await load()
  } catch (err) {
    toasts.error(err.response?.data?.detail || 'Не удалось добавить вариант.')
  }
}

async function detachProperty (m) {
  if (!confirm('Убрать объект из подборки?')) return
  try {
    await api.post(`/requests/${route.params.id}/detach_property/`, {
      match_id: m.id,
    })
    await load()
  } catch (err) {
    toasts.error(err.response?.data?.detail || 'Не удалось убрать вариант.')
  }
}

/**
 * Подтвердить вариант из подборки. Бэк запускает цепочку:
 *   - закрывает связанные задачи «Поиск клиентов / Подбор объектов»;
 *   - пишет KPI сотрудника;
 *   - ставит письмо клиенту в очередь (SMTP, шаблон property_matched).
 */
async function acceptMatch (m) {
  busyMatchId.value = m.id
  const res = await acceptRequestMatch(route.params.id, m.id)
  busyMatchId.value = null
  if (!res.ok) {
    toasts.error(res.error || 'Не удалось подтвердить вариант.')
    return
  }
  toasts.success(
    'Вариант подтверждён. Задачи по подбору закрыты, клиенту отправлено письмо.'
  )
  await load()
}

function formatMoney (v) {
  return v ? new Intl.NumberFormat('ru-RU').format(v) : '—'
}
function formatDate (s) {
  return new Date(s).toLocaleString('ru-RU')
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
.task-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--c-paper-2);
  border-radius: var(--r-sm);
}
.select--sm, .input { font-size: 13px; }
</style>
