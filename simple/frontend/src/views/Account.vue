<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">ЛИЧНЫЙ КАБИНЕТ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">
        {{ auth.displayName }}
      </h1>
      <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
        {{ auth.user?.email }} · {{ auth.roleLabel }}
      </div>
      <!-- Приветственный баннер после регистрации -->
      <div v-if="showWelcome"
           style="margin-top: 14px; background: rgba(61, 219, 199, .15);
                  border: 1px solid rgba(61, 219, 199, .35);
                  color: #cdf6ee; padding: 10px 14px; border-radius: 8px;
                  font-size: 13px">
        Добро пожаловать! Дополните договорные данные ниже — и договор
        будет готов к подписанию без ручного заполнения.
      </div>
    </div>

    <!-- Тосты -->
    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="'toast--' + toast.type">
        {{ toast.message }}
      </div>
    </Transition>

    <div class="grid grid--2">
      <div class="panel panel--light stack">
        <h2 class="h3">Основные данные</h2>
        <InfoRow label="Номер"              :value="auth.user?.id" />
        <InfoRow label="Логин"              :value="auth.user?.username" />
        <InfoRow label="Электронная почта"  :value="auth.user?.email" />
        <InfoRow label="Телефон"            :value="auth.user?.phone || '—'" />
        <InfoRow label="Тип учётной записи" :value="auth.user?.user_type === 'employee' ? 'Сотрудник' : 'Клиент'" />
        <InfoRow label="Должность"          :value="auth.user?.role_name || '—'" />
        <InfoRow label="Почта подтверждена"   :value="auth.user?.is_email_verified ? 'да' : 'нет'" />
        <InfoRow label="Телефон подтверждён"  :value="auth.user?.is_phone_verified ? 'да' : 'нет'" />
      </div>

      <div class="panel">
        <h2 class="h3" style="color: #fff">Безопасность</h2>
        <p style="color: rgba(255,255,255,.8); font-size: 14px">
          Доступ к системе защищён токенами: основной токен обновляется автоматически
          по обновляющему токену. Пароль хранится в зашифрованном виде,
          ключи внешних сервисов хранятся только на сервере и никогда не попадают
          в браузер.
        </p>
        <button class="btn btn--danger" @click="logout">Выйти из учётной записи</button>
      </div>
    </div>

    <!-- Договорные данные: только для клиентов. Сотруднику этот блок
         не нужен, т.к. ClientProfile у сотрудников не создаётся. -->
    <div v-if="auth.user?.user_type === 'client'" class="panel panel--light stack">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <h2 class="h3">Договорные данные</h2>
          <div class="muted" style="font-size: 13px; margin-top: 4px">
            Используются для автоматического заполнения договора.
            Просмотреть их кроме вас могут только сотрудники агентства.
          </div>
        </div>
        <!-- Индикатор полноты профиля — помогает клиенту понять,
             что осталось дозаполнить для договора. -->
        <div class="completeness" :class="`is-${completeness.state}`">
          <div class="completeness__bar">
            <div class="completeness__fill"
                 :style="{ width: completeness.percent + '%' }"></div>
          </div>
          <div class="completeness__label">
            Заполнено на {{ completeness.percent }}%
          </div>
        </div>
      </div>

      <div v-if="loadingProfile" class="muted">Загрузка…</div>

      <form v-else class="stack" @submit.prevent="saveProfile">
        <div class="grid grid--2">
          <div class="field">
            <label>Фамилия</label>
            <input class="input" v-model.trim="profile.last_name" required />
          </div>
          <div class="field">
            <label>Имя</label>
            <input class="input" v-model.trim="profile.first_name" required />
          </div>
          <div class="field">
            <label>Отчество</label>
            <input class="input" v-model.trim="profile.middle_name" />
          </div>
          <div class="field">
            <label>Дата рождения</label>
            <input class="input" type="date" v-model="profile.birth_date" />
          </div>
          <div class="field">
            <label>Серия паспорта</label>
            <input class="input" v-model.trim="profile.passport_series"
                   maxlength="4" inputmode="numeric" />
          </div>
          <div class="field">
            <label>Номер паспорта</label>
            <input class="input" v-model.trim="profile.passport_number"
                   maxlength="6" inputmode="numeric" />
          </div>
          <div class="field" style="grid-column: 1 / -1">
            <label>Кем выдан</label>
            <input class="input" v-model.trim="profile.passport_issued_by" />
          </div>
          <div class="field">
            <label>Дата выдачи</label>
            <input class="input" type="date" v-model="profile.passport_issued_date" />
          </div>
          <div class="field">
            <label>Код подразделения</label>
            <input class="input" v-model.trim="profile.passport_code"
                   placeholder="000-000" maxlength="7" />
          </div>
          <div class="field" style="grid-column: 1 / -1">
            <label>Адрес регистрации</label>
            <textarea class="textarea" v-model="profile.registration_address" rows="2"></textarea>
          </div>
          <div class="field" style="grid-column: 1 / -1">
            <label>Фактический адрес</label>
            <textarea class="textarea" v-model="profile.actual_address" rows="2"></textarea>
          </div>
        </div>

        <div class="row" style="justify-content: flex-end; gap: 8px">
          <button class="btn btn--accent" type="submit" :disabled="saving">
            {{ saving ? 'Сохраняем…' : 'Сохранить' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../store/auth'
import InfoRow from '../components/InfoRow.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// Приветственный баннер показываем только один раз — после регистрации
// мы редиректим на /account?welcome=1.
const showWelcome = ref(!!route.query.welcome)

const loadingProfile = ref(false)
const saving = ref(false)
const profileId = ref(null)
const profile = reactive({
  first_name: '',
  last_name: '',
  middle_name: '',
  birth_date: '',
  passport_series: '',
  passport_number: '',
  passport_issued_by: '',
  passport_issued_date: '',
  passport_code: '',
  registration_address: '',
  actual_address: '',
})

const toast = reactive({ show: false, message: '', type: 'success' })
function showToast (message, type = 'success') {
  toast.message = message
  toast.type = type
  toast.show = true
  setTimeout(() => { toast.show = false }, 4000)
}

// ---------------------------------------------------------------------------
// Индикатор полноты договорного профиля.
// Поля, которые реально используются в PDF-договоре (см. key/documents.py):
// ФИО, дата рождения, серия+номер+кем/когда выдан+код, адрес регистрации.
// Остальное — бонусом.
// ---------------------------------------------------------------------------
const REQUIRED_FIELDS = [
  'first_name', 'last_name', 'birth_date',
  'passport_series', 'passport_number',
  'passport_issued_by', 'passport_issued_date', 'passport_code',
  'registration_address',
]

const completeness = computed(() => {
  const filled = REQUIRED_FIELDS.filter(k => !!profile[k]).length
  const percent = Math.round((filled / REQUIRED_FIELDS.length) * 100)
  let state = 'low'
  if (percent >= 100) state = 'full'
  else if (percent >= 60) state = 'mid'
  return { percent, state }
})

// ---------------------------------------------------------------------------
// Загрузка и сохранение профиля
// ---------------------------------------------------------------------------
async function loadProfile () {
  if (auth.user?.user_type !== 'client') return
  loadingProfile.value = true
  try {
    const { data } = await api.get('/client-profiles/')
    const list = data.results || data
    const mine = list[0] // для клиента get_queryset фильтрует по user=self
    if (mine) {
      profileId.value = mine.id
      for (const key of Object.keys(profile)) {
        if (mine[key] != null) profile[key] = mine[key]
      }
    }
  } catch (err) {
    showToast('Не удалось загрузить профиль', 'error')
  } finally {
    loadingProfile.value = false
  }
}

async function saveProfile () {
  if (!profileId.value) {
    showToast('Профиль ещё не создан — обратитесь к менеджеру', 'error')
    return
  }
  saving.value = true
  // Пустые строки преобразуем в null, чтобы в БД лежало NULL и
  // генератор договора выводил прочерк, а не пустую строку.
  const payload = { user: auth.user.id }
  for (const [k, v] of Object.entries(profile)) {
    payload[k] = v === '' ? null : v
  }
  try {
    await api.patch(`/client-profiles/${profileId.value}/`, payload)
    showToast('Профиль сохранён')
  } catch (err) {
    const detail = err.response?.data
    const msg = typeof detail === 'object'
      ? Object.values(detail).flat().join(' ')
      : detail || 'Не удалось сохранить профиль'
    showToast(msg, 'error')
  } finally {
    saving.value = false
  }
}

function logout () {
  auth.logout()
  router.push('/login')
}

onMounted(loadProfile)
</script>

<style scoped>
.completeness {
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}
.completeness__bar {
  width: 180px;
  height: 6px;
  background: #e2e8e6;
  border-radius: 999px;
  overflow: hidden;
}
.completeness__fill {
  height: 100%;
  background: #8aa5a0;
  transition: width .25s ease, background .25s ease;
}
.completeness.is-mid .completeness__fill  { background: #f5b567; }
.completeness.is-full .completeness__fill { background: #0f3a33; }
.completeness__label {
  font-size: 12px;
  color: var(--c-text-muted);
  font-weight: 600;
}

.toast {
  position: fixed;
  top: 20px; right: 20px;
  z-index: 1000;
  padding: 14px 20px;
  border-radius: 8px;
  font-size: 14px; font-weight: 500;
  box-shadow: 0 4px 16px rgba(0,0,0,.15);
}
.toast--success { background: #0f3a33; color: #fff; }
.toast--error { background: #c2554a; color: #fff; }
.toast-enter-active, .toast-leave-active { transition: all .3s ease; }
.toast-enter-from, .toast-leave-to {
  opacity: 0; transform: translateX(30px);
}
</style>
