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
            :class="{ 'rstep__item--active': step === 2 }">
          <span class="rstep__num">2</span>
          <span class="rstep__label">Договорные данные</span>
          <span class="rstep__hint">необязательно</span>
        </li>
      </ol>

      <form v-if="step === 1" class="stack" @submit.prevent="goToStep2">
        <div class="field">
          <label>Логин</label>
          <input class="input" v-model.trim="form.username" required
                 autocomplete="username" />
        </div>
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
          <input class="input" v-model.trim="form.phone" placeholder="+7..."
                 autocomplete="tel" />
        </div>
        <div class="field">
          <label>Пароль</label>
          <input class="input" type="password" v-model="form.password"
                 required autocomplete="new-password" minlength="8" />
          <div class="muted" style="font-size: 12px; margin-top: 4px">
            Минимум 8 символов. Не должен быть слишком простым.
          </div>
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

      <form v-else class="stack" @submit.prevent="submit">
        <p class="muted" style="color: rgba(255,255,255,.7)">
          Эти данные нужны для автоматического заполнения договора.
          Если сейчас нет под рукой паспорта — пропустите шаг, заполните
          позже в личном кабинете.
        </p>

        <div class="field">
          <label>Дата рождения</label>
          <input class="input" type="date" v-model="form.birth_date" />
        </div>

        <div class="grid grid--2">
          <div class="field">
            <label>Серия паспорта</label>
            <input class="input" v-model.trim="form.passport_series"
                   maxlength="4" placeholder="0000" inputmode="numeric" />
          </div>
          <div class="field">
            <label>Номер паспорта</label>
            <input class="input" v-model.trim="form.passport_number"
                   maxlength="6" placeholder="000000" inputmode="numeric" />
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
                   placeholder="000-000" maxlength="7" />
          </div>
        </div>

        <div class="field">
          <label>Адрес регистрации</label>
          <textarea class="textarea" v-model="form.registration_address"
                    rows="2"></textarea>
        </div>
        <div class="field">
          <label>Фактический адрес</label>
          <textarea class="textarea" v-model="form.actual_address"
                    rows="2" placeholder="Можно оставить пустым, если совпадает"></textarea>
        </div>

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
const error = ref('')

const form = reactive({
  username: '',
  email: '',
  phone: '',
  password: '',
  last_name: '',
  first_name: '',
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

function goToStep2 () {
  error.value = ''
  if (form.password.length < 8) {
    error.value = 'Пароль должен быть не короче 8 символов.'
    return
  }
  step.value = 2
}

async function doRegister (extended) {
  loading.value = true
  error.value = ''
  try {
    const payload = extended ? stripEmpty(form) : {
      username: form.username,
      email: form.email,
      phone: form.phone,
      password: form.password,
      first_name: form.first_name,
      last_name: form.last_name,
      ...(form.middle_name ? { middle_name: form.middle_name } : {}),
    }
    await auth.register(payload)
    router.push('/account?welcome=1')
  } catch (e) {
    const data = e.response?.data || {}
    error.value = Object.values(data).flat().join(' ')
      || 'Не удалось создать учётную запись'
    if (data.username || data.email || data.password || data.phone) {
      step.value = 1
    }
  } finally {
    loading.value = false
  }
}

function submit () { return doRegister(true) }
function submitWithoutExtras () { return doRegister(false) }

function stripEmpty (obj) {
  const out = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v === '' || v == null) continue
    out[k] = v
  }
  return out
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

.auth__title {
  margin: 18px 0 12px;
  font-size: clamp(28px, 4vw, 34px);
  color: var(--c-text);
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
