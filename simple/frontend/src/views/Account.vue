<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">АККАУНТ</div>
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
        <InfoRow label="ID"       :value="auth.user?.id" />
        <InfoRow label="Логин"    :value="auth.user?.username" />
        <InfoRow label="Email"    :value="auth.user?.email" />
        <InfoRow label="Телефон"  :value="auth.user?.phone || '—'" />
        <InfoRow label="Тип"      :value="auth.user?.user_type === 'employee' ? 'Сотрудник' : 'Клиент'" />
        <InfoRow label="Роль"     :value="auth.user?.role_name || '—'" />
        <InfoRow label="Email подтверждён"   :value="auth.user?.is_email_verified ? 'да' : 'нет'" />
        <InfoRow label="Телефон подтверждён" :value="auth.user?.is_phone_verified ? 'да' : 'нет'" />
      </div>

      <div class="panel">
        <h2 class="h3" style="color: #fff">Безопасность</h2>
        <p style="color: rgba(255,255,255,.8); font-size: 14px">
          Доступ к API осуществляется по JWT: access-токен обновляется автоматически
          через refresh. Токен ФИАС хранится только на сервере и никогда не
          передаётся в браузер.
        </p>
        <button class="btn btn--danger" @click="logout">Выйти из аккаунта</button>
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
