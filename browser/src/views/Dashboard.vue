<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface GalleryImage {
  id: number
  displayName: string
  created_at?: string
  thumbUrl: string
  fullUrl: string
  tags?: string[]
}

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const viewMode = ref<'grid' | 'masonry' | 'large'>('grid')
const sortOrder = ref<'newest' | 'oldest'>('newest')
const currentPage = ref(1)
const pageSize = ref(12)
const isBatchMode = ref(false)
const selectedIds = ref<number[]>([])
const images = ref<GalleryImage[]>([])
const total = ref(0)
const loading = ref(false)
const todayDeleted = ref(0)

const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (path: string) => (!path ? '' : path.startsWith('http') ? path : `${apiBase}${path}`)

const tasksCount = computed(() => todayDeleted.value)
const hasImages = computed(() => images.value.length > 0)
const galleryClass = computed(() => ['gallery', hasImages.value ? viewMode.value : 'empty'])

const links = [
  { label: '首页', icon: '🏠', path: '/' },
  { label: '搜索引擎', icon: '🔎', path: '/search' },
  { label: '上传中心', icon: '☁️', path: '/upload' },
  { label: '标签', icon: '🏷️', path: '/tags' },
  { label: '文件夹', icon: '📁', path: '/folders' },
  { label: '相册', icon: '📚', path: '/albums' },
  { label: '智能分类', icon: '🧠', path: '/smart' },
  { label: 'AI工作区', icon: '🤖', path: '/ai' },
  { label: '任务中心', icon: '🧾', path: '/tasks' },
  { label: '回收站', icon: '🗑️', path: '/recycle' },
  { label: '设置', icon: '⚙️', path: '/settings' },
]

const currentPath = computed(() => router.currentRoute.value.path)
function go(path: string) {
  router.push(path)
}
function isActive(path: string) {
  return currentPath.value === path || currentPath.value.startsWith(path + '/')
}

function fallbackToRaw(event: Event, url: string) {
  const img = event.target as HTMLImageElement | null
  if (img && img.src !== url) img.src = url
}

async function fetchImages() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/images', {
      params: { page: currentPage.value, page_size: pageSize.value, sort: sortOrder.value },
    })
    const tokenParam = authStore.token ? `?jwt=${authStore.token}` : ''

    images.value = (res.data.items || []).map((item: any) => ({
      ...item,
      thumbUrl: withBase((item.thumb_url || `/api/v1/images/${item.id}/thumb`) + tokenParam),
      fullUrl: withBase((item.raw_url || `/api/v1/images/${item.id}/raw`) + tokenParam),
      displayName: item.name || item.original_name,
    }))
    total.value = res.data.total || 0
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '获取图片失败')
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await axios.get('/api/v1/images/stats')
    todayDeleted.value = res.data.today_deleted || 0
  } catch (err) {
    /* ignore */
  }
}

onMounted(() => {
  if (authStore.token) {
    fetchImages()
    fetchStats()
  }
})
watch(
  () => authStore.token,
  token => {
    currentPage.value = 1
    if (token) {
      fetchImages()
      fetchStats()
    } else images.value = []
  }
)

function handlePageChange(p: number) {
  currentPage.value = p
  fetchImages()
}
function changeView(mode: 'grid' | 'masonry' | 'large') {
  viewMode.value = mode
}
function toggleBatchMode() {
  isBatchMode.value = !isBatchMode.value
  if (!isBatchMode.value) selectedIds.value = []
}
function toggleSelect(id: number) {
  if (!isBatchMode.value) {
    router.push(`/images/${id}`)
    return
  }
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(id)
}
function isSelected(id: number) {
  return selectedIds.value.includes(id)
}
function logout() {
  authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/auth/login')
}
function upload() {
  router.push('/upload')
}

function confirmPink(title: string, text: string) {
  return ElMessageBox.confirm(text, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
    customClass: 'pink-confirm',
  })
}
async function batchTrash() {
  if (!selectedIds.value.length) return
  const ids = [...selectedIds.value]
  try {
    await confirmPink('移入回收站', `确定将选中的 ${ids.length} 张图片移入回收站吗？`)
    await axios.post('/api/v1/images/trash-batch', { ids })
    images.value = images.value.filter(img => !ids.includes(img.id))
    total.value = images.value.length
    selectedIds.value = []
    isBatchMode.value = false
    await fetchStats()
    ElMessage.success('已移入回收站')
  } catch {
    /* cancelled or failed */
  }
}
</script>

<template>
  <div class="dashboard">
    <aside class="sidebar">
      <div class="logo">
        <div class="icon">📸</div>
        <div class="text">
          <h1>Photory</h1>
          <p>记录世间每一份美好，让瞬间变成永恒～</p>
        </div>
      </div>

      <nav>
        <a v-for="item in links" :key="item.path" :class="{ active: isActive(item.path) }" @click="go(item.path)">
          {{ item.icon }} {{ item.label }}
        </a>
      </nav>
    </aside>

    <main>
      <header class="topbar">
        <div class="left">
          <div class="title">今天也要好好记录生活哦～</div>
          <div class="subtitle">Photory 记录你的每一张 photo 下的温柔 story</div>
        </div>

        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}</span>
          <el-badge is-dot class="bell"><button class="icon-btn">🔔</button></el-badge>
          <button class="icon-btn" @click="logout">🚪</button>
        </div>
      </header>

      <section class="hero">
        <div class="hero-left">
          <div class="badge">今日心情 · 小小记录</div>
          <h2>让美好永远留在心底 🌸</h2>
          <p>这里是你的专属回忆小宇宙，生活里的每一朵花、每一片天空、每一场落日，都值得被认真记录～</p>
          <div class="stats">
            <div><b>{{ total }}</b><span>图片总数</span></div>
            <div><b>1</b><span>今日上传</span></div>
            <div><b>{{ tasksCount }}</b><span>今日删除</span></div>
          </div>
        </div>

        <div class="hero-right">
          <div class="hero-img"><span>🌷 Photory 等你来探索哦～</span></div>
        </div>
      </section>

      <section class="toolbar">
        <div class="left">
          <button class="upload-btn" @click="upload">☁️ 上传图片</button>
          <button class="manage-btn" :class="{ active: isBatchMode }" @click="toggleBatchMode">
            🗑️ {{ isBatchMode ? '退出批量删除' : '批量删除' }}
          </button>
          <span v-if="isBatchMode" class="selected-tip">已选中 {{ selectedIds.length }} 张图</span>
          <button v-if="isBatchMode && selectedIds.length" class="danger-btn" @click="batchTrash">确认删除到回收站</button>
        </div>

        <div class="right">
          <div class="view-switch">
            <button class="view-pill" :class="{ active: viewMode === 'grid' }" @click="changeView('grid')">🟦 网格</button>
            <button class="view-pill" :class="{ active: viewMode === 'masonry' }" @click="changeView('masonry')">🧱 瀑布流</button>
            <button class="view-pill" :class="{ active: viewMode === 'large' }" @click="changeView('large')">🃏 大卡片</button>
          </div>

          <div class="sort">
            <span>排序：</span>
            <button class="sort-pill" :class="{ active: sortOrder === 'newest' }" @click="sortOrder = 'newest'; fetchImages()">最新上传</button>
            <button class="sort-pill" :class="{ active: sortOrder === 'oldest' }" @click="sortOrder = 'oldest'; fetchImages()">最早记录</button>
          </div>
        </div>
      </section>

      <section :class="galleryClass">
        <div v-if="!loading && images.length === 0" class="empty-box">
          <div class="empty-row">
            <span>你的图库还是空空如也哦，</span>
            <span>快来上传第一张图片吧～</span>
          </div>
        </div>
        <div
          v-for="img in images"
          v-else
          :key="img.id"
          class="photo"
          :class="{ selected: isSelected(img.id), 'batch-mode': isBatchMode }"
          @click="toggleSelect(img.id)"
        >
          <div class="select-badge" v-if="isBatchMode"><span v-if="isSelected(img.id)">✓</span></div>
          <img :src="img.thumbUrl" :alt="img.displayName" loading="lazy" @error="fallbackToRaw($event, img.fullUrl)" />

          <div class="caption">
            <div class="title">{{ img.displayName }}</div>
            <div class="date">{{ img.created_at?.slice(0, 10) }}</div>
          </div>
        </div>
      </section>

      <div class="footer-wrapper">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="handlePageChange"
          class="pagination"
        />
        <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard { display: flex; min-height: 100vh; background: linear-gradient(135deg, #ffeef5, #ffe5f0); color: #4b4b4b; }
.sidebar { width: 220px; background: linear-gradient(180deg, #fff7fb, #ffeef5); border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 20px; }
.logo { display: flex; gap: 10px; margin-bottom: 20px; }
.logo .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 36px; height: 36px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.logo h1 { font-size: 18px; color: #ff4c8a; margin: 0; }
.logo p { font-size: 11px; color: #b6788d; margin: 0; }
nav a { display: block; padding: 8px 12px; border-radius: 12px; font-size: 13px; color: #6b3c4a; margin: 2px 0; cursor: default; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }
main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.9); }
.topbar .title { font-weight: 600; color: #ff4c8a; }
.topbar .subtitle { font-size: 12px; color: #a36e84; }
.topbar .right { display: flex; align-items: center; gap: 10px; }
.welcome { font-size: 13px; color: #8c546e; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn:hover { background: #ffd6e5; }
.hero { display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px; padding: 20px 24px 10px; }
.hero-left { background: linear-gradient(135deg, #ffe9f5, #ffe1f0); border-radius: 24px; padding: 20px 24px; box-shadow: 0 16px 32px rgba(255, 165, 199, 0.35); }
.hero-left .badge { background: #fff; display: inline-block; border-radius: 999px; padding: 4px 10px; font-size: 11px; color: #c06d8a; }
.hero-left h2 { color: #ff3f87; margin: 12px 0 6px; }
.hero-left p { font-size: 13px; color: #a25c77; }
.stats { display: flex; gap: 18px; margin-top: 18px; }
.stats div { background: rgba(255, 255, 255, 0.9); border-radius: 14px; padding: 10px 16px; text-align: center; min-width: 90px; }
.stats b { color: #ff4c8a; font-size: 18px; }
.stats span { display: block; font-size: 11px; color: #b6788d; }
.hero-right { display: flex; align-items: center; justify-content: center; }
.hero-right .hero-img { width: 100%; height: 100%; min-height: 160px; border-radius: 24px; background: url('@/assets/pretty_flower.jpg') center/cover no-repeat; border: 8px solid rgba(255, 255, 255, 0.95); box-shadow: 0 18px 36px rgba(255, 167, 201, 0.45); position: relative; }
.hero-img span { position: absolute; bottom: 14px; left: 16px; right: 16px; background: rgba(255, 255, 255, 0.9); border-radius: 999px; font-size: 12px; padding: 6px 12px; color: #a15773; text-align: center; }
.toolbar { display: flex; justify-content: space-between; align-items: flex-start; padding: 6px 24px 0; }
.toolbar .left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.upload-btn, .manage-btn { border: none; border-radius: 20px; padding: 8px 18px; cursor: pointer; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 13px; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.manage-btn { background: linear-gradient(135deg, #ffb2cc, #ff8db8); }
.manage-btn.active { background: linear-gradient(135deg, #fca9c9, #ff88b3); }
.selected-tip { font-size: 12px; color: #a35d76; }
.danger-btn { border: none; border-radius: 14px; padding: 6px 12px; background: linear-gradient(135deg, #ff9c9c, #ff6b6b); color: #fff; box-shadow: 0 4px 10px rgba(255,100,120,0.4); cursor: pointer; }
.toolbar .right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.view-switch, .sort { display: flex; align-items: center; gap: 8px; }
.view-pill, .sort-pill { border-radius: 999px; border: 1px solid rgba(255, 180, 205, 0.9); background: rgba(255, 255, 255, 0.9); font-size: 12px; padding: 4px 12px; cursor: pointer; }
.view-pill.active, .sort-pill.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
.gallery { padding: 16px 24px 10px; }
.gallery.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.gallery.masonry { column-count: 4; column-gap: 18px; }
.gallery.masonry .photo { break-inside: avoid; margin-bottom: 18px; }
.gallery.large { display: flex; flex-direction: column; gap: 16px; }
.gallery.large .photo { display: flex; height: 190px; }
.gallery.large .photo img { width: 45%; height: 100%; object-fit: cover; }
.gallery.large .caption { flex: 1; padding: 16px; }
.gallery.empty { display: flex !important; align-items: center; justify-content: center; width: 100%; }
.empty-box { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; min-height: 320px; width: 100%; }
.empty-row { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; font-size: 20px; color: #a35d76; text-align: center; }
.photo { position: relative; border-radius: 18px; overflow: hidden; background: #ffeaf3; box-shadow: 0 10px 20px rgba(255, 153, 187, 0.28); cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease, border 0.15s ease; }
.gallery.grid .photo { height: 230px; display: flex; flex-direction: column; }
.photo img { width: 100%; height: 72%; object-fit: cover; background: #fce6f0; }
.gallery.masonry .photo img { height: auto; }
.caption { padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; }
.caption .title { font-size: 13px; color: #613448; }
.caption .date { font-size: 11px; color: #b57a90; }
.photo.batch-mode::after { content: ''; position: absolute; inset: 0; background: rgba(255, 255, 255, 0); transition: background 0.15s ease; }
.photo.selected { border: 2px solid #ff6fa5; box-shadow: 0 0 0 2px rgba(255, 152, 201, 0.5), 0 10px 24px rgba(255, 152, 201, 0.5); }
.select-badge { position: absolute; top: 8px; right: 8px; width: 22px; height: 22px; border-radius: 999px; background: rgba(255, 255, 255, 0.98); border: 1px solid #ff8cb7; display: flex; align-items: center; justify-content: center; font-size: 13px; color: #ff4c8a; z-index: 2; }
.photo:hover { transform: translateY(-3px); box-shadow: 0 14px 26px rgba(255, 153, 187, 0.4); }
.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding-bottom: 16px; }
.pagination { display: flex; justify-content: center; }
:deep(.el-pagination.is-background .el-pager li) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination.is-background .el-pager li.is-active) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
:deep(.el-pagination.is-background .el-pager li:hover) { background-color: #ffdce9; }
:deep(.el-pagination button) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination button.is-disabled) { opacity: 0.5; }
footer { text-align: center; font-size: 12px; color: #b57a90; }
:deep(.pink-confirm .el-message-box__title) { color: #ff4c8a; }
:deep(.pink-confirm .el-button--primary) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); border: none; }
:deep(.pink-confirm .el-button--default) { border-color: #ffb6cf; color: #b05f7a; }
@media (max-width: 1200px) { .gallery.grid { grid-template-columns: repeat(3, 1fr); } .gallery.masonry { column-count: 3; } }
@media (max-width: 900px) { .sidebar { display: none; } .hero { grid-template-columns: 1fr; } .gallery.grid { grid-template-columns: repeat(2, 1fr); } .gallery.masonry { column-count: 2; } }
</style>
