import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './store/auth'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Восстановление сессии из localStorage токенов
const auth = useAuthStore()
auth.hydrate()

app.mount('#app')
