// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import UploadCenter from '../views/UploadCenter.vue'
import ImageDetail from '../views/ImageDetail.vue'
import TagManagement from '../views/TagManagement.vue'
import Placeholder from '../views/Placeholder.vue' 

import Login from '../views/auth/Login.vue'
import Register from '../views/auth/Register.vue'
import ForgotPassword from '../views/auth/ForgotPassword.vue'

const routes = [
   { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/upload', name: 'UploadCenter', component: UploadCenter },
  { path: '/tags', name: 'TagManagement', component: TagManagement },
  { path: '/folders', name: 'Folders', component: Placeholder, meta: { title: '文件夹' } },
  { path: '/albums', name: 'Albums', component: Placeholder, meta: { title: '相册' } },
  { path: '/smart', name: 'Smart', component: Placeholder, meta: { title: '智能分类' } },
  { path: '/ai', name: 'AIWorkspace', component: Placeholder, meta: { title: 'AI 工作台' } },
  { path: '/tasks', name: 'Tasks', component: Placeholder, meta: { title: '任务中心' } },
  { path: '/recycle', name: 'Recycle', component: Placeholder, meta: { title: '回收站' } },
  { path: '/settings', name: 'Settings', component: Placeholder, meta: { title: '设置' } },
  { path: '/images/:id', name: 'ImageDetail', component: ImageDetail, props: true },
  { path: '/auth/login', name: 'AuthLogin', component: Login },
  { path: '/login', redirect: '/auth/login' },
  { path: '/auth/register', name: 'AuthRegister', component: Register },
  { path: '/auth/forgot-password', name: 'AuthForgotPassword', component: ForgotPassword },
]

const router = createRouter({ history: createWebHistory(), routes })
export default router