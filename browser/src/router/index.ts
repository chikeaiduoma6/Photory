// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import UploadCenter from '../views/UploadCenter.vue'
import Login from '../views/auth/Login.vue'
import Register from '../views/auth/Register.vue'
import ForgotPassword from '../views/auth/ForgotPassword.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
  },
  {
    path: '/upload',
    name: 'UploadCenter',
    component: UploadCenter,
  },
  {
    path: '/auth/login',
    name: 'AuthLogin',
    component: Login,
  },
  {
    path: '/login', 
    redirect: '/auth/login',
  },
  {
    path: '/auth/register',
    name: 'AuthRegister',
    component: Register,
  },
  {
    path: '/auth/forgot-password',
    name: 'AuthForgotPassword',
    component: ForgotPassword,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
