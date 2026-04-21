<!--
  Двухшаговая регистрация клиента.

  Цель:
    1) Максимально упростить первый экран: логин, пароль, ФИО —
       и уже этого достаточно, чтобы войти в личный кабинет.
    2) Параллельно собрать договорные данные (паспорт, адреса,
       дату рождения), чтобы PDF-договор (key/documents.py) мог
       автоматически заполняться без повторного ввода.

  Все поля шага 2 — опциональные: их можно пропустить и дозаполнить
  позже в /account. На бэке обрабатывается в :class:`RegisterSerializer`,
  который в одной транзакции создаёт User и ClientProfile.
-->
<template>
  <section class="auth">
    <div class="panel auth__card">
      <div class="hero__eyebrow">РЕГИСТРАЦИЯ</div>
      <h1 class="auth__title">Создание учётной записи</h1>

      <!-- Прогресс шагов -->
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

      <!-- ШАГ 1 — вход в систему + ФИО -->
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

      <!-- ШАГ 2 — данные для договора -->
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

// Все поля — в одном объекте. На шаге 1 используются обязательные,
// на шаге 2 — опциональные. В бэкенд уходит вся структура одним POST.
const form = reactive({
  // Аккаунт
  username: '',
  email: '',
  phone: '',
  password: '',
  // ФИО (обязательно на шаге 1)
  last_name: '',
  first_name: '',
  middle_name: '',
  // Договорные данные (шаг 2, все опциональны)
  birth_date: '',
  passport_series: '',
  passport_number: '',
  passport_issued_by: '',
  passport_issued_date: '',
  passport_code: '',
  registration_address: '',
  actual_address: '',
})

/**
 * Валидация шага 1 не вызывает бэк — просто HTML5 required + длина пароля.
 * Если бэкенд отвергнет уникальность логина/почты, покажем ошибку
 * после общего submit.
 */
function goToStep2 () {
  error.value = ''
  if (form.password.length < 8) {
    error.value = 'Пароль должен быть не короче 8 символов.'
    return
  }
  step.value = 2
}

/**
 * Попытка регистрации. `extended` = true — шлём все поля, иначе
 * только базовые (шаг 2 пропущен).
 */
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
      // middle_name — допустим пустым, но лучше отправить,
      // если пользователь ввёл его на шаге 1.
      ...(form.middle_name ? { middle_name: form.middle_name } : {}),
    }
    await auth.register(payload)
    router.push('/account?welcome=1')
  } catch (e) {
    const data = e.response?.data || {}
    error.value = Object.values(data).flat().join(' ')
      || 'Не удалось создать учётную запись'
    // Если ошибка в первой половине полей — отправляем обратно на шаг 1,
    // чтобы пользователь увидел, что пошло не так.
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
.auth { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.auth__card { width: min(560px, 100%); }
.auth__title { font-size: 28px; margin: 16px 0 12px; color: #fff; }

/* Прогресс регистрации — двухпунктная дорожка. */
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
  color: rgba(255, 255, 255, .55);
  font-size: 13px;
}
.rstep__num {
  display: inline-flex;
  width: 22px; height: 22px;
  align-items: center; justify-content: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, .1);
  color: rgba(255, 255, 255, .7);
  font-weight: 700;
  font-size: 12px;
}
.rstep__item--active {
  color: #fff;
}
.rstep__item--active .rstep__num {
  background: #3ddbc7;
  color: #0f3a33;
}
.rstep__item--done .rstep__num {
  background: rgba(61, 219, 199, .25);
  color: #3ddbc7;
}
.rstep__hint {
  font-size: 11px;
  font-style: italic;
  opacity: .75;
}

.error {
  background: rgba(255, 122, 107, .15);
  border: 1px solid rgba(255, 122, 107, .35);
  color: #ffd3cc;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
}
</style>
