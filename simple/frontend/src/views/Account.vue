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
    </div>

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
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import InfoRow from '../components/InfoRow.vue'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
