<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
const featuredImages = ref<GalleryImage[]>([])
const total = ref(0)
const loading = ref(false)
const todayDeleted = ref(0)
const todayUploaded = ref(0)
const navOpen = ref(false)

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
  { label: 'AI 工作台', icon: '🤖', path: '/ai' },
  { label: '任务中心', icon: '🧾', path: '/tasks' },
  { label: '回收站', icon: '🗑️', path: '/recycle' },
  { label: '设置', icon: '⚙️', path: '/settings' },
]

const currentPath = computed(() => router.currentRoute.value.path)
function go(path: string) {
  router.push(path)
  navOpen.value = false
}
function isActive(path: string) {
  return currentPath.value === path || currentPath.value.startsWith(path + '/')
}
function toggleNav() {
  navOpen.value = !navOpen.value
}
function closeNav() {
  navOpen.value = false
}
watch(
  () => router.currentRoute.value.fullPath,
  () => closeNav()
)

function fallbackToRaw(event: Event, url: string) {
  const img = event.target as HTMLImageElement | null
  if (img && img.src !== url) img.src = url
}

function mapImage(item: any): GalleryImage {
  const tokenParam = authStore.token ? `?jwt=${authStore.token}` : ''
  return {
    ...item,
    thumbUrl: withBase((item.thumb_url || `/api/v1/images/${item.id}/thumb`) + tokenParam),
    fullUrl: withBase((item.raw_url || `/api/v1/images/${item.id}/raw`) + tokenParam),
    displayName: item.name || item.original_name,
  }
}

async function fetchImages() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/images', {
      params: { page: currentPage.value, page_size: pageSize.value, sort: sortOrder.value },
    })
    images.value = (res.data.items || []).map(mapImage)
    total.value = res.data.total || 0
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '获取图片失败')
  } finally {
    loading.value = false
  }
}

async function fetchFeatured() {
  try {
    const res = await axios.get('/api/v1/images', { params: { featured: 1, page: 1, page_size: 12, sort: 'newest' } })
    featuredImages.value = (res.data.items || []).map(mapImage)
  } catch {
    featuredImages.value = []
  }
}

async function fetchStats() {
  try {
    const res = await axios.get('/api/v1/images/stats')
    todayDeleted.value = res.data.today_deleted || 0
    todayUploaded.value = res.data.today_uploaded || 0
    total.value = res.data.total_active ?? total.value
  } catch {
    /* ignore */
  }
}

onMounted(() => {
  if (authStore.token) {
    fetchImages()
    fetchFeatured()
    fetchStats()
  }
})
watch(
  () => authStore.token,
  token => {
    currentPage.value = 1
    if (token) {
      fetchImages()
      fetchFeatured()
      fetchStats()
    } else {
      images.value = []
      featuredImages.value = []
    }
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

/* 轮播逻辑：精选优先，不足 4 张时用首页前 8 张补足 */
const sliderImages = computed(() => {
  const maxSlides = 8
  const minSlides = 4
  const merged: Map<number, GalleryImage> = new Map()
  for (const item of featuredImages.value) merged.set(item.id, item)
  for (const item of images.value.slice(0, 8)) {
    if (!merged.has(item.id)) merged.set(item.id, item)
  }
  const arr = Array.from(merged.values())
  if (arr.length >= minSlides) return arr.slice(0, Math.min(maxSlides, arr.length))
  return arr
})
const currentSlide = ref(0)
const sliderTimer = ref<number | null>(null)
const hasSlider = computed(() => sliderImages.value.length > 0)

function nextSlide() {
  if (!sliderImages.value.length) return
  currentSlide.value = (currentSlide.value + 1) % sliderImages.value.length
}
function prevSlide() {
  if (!sliderImages.value.length) return
  currentSlide.value = (currentSlide.value - 1 + sliderImages.value.length) % sliderImages.value.length
}
function startSlider() {
  stopSlider()
  if (!sliderImages.value.length) return
  sliderTimer.value = window.setInterval(nextSlide, 4000)
}
function stopSlider() {
  if (sliderTimer.value !== null) {
    clearInterval(sliderTimer.value)
    sliderTimer.value = null
  }
}
watch(
  () => sliderImages.value.map(i => i.id).join(','),
  () => {
    currentSlide.value = 0
    if (sliderImages.value.length) startSlider()
    else stopSlider()
  }
)
onUnmounted(stopSlider)
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
      <header class="mobile-topbar">
        <button class="icon-btn ghost" @click="toggleNav">☰</button>
        <div class="mobile-brand">
          <span class="logo-mini">📸</span>
          <span>Photory</span>
        </div>
        <button class="icon-btn ghost" @click="upload">⬆️</button>
      </header>

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

      <div class="drawer" :class="{ open: navOpen }">
        <div class="drawer-mask" @click="closeNav"></div>
        <div class="drawer-panel">
          <div class="drawer-head">
            <div class="brand">
              <div class="icon">📸</div>
              <div class="text">
                <h1>Photory</h1>
                <p>记录美好 · 随时随地</p>
              </div>
            </div>
            <button class="icon-btn ghost" @click="closeNav">×</button>
          </div>
          <nav>
            <a v-for="item in links" :key="item.path" :class="{ active: isActive(item.path) }" @click="go(item.path)">
              {{ item.icon }} {{ item.label }}
            </a>
          </nav>
        </div>
      </div>

      <section class="hero">
        <div class="hero-left">
          <div class="badge">今日心情 · 小小记录</div>
          <h2>让美好永远留在心间 🌸</h2>
          <p>这里是你的专属回忆小宇宙，生活里的每一朵花、每一片天空、每一场落日，都值得被认真记录～</p>
          <div class="stats">
            <div><b>{{ total }}</b><span>图片总数</span></div>
            <div><b>{{ todayUploaded }}</b><span>今日上传</span></div>
            <div><b>{{ tasksCount }}</b><span>今日删除</span></div>
          </div>
        </div>

        <div class="hero-right">
          <div class="hero-img"><span>🌷 Photory 等你来探索哦</span></div>
        </div>
      </section>

      <section v-if="hasSlider" class="carousel" @mouseenter="stopSlider" @mouseleave="startSlider">
        <div class="carousel-head">
          <div class="carousel-title">精选轮播</div>
          <div class="carousel-actions">
            <button class="pill ghost" @click="prevSlide">←</button>
            <button class="pill ghost" @click="nextSlide">→</button>
          </div>
        </div>
        <div class="carousel-window">
          <div class="carousel-track" :style="{ transform: `translateX(-${currentSlide * 100}%)` }">
            <div
              v-for="img in sliderImages"
              :key="img.id"
              class="slide"
              @click="toggleSelect(img.id)"
            >
              <img :src="img.fullUrl" :alt="img.displayName" loading="lazy" @error="fallbackToRaw($event, img.fullUrl)" />
              <div class="slide-mask">
                <div class="slide-title">{{ img.displayName }}</div>
                <div class="slide-meta">{{ img.created_at?.slice(0, 16) || '' }}</div>
              </div>
            </div>
          </div>
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
.dashboard {
  --pink-main: #ff6fa0;
  --pink-soft: #ffeef5;
  --text-strong: #4b2b3a;
  --text-muted: #9a6c82;
  --card: rgba(255, 255, 255, 0.92);
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #ffeef5, #ffe5f0);
  color: var(--text-strong);
}
.sidebar {
  width: 240px;
  background: linear-gradient(180deg, #fff7fb, #ffeef5);
  border-right: 1px solid rgba(255, 190, 210, 0.6);
  padding: 20px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.logo {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
.logo .icon {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo h1 {
  font-size: 18px;
  color: #ff4c8a;
  margin: 0;
}
.logo p {
  font-size: 11px;
  color: #b6788d;
  margin: 0;
}
nav a {
  display: block;
  padding: 9px 12px;
  border-radius: 12px;
  font-size: 14px;
  color: #6b3c4a;
  margin: 4px 0;
  cursor: pointer;
}
nav a.active,
nav a:hover {
  background: rgba(255, 153, 187, 0.16);
  color: #ff4c8a;
}
main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  border-bottom: 1px solid rgba(255, 190, 210, 0.5);
  background: rgba(255, 255, 255, 0.9);
}
.topbar .title {
  font-weight: 600;
  color: #ff4c8a;
}
.topbar .subtitle {
  font-size: 12px;
  color: #a36e84;
}
.topbar .right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.welcome {
  font-size: 13px;
  color: #8c546e;
}
.icon-btn {
  background: #ffeef5;
  border: none;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  cursor: pointer;
}
.icon-btn:hover {
  background: #ffd6e5;
}
.icon-btn.ghost {
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(255, 190, 210, 0.7);
}
.hero {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 20px;
  padding: 20px 24px 10px;
}
.hero-left {
  background: linear-gradient(135deg, #ffe9f5, #ffe1f0);
  border-radius: 24px;
  padding: 20px 24px;
  box-shadow: 0 16px 32px rgba(255, 165, 199, 0.35);
}
.hero-left .badge {
  background: #fff;
  display: inline-block;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  color: #c06d8a;
}
.hero-left h2 {
  color: #ff3f87;
  margin: 12px 0 6px;
}
.hero-left p {
  font-size: 13px;
  color: #a25c77;
}
.stats {
  display: flex;
  gap: 18px;
  margin-top: 18px;
  flex-wrap: wrap;
}
.stats div {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 14px;
  padding: 10px 16px;
  text-align: center;
  min-width: 90px;
}
.stats b {
  color: #ff4c8a;
  font-size: 18px;
}
.stats span {
  display: block;
  font-size: 11px;
  color: #b6788d;
}
.hero-right {
  display: flex;
  align-items: center;
  justify-content: center;
}
.hero-right .hero-img {
  width: 100%;
  height: 100%;
  min-height: 180px;
  border-radius: 24px;
  background: url('@/assets/pretty_flower.jpg') center/cover no-repeat;
  border: 8px solid rgba(255, 255, 255, 0.95);
  box-shadow: 0 18px 36px rgba(255, 167, 201, 0.45);
  position: relative;
}
.hero-img span {
  position: absolute;
  bottom: 14px;
  left: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 999px;
  font-size: 12px;
  padding: 6px 12px;
  color: #a15773;
  text-align: center;
}

/* 轮播 */
.carousel {
  padding: 10px 24px 4px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.carousel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.carousel-title {
  font-weight: 700;
  color: #ff3f87;
}
.carousel-actions {
  display: flex;
  gap: 8px;
}
.carousel-window {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 12px 28px rgba(255, 165, 199, 0.25);
}
.carousel-track {
  display: flex;
  transition: transform 0.45s ease;
  width: 100%;
}
.slide {
  min-width: 100%;
  position: relative;
  cursor: pointer;
}
.slide img {
  width: 100%;
  height: 360px;
  object-fit: cover;
}
.slide-mask {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 55%, rgba(0, 0, 0, 0.32));
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 14px 16px;
  color: #fff;
  gap: 4px;
}
.slide-title {
  font-weight: 600;
}
.slide-meta {
  font-size: 12px;
  opacity: 0.85;
}
.pill {
  border: 1px solid rgba(255, 180, 205, 0.9);
  border-radius: 12px;
  padding: 4px 10px;
  background: #fff7fb;
  cursor: pointer;
  color: #b05f7a;
}
.pill.ghost:hover {
  background: #ffe2ef;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 6px 24px 0;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar .left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.upload-btn,
.manage-btn {
  border: none;
  border-radius: 20px;
  padding: 8px 18px;
  cursor: pointer;
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
  font-size: 13px;
  box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4);
}
.manage-btn {
  background: linear-gradient(135deg, #ffb2cc, #ff8db8);
}
.manage-btn.active {
  background: linear-gradient(135deg, #fca9c9, #ff88b3);
}
.selected-tip {
  font-size: 12px;
  color: #a35d76;
}
.danger-btn {
  border: none;
  border-radius: 14px;
  padding: 6px 12px;
  background: linear-gradient(135deg, #ff9c9c, #ff6b6b);
  color: #fff;
  box-shadow: 0 4px 10px rgba(255, 100, 120, 0.4);
  cursor: pointer;
}
.toolbar .right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.view-switch,
.sort {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.view-pill,
.sort-pill {
  border-radius: 999px;
  border: 1px solid rgba(255, 180, 205, 0.9);
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
}
.view-pill.active,
.sort-pill.active {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
}
.gallery {
  padding: 16px 24px 10px;
}
.gallery.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}
.gallery.grid .photo {
  height: 320px;
}
.gallery.masonry {
  column-count: 4;
  column-gap: 18px;
}
.gallery.masonry .photo {
  break-inside: avoid;
  margin-bottom: 18px;
}
.gallery.large {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.gallery.large .photo {
  display: flex;
  min-height: 190px;
}
.gallery.large .photo img {
  width: 45%;
  height: 100%;
  object-fit: cover;
}
.gallery.large .caption {
  flex: 1;
  padding: 16px;
}
.gallery.empty {
  display: flex !important;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.empty-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 320px;
  width: 100%;
}
.empty-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
  font-size: 20px;
  color: #a35d76;
  text-align: center;
}
.photo {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  background: #ffeaf3;
  box-shadow: 0 10px 20px rgba(255, 153, 187, 0.28);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border 0.15s ease;
  display: flex;
  flex-direction: column;
}
.gallery.grid .photo {
  min-height: 230px;
}
.photo img {
  width: 100%;
  height: 78%;
  object-fit: cover;
  background: #fce6f0;
}
.gallery.masonry .photo img {
  height: auto;
}
.caption {
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.caption .title {
  font-size: 13px;
  color: #613448;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}
.caption .date {
  font-size: 11px;
  color: #b57a90;
}
.photo.batch-mode::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0);
  transition: background 0.15s ease;
}
.photo.selected {
  border: 2px solid #ff6fa5;
  box-shadow: 0 0 0 2px rgba(255, 152, 201, 0.5), 0 10px 24px rgba(255, 152, 201, 0.5);
}
.select-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #ff8cb7;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #ff4c8a;
  z-index: 2;
}
.photo:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 26px rgba(255, 153, 187, 0.4);
}
.footer-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin-top: auto;
  padding-bottom: 16px;
}
.pagination {
  display: flex;
  justify-content: center;
}
:deep(.el-pagination.is-background .el-pager li) {
  background-color: #ffeef5;
  border-radius: 999px;
  color: #b26a84;
}
:deep(.el-pagination.is-background .el-pager li.is-active) {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
}
:deep(.el-pagination.is-background .el-pager li:hover) {
  background-color: #ffdce9;
}
:deep(.el-pagination button) {
  background-color: #ffeef5;
  border-radius: 999px;
  color: #b26a84;
}
:deep(.el-pagination button.is-disabled) {
  opacity: 0.5;
}
footer {
  text-align: center;
  font-size: 12px;
  color: #b57a90;
}
:deep(.pink-confirm .el-message-box__title) {
  color: #ff4c8a;
}
:deep(.pink-confirm .el-button--primary) {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  border: none;
}
:deep(.pink-confirm .el-button--default) {
  border-color: #ffb6cf;
  color: #b05f7a;
}
.mobile-topbar {
  display: none;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px 0;
  gap: 12px;
}
.mobile-brand {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: #d2517f;
}
.logo-mini {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
  border-radius: 10px;
  padding: 6px;
  font-size: 12px;
}
.drawer {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 20;
}
.drawer.open {
  pointer-events: auto;
}
.drawer-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  opacity: 0;
  transition: opacity 0.2s ease;
}
.drawer.open .drawer-mask {
  opacity: 1;
}
.drawer-panel {
  position: absolute;
  top: 0;
  left: -260px;
  width: 240px;
  height: 100%;
  background: #fff7fb;
  border-right: 1px solid rgba(255, 190, 210, 0.6);
  padding: 16px;
  transition: left 0.2s ease;
  display: flex;
  flex-direction: column;
}
.drawer.open .drawer-panel {
  left: 0;
}
.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.drawer .brand {
  display: flex;
  gap: 10px;
  align-items: center;
}
.drawer .brand .icon {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  width: 32px;
  height: 32px;
  border-radius: 10px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.drawer .brand h1 {
  margin: 0;
  font-size: 16px;
  color: #ff4c8a;
}
.drawer .brand p {
  margin: 0;
  font-size: 12px;
  color: #b6788d;
}

@media (max-width: 1200px) {
  .gallery.grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .gallery.masonry {
    column-count: 3;
  }
}
@media (max-width: 900px) {
  .sidebar {
    display: none;
  }
  .mobile-topbar {
    display: flex;
  }
  .topbar {
    padding: 12px 16px;
  }
  .hero {
    grid-template-columns: 1fr;
    padding-inline: 16px;
  }
  .toolbar {
    padding-inline: 16px;
    flex-direction: column;
    align-items: flex-start;
  }
  .toolbar .right {
    align-items: flex-start;
  }
  .gallery {
    padding-inline: 16px;
  }
  .gallery.grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .gallery.grid .photo {
    height: 260px;
  }
  .gallery.masonry {
    column-count: 2;
  }
  .carousel {
    padding-inline: 16px;
  }
  .slide img {
    height: 240px;
  }
}
@media (max-width: 640px) {
  .topbar .right {
    display: none;
  }
  .hero-left h2 {
    font-size: 20px;
  }
  .stats {
    gap: 10px;
  }
  .upload-btn,
  .manage-btn,
  .danger-btn {
    width: 100%;
    justify-content: center;
    display: inline-flex;
  }
  .toolbar .left {
    width: 100%;
  }
  .gallery.grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .gallery.masonry {
    column-count: 1;
  }
}
</style>
