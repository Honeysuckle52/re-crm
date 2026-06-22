<template>
  <section class="auth">
    <div class="panel auth__card">
      <div class="hero__eyebrow">РЕГИСТРАЦИЯ</div>
      <h1 class="auth__title">Создание учётной записи</h1>

      <ol class="rstep">
        <li class="rstep__item"
            :class="{ 'rstep__item--active': step === 1, 'rstep__item--done': step > 1 }">
          <span class="rstep__num">1</span>
          <span class="rstep__label">Аккаунт</span>
        </li>
        <li class="rstep__item"
            :class="{ 'rstep__item--active': step === 2, 'rstep__item--done': step > 2 }">
          <span class="rstep__num">2</span>
          <span class="rstep__label">Договорные данные</span>
          <span class="rstep__hint">необязательно</span>
        </li>
        <li class="rstep__item"
            :class="{ 'rstep__item--active': step === 3 }">
          <span class="rstep__num">3</span>
          <span class="rstep__label">Подтверждение</span>
        </li>
      </ol>

      <form v-if="step === 1" class="stack" @submit.prevent="goToStep2">
        <div class="grid grid--2">
          <div class="field">
            <label>Фамилия</label>
            <input class="input" v-model.trim="form.last_name" required
                   autocomplete="family-name" />
          </div>
          <div class="field">
            <label>Имя</label>
            <input class="input" v-model.trim="form.first_name" required
                   autocomplete="given-name" />
          </div>
          <div class="field" style="grid-column: 1 / -1">
            <label>Отчество <span class="muted">(необязательно)</span></label>
            <input class="input" v-model.trim="form.middle_name"
                   autocomplete="additional-name" />
          </div>
        </div>
        <div class="field">
          <label>Электронная почта</label>
          <input class="input" type="email" v-model.trim="form.email" required
                 autocomplete="email" />
        </div>
        <div class="field">
          <label>Телефон</label>
          <input class="input" type="tel" v-model.trim="form.phone"
                 placeholder="+7XXXXXXXXXX" autocomplete="tel" maxlength="12"
                 inputmode="tel" @input="formatPhoneInput" />
        </div>
        <div class="field">
          <label>Пароль</label>
          <input class="input" type="password" v-model="form.password"
                 required autocomplete="new-password" minlength="8" />
          <div class="muted" style="font-size: 12px; margin-top: 4px">
            Минимум 8 символов. Не должен быть слишком простым.
          </div>
        </div>
        <div class="field">
          <label>Подтверждение пароля</label>
          <input class="input" type="password" v-model="form.password_confirm"
                 required autocomplete="new-password" minlength="8" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button class="btn btn--accent" type="submit">
          Продолжить
        </button>
        <router-link to="/login" class="btn btn--ghost btn--sm"
                     style="margin-top: 8px">
          У меня уже есть учётная запись
        </router-link>
      </form>

      <form v-else-if="step === 2" class="stack" @submit.prevent="submit">
        <p class="muted" style="color: rgba(255,255,255,.7)">
          Эти данные нужны для автоматического заполнения договора.
          Для физлица укажите паспорт, для юрлица — ИНН компании. Если сейчас нет данных под рукой — пропустите шаг, заполните
          позже в личном кабинете.
        </p>

        <div class="field">
          <label>Тип клиента</label>
          <select class="select" v-model="form.client_kind">
            <option value="individual">Физическое лицо</option>
            <option value="company">Юридическое лицо</option>
          </select>
        </div>

        <template v-if="form.client_kind === 'individual'">
          <div class="grid grid--2">
            <div class="field">
              <label>Серия паспорта</label>
              <input class="input" v-model.trim="form.passport_series"
                     maxlength="4" placeholder="0000" inputmode="numeric"
                     @input="limitDigits('passport_series', 4)" />
            </div>
            <div class="field">
              <label>Номер паспорта</label>
              <input class="input" v-model.trim="form.passport_number"
                     maxlength="6" placeholder="000000" inputmode="numeric"
                     @input="limitDigits('passport_number', 6)" />
            </div>
          </div>

          <div class="field">
            <label>Кем выдан</label>
            <input class="input" v-model.trim="form.passport_issued_by" />
          </div>
          <div class="grid grid--2">
            <div class="field">
              <label>Дата выдачи</label>
              <input class="input" type="date"
                     v-model="form.passport_issued_date" />
            </div>
            <div class="field">
              <label>Код подразделения</label>
              <input class="input" v-model.trim="form.passport_code"
                     placeholder="000-000" maxlength="7"
                     @input="formatPassportCode" />
            </div>
          </div>
        </template>

        <template v-else>
          <div class="field">
            <label>ИНН компании</label>
            <input class="input" v-model.trim="form.company_inn"
                   maxlength="10" placeholder="0000000000" inputmode="numeric"
                   @input="limitDigits('company_inn', 10)" />
          </div>
        </template>

        <div v-if="error" class="error">{{ error }}</div>

        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--ghost" type="button" @click="step = 1"
                  :disabled="loading">
            ← Назад
          </button>
          <button class="btn" type="button" @click="submitWithoutExtras"
                  :disabled="loading">
            {{ loading ? '…' : 'Пропустить и зарегистрироваться' }}
          </button>
          <button class="btn btn--accent" type="submit" :disabled="loading">
            {{ loading ? 'Создание…' : 'Зарегистрироваться' }}
          </button>
        </div>
      </form>

      <form v-else class="stack" @submit.prevent="verifyEmailCode">
        <p class="muted" style="color: rgba(255,255,255,.7)">
          Мы отправили код подтверждения на {{ registeredEmail || form.email }}.
          Введите 6 цифр из письма, чтобы активировать аккаунт.
        </p>
        <div class="field">
          <label>Код из письма</label>
          <input class="input auth__code-input" v-model.trim="verificationCode"
                 inputmode="numeric" maxlength="6" autocomplete="one-time-code"
                 required @input="formatVerificationCode" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button class="btn btn--accent" type="submit" :disabled="loading">
            {{ loading ? 'Проверяем…' : 'Подтвердить аккаунт' }}
          </button>
          <button class="btn" type="button" @click="resendCode" :disabled="loading || resendLoading">
            {{ resendLoading ? 'Отправляем…' : 'Отправить код ещё раз' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()

const step = ref(1)
const loading = ref(false)
const resendLoading = ref(false)
const error = ref('')
const verificationCode = ref('')
const registeredEmail = ref('')
const verificationToken = ref('')

const form = reactive({
  email: '',
  phone: '',
  password: '',
  password_confirm: '',
  last_name: '',
  first_name: '',
  middle_name: '',
  client_kind: 'individual',
  passport_series: '',
  passport_number: '',
  passport_issued_by: '',
  passport_issued_date: '',
  passport_code: '',
  company_inn: '',
})

const PERSON_NAME_RE = /[A-Za-zА-Яа-яЁё]/

function digitsOnly (value) {
  return String(value || '').replace(/\D/g, '')
}

function todayIso () {
  return new Date().toISOString().slice(0, 10)
}

function normalizeRussianPhone (value) {
  const digits = digitsOnly(value)
  if (!digits) return ''
  if (digits.length === 11 && ['7', '8'].includes(digits[0])) {
    return `+7${digits.slice(1)}`
  }
  if (digits.length === 10) {
    return `+7${digits}`
  }
  return ''
}

function phoneInputValue (value) {
  const digits = digitsOnly(value)
  if (!digits) return ''
  if (digits[0] === '8') return `+7${digits.slice(1, 11)}`
  if (digits[0] === '7') return `+7${digits.slice(1, 11)}`
  return `+7${digits.slice(0, 10)}`
}

function formatPhoneInput () {
  form.phone = phoneInputValue(form.phone)
}

function limitDigits (field, max) {
  form[field] = digitsOnly(form[field]).slice(0, max)
}

function formatPassportCode () {
  const digits = digitsOnly(form.passport_code).slice(0, 6)
  form.passport_code = digits.length > 3
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

function validateAccountStep () {
  const phone = normalizeRussianPhone(form.phone)
  const checks = [
    validatePersonName(form.last_name, 'Фамилия'),
    validatePersonName(form.first_name, 'Имя'),
    validatePersonName(form.middle_name, 'Отчество', { required: false }),
  ]
  const failed = checks.find(Boolean)
  if (failed) return failed
  if (form.phone && !phone) {
    return 'Телефон должен быть российским номером в формате +7XXXXXXXXXX.'
  }
  if (phone) form.phone = phone
  if (form.password.length < 8) {
    return 'Пароль должен быть не короче 8 символов.'
  }
  if (form.password !== form.password_confirm) {
    return 'Пароли не совпадают.'
  }
  return ''
}

function validateContractStep () {
  if (form.client_kind === 'company') {
    if (!/^\d{10}$/.test(form.company_inn)) {
      return 'ИНН компании должен состоять из 10 цифр.'
    }
    return ''
  }

  const today = todayIso()
  if (!/^\d{4}$/.test(form.passport_series)) return 'Серия паспорта должна состоять из 4 цифр.'
  if (!/^\d{6}$/.test(form.passport_number)) return 'Номер паспорта должен состоять из 6 цифр.'
  if (String(form.passport_issued_by || '').trim().length < 5 || !PERSON_NAME_RE.test(form.passport_issued_by)) {
    return 'Кем выдан: укажите название органа выдачи минимум на 5 символов.'
  }
  if (!form.passport_issued_date) return 'Дата выдачи паспорта обязательна.'
  if (form.passport_issued_date > today) return 'Дата выдачи паспорта не может быть в будущем.'
  if (!/^\d{3}-\d{3}$/.test(form.passport_code)) {
    return 'Код подразделения должен быть в формате 000-000.'
  }
  return ''
}

function goToStep2 () {
  error.value = ''
  const validationError = validateAccountStep()
  if (validationError) {
    error.value = validationError
    return
  }
  step.value = 2
}

function basePayload () {
  const payload = {
    email: form.email,
    password: form.password,
    password_confirm: form.password_confirm,
    first_name: form.first_name,
    last_name: form.last_name,
    client_kind: form.client_kind,
  }
  const phone = normalizeRussianPhone(form.phone)
  if (phone) payload.phone = phone
  if (form.middle_name) payload.middle_name = form.middle_name
  return payload
}

function contractPayload () {
  const requisites = {
    contract_data_required: true,
  }
  if (form.client_kind === 'company') {
    requisites.company_inn = form.company_inn
  } else {
    requisites.passport_series = form.passport_series
    requisites.passport_number = form.passport_number
    requisites.passport_issued_by = form.passport_issued_by
    requisites.passport_issued_date = form.passport_issued_date
    requisites.passport_code = form.passport_code
  }
  return stripEmpty(requisites)
}

async function doRegister (extended) {
  error.value = ''
  const accountError = validateAccountStep()
  if (accountError) {
    error.value = accountError
    step.value = 1
    return
  }
  if (extended) {
    const contractError = validateContractStep()
    if (contractError) {
      error.value = contractError
      return
    }
  }

  loading.value = true
  try {
    const payload = {
      ...basePayload(),
      ...(extended ? contractPayload() : {}),
    }
    const result = await auth.register(payload)
    registeredEmail.value = payload.email
    verificationToken.value = result.verification_token || ''
    verificationCode.value = ''
    step.value = 3
    if (result.email_sent === false) {
      error.value = 'Не удалось доставить письмо с кодом. Нажмите «Отправить код ещё раз» или свяжитесь с поддержкой.'
    } else {
      error.value = ''
    }
  } catch (e) {
    const data = e.response?.data || {}
    const msg = flattenErrors(data) || 'Не удалось создать учётную запись'
    error.value = msg
    if (data.email || data.password || data.phone || data.first_name || data.last_name) {
      step.value = 1
    }
  } finally {
    loading.value = false
  }
}

function submit () { return doRegister(true) }
function submitWithoutExtras () { return doRegister(false) }

function formatVerificationCode () {
  verificationCode.value = digitsOnly(verificationCode.value).slice(0, 6)
}

async function verifyEmailCode () {
  error.value = ''
  formatVerificationCode()
  if (verificationCode.value.length !== 6) {
    error.value = 'Введите 6 цифр из письма.'
    return
  }
  loading.value = true
  try {
    await auth.verifyEmail({
      token: verificationToken.value,
      code: verificationCode.value,
    })
    await auth.login(form.email, form.password)
    router.push('/account?welcome=1')
  } catch (e) {
    error.value = flattenErrors(e.response?.data) || 'Не удалось подтвердить email.'
  } finally {
    loading.value = false
  }
}

async function resendCode () {
  error.value = ''
  resendLoading.value = true
  try {
    await auth.resendEmailCode(verificationToken.value)
    error.value = 'Новый код отправлен на почту.'
  } catch (e) {
    error.value = flattenErrors(e.response?.data) || 'Не удалось отправить код ��овторно.'
  } finally {
    resendLoading.value = false
  }
}

function stripEmpty (obj) {
  const out = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v === '' || v == null) continue
    out[k] = v
  }
  return out
}

function flattenErrors (data) {
  if (!data || typeof data !== 'object') return ''
  return Object.values(data)
    .flatMap((value) => Array.isArray(value) ? value : [value])
    .filter(Boolean)
    .join(' ')
}
</script>

<style scoped>
.auth {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 28px 18px;
}

.auth::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 18%, rgba(120, 216, 206, 0.22), transparent 26%),
    radial-gradient(circle at 78% 8%, rgba(226, 248, 245, 0.14), transparent 22%);
  pointer-events: none;
}

.auth__card {
  position: relative;
  width: min(560px, 100%);
}

.auth__card .field > .select {
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

.auth__card .field > .select option {
  background: #f4f8fa;
  color: var(--c-page-text);
}

.auth__title {
  margin: 18px 0 12px;
  font-size: clamp(28px, 4vw, 34px);
  color: var(--c-text);
}

.auth__code-input {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-align: center;
}

.rstep {
  display: flex;
  align-items: center;
  gap: 18px;
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
}
.rstep__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--c-text-muted);
  font-size: 13px;
}
.rstep__num {
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(120, 216, 206, 0.2);
  background: rgba(255, 255, 255, 0.08);
  color: var(--c-ink-soft);
  font-weight: 700;
  font-size: 12px;
}
.rstep__item--active {
  color: var(--c-text);
}
.rstep__item--active .rstep__num {
  background: var(--grad-accent);
  color: #123330;
  border-color: rgba(255, 255, 255, 0.16);
  box-shadow: 0 0 18px rgba(120, 216, 206, 0.14);
}
.rstep__item--done .rstep__num {
  background: rgba(120, 216, 206, 0.18);
  color: #efffff;
  border-color: rgba(120, 216, 206, 0.2);
}
.rstep__hint {
  font-size: 11px;
  font-style: italic;
  opacity: 0.75;
}

@media (max-width: 640px) {
  .rstep {
    align-items: flex-start;
    gap: 12px;
    flex-direction: column;
  }
}
</style>
