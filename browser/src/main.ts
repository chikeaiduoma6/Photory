import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from 'axios'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

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
      if (router.currentRoute.value.path !== '/auth/login') {
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
