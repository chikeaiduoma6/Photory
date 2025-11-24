import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from 'axios'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
if (API_BASE) axios.defaults.baseURL = API_BASE
axios.defaults.withCredentials = false

axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token') || ''
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

axios.interceptors.response.use(
  res => res,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      delete axios.defaults.headers.common.Authorization
      const cur = router.currentRoute.value.path
      if (!cur.startsWith('/auth')) {
        router.push('/auth/login')
      }
    }
    return Promise.reject(error)
  }
)

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const authStore = useAuthStore(pinia)
authStore.hydrate()

router.beforeEach((to, _from, next) => {
  if (to.path.startsWith('/auth')) return next()
  if (!authStore.token) return next('/auth/login')
  return next()
})

app.use(router)
app.use(ElementPlus)
app.mount('#app')
