import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './store/auth'

const routes = [
  { path: '/login', name: 'login',
    component: () => import('./views/Login.vue'), meta: { guest: true } },
  { path: '/register', name: 'register',
    component: () => import('./views/Register.vue'), meta: { guest: true } },

  { path: '/', name: 'home',
    component: () => import('./views/Dashboard.vue') },

  { path: '/properties', name: 'properties',
    component: () => import('./views/Properties.vue') },
  { path: '/properties/new', name: 'property-new',
    component: () => import('./views/PropertyForm.vue') },
  { path: '/properties/:id', name: 'property-detail',
    component: () => import('./views/PropertyDetail.vue') },
  { path: '/properties/:id/edit', name: 'property-edit',
    component: () => import('./views/PropertyForm.vue') },

  { path: '/requests', name: 'requests',
    component: () => import('./views/Requests.vue') },
  { path: '/clients', name: 'clients',
    component: () => import('./views/Clients.vue') },
  { path: '/deals', name: 'deals',
    component: () => import('./views/Deals.vue') },
  { path: '/account', name: 'account',
    component: () => import('./views/Account.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.guest && !auth.isAuthenticated) return { name: 'login' }
  if (to.meta.guest && auth.isAuthenticated) return { name: 'home' }
})

export default router
