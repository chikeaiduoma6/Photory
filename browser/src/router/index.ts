import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import UploadCenter from '../views/UploadCenter.vue'
import ImageDetail from '../views/ImageDetail.vue'
import ImageEditor from '../views/ImageEditor.vue'
import TagManagement from '../views/TagManagement.vue'
import RecycleBin from '../views/RecycleBin.vue'
import Placeholder from '../views/Placeholder.vue'
import Login from '../views/auth/Login.vue'
import Register from '../views/auth/Register.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/upload', name: 'UploadCenter', component: UploadCenter },
  { path: '/tags', name: 'TagManagement', component: TagManagement },
  { path: '/recycle', name: 'RecycleBin', component: RecycleBin },
  { path: '/folders', name: 'Folders', component: Placeholder, meta: { title: '文件夹' } },
  { path: '/albums', name: 'Albums', component: Placeholder, meta: { title: '相册' } },
  { path: '/smart', name: 'Smart', component: Placeholder, meta: { title: '智能分类' } },
  { path: '/ai', name: 'AIWorkspace', component: Placeholder, meta: { title: 'AI 工作区' } },
  { path: '/tasks', name: 'Tasks', component: Placeholder, meta: { title: '任务中心' } },
  { path: '/settings', name: 'Settings', component: Placeholder, meta: { title: '设置' } },
  { path: '/images/:id', name: 'ImageDetail', component: ImageDetail, props: true },
  { path: '/images/:id/edit', name: 'ImageEditor', component: ImageEditor, props: true },
  { path: '/auth/login', name: 'AuthLogin', component: Login },
  { path: '/login', redirect: '/auth/login' },
  { path: '/auth/register', name: 'AuthRegister', component: Register },
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
