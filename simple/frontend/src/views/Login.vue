<template>
  <section class="auth">
    <div class="panel auth__card">
      <div class="hero__eyebrow">РИЭЛТ</div>
      <h1 class="auth__title">Вход в систему</h1>
      <p class="muted" style="color: rgba(255,255,255,.7)">
        Введите электронную почту и пароль, чтобы продолжить работу
      </p>
      <form class="stack" @submit.prevent="submit">
        <div class="field">
          <label>Электронная почта</label>
          <input class="input" type="email" v-model.trim="email"
                 autocomplete="email" required />
        </div>
        <div class="field">
          <label>Пароль</label>
          <input class="input" type="password" v-model="password"
                 autocomplete="current-password" required />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button class="btn btn--accent" :disabled="loading" type="submit">
          {{ loading ? 'Вход…' : 'Войти' }}
        </button>
      </form>
      <div class="row row--between" style="margin-top: 12px">
        <span class="muted" style="color: rgba(255,255,255,.6)">Нет учётной записи?</span>
        <router-link to="/register" class="btn btn--ghost btn--sm">
          Регистрация
        </router-link>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true; error.value = ''
  try {
    await auth.login(email.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Неверная почта или пароль'
  } finally {
    loading.value = false
  }
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
    radial-gradient(circle at 18% 20%, rgba(120, 216, 206, 0.22), transparent 26%),
    radial-gradient(circle at 82% 12%, rgba(226, 248, 245, 0.14), transparent 22%);
  pointer-events: none;
}

.auth__card {
  position: relative;
  width: min(420px, 100%);
}

.auth__title {
  margin: 18px 0 8px;
  font-size: clamp(30px, 5vw, 38px);
  line-height: 1.05;
  color: var(--c-text);
}
</style>
