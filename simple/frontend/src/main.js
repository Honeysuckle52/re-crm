import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './store/auth'
import './styles/main.css'

async function bootstrap () {
  const app = createApp(App)
  app.use(createPinia())
  app.use(router)

  const auth = useAuthStore()
  await auth.initialize()

  window.addEventListener('auth:expired', async () => {
    await auth.clearSession()
    if (router.currentRoute.value.name !== 'login') {
      await router.replace('/login')
    }
  })

  app.mount('#app')
}

bootstrap()
