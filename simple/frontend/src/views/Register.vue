<template>
  <section class="auth">
    <div class="panel auth__card">
      <div class="hero__eyebrow">РЕГИСТРАЦИЯ</div>
      <h1 class="auth__title">Создание учётной записи</h1>
      <p class="muted" style="color: rgba(255,255,255,.7); margin-bottom: 8px">
        Новая учётная запись создаётся как клиент. Права сотрудника
        и роль назначает администратор или менеджер агентства.
      </p>
      <form class="stack" @submit.prevent="submit">
        <div class="field">
          <label>Логин</label>
          <input class="input" v-model="form.username" required autocomplete="username" />
        </div>
        <div class="field">
          <label>Электронная почта</label>
          <input class="input" type="email" v-model="form.email" required autocomplete="email" />
        </div>
        <div class="field">
          <label>Телефон</label>
          <input class="input" v-model="form.phone" placeholder="+7..." autocomplete="tel" />
        </div>
        <div class="field">
          <label>Пароль</label>
          <input class="input" type="password" v-model="form.password"
                 required autocomplete="new-password" />
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button class="btn btn--accent" :disabled="loading" type="submit">
          {{ loading ? 'Создание…' : 'Зарегистрироваться' }}
        </button>
      </form>
      <router-link to="/login" class="btn btn--ghost btn--sm"
                   style="margin-top: 12px; display: inline-flex">
        У меня уже есть учётная запись
      </router-link>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ username: '', email: '', phone: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true; error.value = ''
  try {
    await auth.register({ ...form })
    router.push('/')
  } catch (e) {
    const data = e.response?.data || {}
    error.value = Object.values(data).flat().join(' ')
      || 'Не удалось создать учётную запись'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.auth__card { width: min(480px, 100%); }
.auth__title { font-size: 28px; margin: 16px 0 12px; color: #fff; }
</style>
