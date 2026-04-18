<template>
  <section class="auth">
    <div class="panel auth__card">
      <div class="hero__eyebrow">РИЭЛТ</div>
      <h1 class="auth__title">Вход в систему</h1>
      <p class="muted" style="color: rgba(255,255,255,.7)">
        Введите логин и пароль, чтобы продолжить работу
      </p>
      <form class="stack" @submit.prevent="submit">
        <div class="field">
          <label>Логин</label>
          <input class="input" v-model="username" autocomplete="username" required />
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
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true; error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Неверный логин или пароль'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.auth__card { width: min(420px, 100%); }
.auth__title { font-size: 32px; margin: 16px 0 8px; }
</style>
