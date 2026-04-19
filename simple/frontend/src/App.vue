<template>
  <!-- Sticky-footer через flex: TopBar сверху, main растягивается,
       AppFooter всегда в конце документа и скроллится вместе со страницей. -->
  <div class="app-shell">
    <TopBar v-if="auth.isAuthenticated" />
    <main class="layout">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <AppFooter v-if="auth.isAuthenticated" />
    <!-- Компактная плавающая карточка текущей задачи — только для сотрудников. -->
    <CurrentTaskWidget v-if="auth.isAuthenticated && auth.isStaff" />
    <!-- Хост тост-уведомлений: показывает сообщения о действиях, авто-закрытиях и ошибках. -->
    <ToastHost v-if="auth.isAuthenticated" />
  </div>
</template>

<script setup>
import { useAuthStore } from './store/auth'
import TopBar from './components/TopBar.vue'
import AppFooter from './components/AppFooter.vue'
import CurrentTaskWidget from './components/CurrentTaskWidget.vue'
import ToastHost from './components/ToastHost.vue'

const auth = useAuthStore()
</script>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Корневой шелл — классический sticky-footer layout. */
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-shell > .layout { flex: 1 0 auto; }
.app-shell > .footer {
  flex-shrink: 0;
  /* Виджет CurrentTaskWidget в expanded-режиме выставляет
     --ctw-reserved-space и мы дополнительно отодвигаем нижнее
     содержимое (футер и хвост таблиц), чтобы карточка никогда
     не перекрывала данные — раньше это было основной причиной
     «кривого» отображения страниц. */
  padding-bottom: var(--ctw-reserved-space, 0px);
  transition: padding-bottom .2s ease;
}
</style>
