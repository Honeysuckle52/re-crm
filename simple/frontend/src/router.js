import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './store/auth'

import LoginView from './views/Login.vue'
import RegisterView from './views/Register.vue'
import DashboardView from './views/Dashboard.vue'
import PropertiesView from './views/Properties.vue'
import PropertyFormView from './views/PropertyForm.vue'
import PropertyDetailView from './views/PropertyDetail.vue'
import PropertyModerationView from './views/PropertyModeration.vue'
import RequestsView from './views/Requests.vue'
import RequestDetailView from './views/RequestDetail.vue'
import TasksView from './views/Tasks.vue'
import TaskWorkflowView from './views/TaskWorkflow.vue'
import ClientsView from './views/Clients.vue'
import DealsView from './views/Deals.vue'
import DealDetailView from './views/DealDetail.vue'
import ReportsView from './views/Reports.vue'
import AccountView from './views/Account.vue'
import AdminView from './views/Admin.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
    meta: { guest: true },
  },
  {
    path: '/',
    name: 'home',
    component: DashboardView,
  },
  {
    path: '/properties',
    name: 'properties',
    component: PropertiesView,
  },
  {
    path: '/my-properties',
    name: 'client-properties',
    component: PropertiesView,
  },
  {
    path: '/properties/new',
    name: 'property-new',
    component: PropertyFormView,
  },
  {
    path: '/properties/moderation',
    name: 'property-moderation',
    component: PropertyModerationView,
    meta: { staff: true },
  },
  {
    path: '/properties/:id/edit',
    name: 'property-edit',
    component: PropertyFormView,
    meta: { staff: true },
  },
  {
    path: '/properties/:id',
    name: 'property-detail',
    component: PropertyDetailView,
  },
  {
    path: '/requests',
    name: 'requests',
    component: RequestsView,
  },
  {
    path: '/requests/:id',
    name: 'request-detail',
    component: RequestDetailView,
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: TasksView,
    meta: { staff: true },
  },
  {
    path: '/tasks/:id/work',
    name: 'task-workflow',
    component: TaskWorkflowView,
    meta: { staff: true },
  },
  {
    path: '/clients',
    name: 'clients',
    component: ClientsView,
    meta: { manager: true },
  },
  {
    path: '/deals',
    name: 'deals',
    component: DealsView,
  },
  {
    path: '/deals/:id',
    name: 'deal-detail',
    component: DealDetailView,
  },
  {
    path: '/reports',
    name: 'reports',
    component: ReportsView,
    meta: { manager: true },
  },
  {
    path: '/account',
    name: 'account',
    component: AccountView,
  },
  {
    path: '/admin',
    name: 'admin',
    component: AdminView,
    meta: { manager: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (!to.meta.guest && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'home' }
  }
  if (to.meta.staff && !auth.isStaff) {
    return { name: 'home' }
  }
  if (to.meta.manager && !auth.isManager) {
    return { name: 'home' }
  }
  if (
    (to.name === 'property-new' || to.name === 'property-edit')
    && auth.isEmployee
    && !auth.isAdminOrManager
  ) {
    return { name: 'home' }
  }

  return true
})

router.onError((error) => {
  console.error('Router navigation error:', error)
  throw error
})

export default router
