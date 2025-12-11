import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import UploadCenter from '../views/UploadCenter.vue'
import ImageDetail from '../views/ImageDetail.vue'
import ImageEditor from '../views/ImageEditor.vue'
import TagManagement from '../views/TagManagement.vue'
import TagImages from '../views/TagImages.vue'
import RecycleBin from '../views/RecycleBin.vue'
import Login from '../views/auth/Login.vue'
import Register from '../views/auth/Register.vue'
import SearchEngine from '../views/SearchEngine.vue'
import AIWorkspace from '../views/AIWorkspace.vue'
import AlbumDetail from '../views/AlbumDetail.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/search', name: 'SearchEngine', component: SearchEngine },
  { path: '/upload', name: 'UploadCenter', component: UploadCenter },
  { path: '/tags', name: 'TagManagement', component: TagManagement },
  { path: '/tags/:id/images', name: 'TagImages', component: TagImages, props: true },
  { path: '/recycle', name: 'RecycleBin', component: RecycleBin },
  { path: '/albums', name: 'Albums', component: () => import('../views/Albums.vue'), meta: { title: '相册' } },
  { path: '/albums/:id', name: 'AlbumDetail', component: AlbumDetail, meta: { title: '相册详情' } },
  { path: '/ai', name: 'AIWorkspace', component: AIWorkspace, meta: { title: 'AI 工作台' } },
  { path: '/images/:id', name: 'ImageDetail', component: ImageDetail, props: true },
  { path: '/images/:id/edit', name: 'ImageEditor', component: ImageEditor, props: true },
  { path: '/auth/login', name: 'AuthLogin', component: Login },
  { path: '/login', redirect: '/auth/login' },
  { path: '/auth/register', name: 'AuthRegister', component: Register },
]

const router = createRouter({ history: createWebHistory(), routes })
export default router