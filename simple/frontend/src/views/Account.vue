<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">ЛИЧНЫЙ КАБИНЕТ</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">
        {{ auth.displayName }}
      </h1>
      <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
        {{ auth.user?.email }}<template v-if="!auth.isClient"> · {{ auth.roleLabel }}</template>
      </div>
      <div v-if="showWelcome"
           style="margin-top: 14px; background: rgba(61, 219, 199, .15);
                  border: 1px solid rgba(61, 219, 199, .35);
                  color: #cdf6ee; padding: 10px 14px; border-radius: 8px;
                  font-size: 13px">
        Добро пожаловать! Дополните договорные данные ниже — и договор
        будет готов к подписанию без ручного заполнения.
      </div>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light stack">
        <h2 class="h3">Основные данные</h2>
        <InfoRow v-if="!auth.isClient"
                 label="Логин"
                 :value="auth.user?.username" />
        <InfoRow label="Электронная почта"  :value="auth.user?.email" />
        <InfoRow label="Телефон"            :value="auth.user?.phone || '—'" />
        <InfoRow v-if="!auth.isClient"
                 label="Тип учётной записи"
                 :value="auth.user?.user_type === 'employee' ? 'Сотрудник' : 'Клиент'" />
        <InfoRow v-if="!auth.isClient"
                 label="Должность"
                 :value="auth.user?.role_name || '—'" />
        <InfoRow label="Почта подтверждена"   :value="auth.user?.is_email_verified ? 'да' : 'нет'" />
        <InfoRow v-if="auth.isClient"
                 label="Тип клиента"
                 :value="clientKindLabel" />
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

    <div v-if="auth.user?.user_type === 'client'" class="panel panel--light stack">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <h2 class="h3">Договорные данные</h2>
          <div class="muted" style="font-size: 13px; margin-top: 4px">
            Используются для автоматического заполнения договора.
            Просмотреть их кроме вас могут только сотрудники агентства.
          </div>
        </div>
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
            <label>Тип клиента</label>
            <select class="select" v-model="profile.client_kind">
              <option value="individual">Физическое лицо</option>
              <option value="company">Юридическое лицо</option>
            </select>
          </div>
          <template v-if="profile.client_kind === 'individual'">
            <div class="field">
              <label>Серия паспорта</label>
              <input class="input" v-model.trim="profile.passport_series"
                     maxlength="4" inputmode="numeric"
                     @input="limitDigits('passport_series', 4)" />
            </div>
            <div class="field">
              <label>Номер паспорта</label>
              <input class="input" v-model.trim="profile.passport_number"
                     maxlength="6" inputmode="numeric"
                     @input="limitDigits('passport_number', 6)" />
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
                     placeholder="000-000" maxlength="7"
                     @input="formatPassportCode" />
            </div>
          </template>
          <div v-else class="field">
            <label>ИНН компании</label>
            <input class="input" v-model.trim="profile.company_inn"
                   maxlength="10" inputmode="numeric" placeholder="0000000000"
                   @input="limitDigits('company_inn', 10)" />
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
import { extractError, useToastsStore } from '../store/toasts'
import InfoRow from '../components/InfoRow.vue'
import { unpackPaginated } from '@/utils/paginated'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const toasts = useToastsStore()

const showWelcome = ref(!!route.query.welcome)

const loadingProfile = ref(false)
const saving = ref(false)
const profileId = ref(null)
const profile = reactive({
  first_name: '',
  last_name: '',
  middle_name: '',
  client_kind: 'individual',
  passport_series: '',
  passport_number: '',
  passport_issued_by: '',
  passport_issued_date: '',
  passport_code: '',
  company_inn: '',
  registration_address: '',
  actual_address: '',
})
const clientKindLabel = computed(() => {
  if (profile.client_kind === 'company') return 'Юридическое лицо'
  if (profile.client_kind === 'individual') return 'Физическое лицо'
  return '—'
})

const BASE_REQUIRED_FIELDS = ['first_name', 'last_name', 'registration_address']
const INDIVIDUAL_REQUIRED_FIELDS = [
  'passport_series', 'passport_number',
  'passport_issued_by', 'passport_issued_date', 'passport_code',
]
const COMPANY_REQUIRED_FIELDS = ['company_inn']
const PERSON_NAME_RE = /[A-Za-zА-Яа-яЁё]/
const ADDRESS_MIN_LENGTH = 10

const completeness = computed(() => {
  const fields = [
    ...BASE_REQUIRED_FIELDS,
    ...(profile.client_kind === 'company'
      ? COMPANY_REQUIRED_FIELDS
      : INDIVIDUAL_REQUIRED_FIELDS),
  ]
  const filled = fields.filter(k => !!profile[k]).length
  const percent = Math.round((filled / fields.length) * 100)
  let state = 'low'
  if (percent >= 100) state = 'full'
  else if (percent >= 60) state = 'mid'
  return { percent, state }
})

function digitsOnly (value) {
  return String(value || '').replace(/\D/g, '')
}

function todayIso () {
  return new Date().toISOString().slice(0, 10)
}

function limitDigits (field, max) {
  profile[field] = digitsOnly(profile[field]).slice(0, max)
}

function formatPassportCode () {
  const digits = digitsOnly(profile.passport_code).slice(0, 6)
  profile.passport_code = digits.length > 3
    ? `${digits.slice(0, 3)}-${digits.slice(3)}`
    : digits
}

function validatePersonName (value, label, { required = true } = {}) {
  const normalized = String(value || '').trim().replace(/\s+/g, ' ')
  if (!normalized) return required ? `${label}: заполните поле.` : ''
  if (normalized.length < 2) return `${label}: минимум 2 символа.`
  if (!PERSON_NAME_RE.test(normalized)) return `${label}: укажите буквы.`
  return ''
}

function validateAddress (value, label, { required = false } = {}) {
  const normalized = String(value || '').trim().replace(/\s+/g, ' ')
  if (!normalized) return required ? `${label}: заполните адрес.` : ''
  if (normalized.length < ADDRESS_MIN_LENGTH) {
    return `${label}: минимум ${ADDRESS_MIN_LENGTH} символов.`
  }
  if (!PERSON_NAME_RE.test(normalized) || !/\d/.test(normalized)) {
    return `${label}: укажите улицу или населённый пункт и номер дома.`
  }
  return ''
}

function validateProfile () {
  const commonChecks = [
    validatePersonName(profile.last_name, 'Фамилия'),
    validatePersonName(profile.first_name, 'Имя'),
    validatePersonName(profile.middle_name, 'Отчество', { required: false }),
    validateAddress(profile.registration_address, 'Адрес регистрации', { required: true }),
    validateAddress(profile.actual_address, 'Фактический адрес'),
  ]
  const commonFailed = commonChecks.find(Boolean)
  if (commonFailed) return commonFailed

  if (profile.client_kind === 'company') {
    if (!/^\d{10}$/.test(profile.company_inn)) {
      return 'ИНН компании должен состоять из 10 цифр.'
    }
    return ''
  }

  const today = todayIso()
  if (!/^\d{4}$/.test(profile.passport_series)) return 'Серия паспорта должна состоять из 4 цифр.'
  if (!/^\d{6}$/.test(profile.passport_number)) return 'Номер паспорта должен состоять из 6 цифр.'
  if (String(profile.passport_issued_by || '').trim().length < 5 || !PERSON_NAME_RE.test(profile.passport_issued_by)) {
    return 'Кем выдан: укажите название органа выдачи минимум на 5 символов.'
  }
  if (!profile.passport_issued_date) return 'Дата выдачи паспорта обязательна.'
  if (profile.passport_issued_date > today) return 'Дата выдачи паспорта не может быть в будущем.'
  if (!/^\d{3}-\d{3}$/.test(profile.passport_code)) {
    return 'Код подразделения должен быть в формате 000-000.'
  }
  return ''
}

async function loadProfile () {
  if (auth.user?.user_type !== 'client') return
  loadingProfile.value = true
  try {
    const { data } = await api.get('/client-profiles/', {
      params: { page_size: 1 },
    })
    const list = unpackPaginated(data).items
    const mine = list[0]
    if (mine) {
      profileId.value = mine.id
      for (const key of Object.keys(profile)) {
        profile[key] = mine[key] ?? ''
      }
      profile.client_kind = mine.client_kind || 'individual'
    }
  } catch (err) {
    toasts.error('Не удалось загрузить профиль')
  } finally {
    loadingProfile.value = false
  }
}

async function saveProfile () {
  if (!profileId.value) {
    toasts.error('Профиль ещё не создан — обратитесь к менеджеру')
    return
  }
  const validationError = validateProfile()
  if (validationError) {
    toasts.error(validationError)
    return
  }
  saving.value = true
  const payload = { user: auth.user.id }
  for (const [k, v] of Object.entries(profile)) {
    payload[k] = v === '' ? null : v
  }
  try {
    await api.patch(`/client-profiles/${profileId.value}/`, payload)
    toasts.success('Профиль сохранён')
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось сохранить профиль'))
  } finally {
    saving.value = false
  }
}

async function logout () {
  await auth.logout()
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
  overflow: hidden;
  border-radius: 999px;
  border: 1px solid rgba(120, 216, 206, 0.18);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.22);
}
.completeness__fill {
  height: 100%;
  background: rgba(46, 159, 152, 0.72);
  box-shadow: 0 0 18px rgba(120, 216, 206, 0.2);
  transition: width 0.25s ease, background 0.25s ease;
}
.completeness.is-mid .completeness__fill  { background: var(--c-warning); }
.completeness.is-full .completeness__fill { background: var(--c-accent-2); }
.completeness__label {
  font-size: 12px;
  color: var(--c-text-muted);
  font-weight: 600;
}

.panel--light .field > .select {
  color-scheme: light;
  background-color: #f4f8fa;
  background-image:
    var(--grad-control-light),
    linear-gradient(45deg, transparent 50%, var(--c-accent) 50%),
    linear-gradient(135deg, var(--c-accent) 50%, transparent 50%);
  background-position:
    0 0,
    calc(100% - 24px) calc(50% - 3px),
    calc(100% - 18px) calc(50% - 3px);
  background-size: 100% 100%, 6px 6px, 6px 6px;
  background-repeat: no-repeat;
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.18);
}

.panel--light .field > .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

</style>
