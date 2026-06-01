import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './store/auth'
import './styles/main.css'

async function bootstrap () {
  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)

  const auth = useAuthStore()
  await auth.initialize()

  app.use(router)
  await router.isReady()

  window.addEventListener('auth:expired', async () => {
    auth.clearSession()
    if (router.currentRoute.value.name !== 'login') {
      await router.replace('/login')
    }
  })

  app.mount('#app')
}

bootstrap()
