<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface GalleryImage {
  id: number
  displayName: string
  created_at?: string
  thumbUrl: string
  fullUrl: string
  tags?: string[]
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const palette = ['#ff9db8', '#8ed0ff', '#ffd27f', '#9dd0a5', '#c3a0ff', '#f7a3ff']

const tagId = computed(() => Number(route.params.id))
const tagName = ref((route.query.name as string) || '')
const tagColor = ref('#ff9db8')

const viewMode = ref<'grid' | 'masonry' | 'large'>('grid')
const sortOrder = ref<'newest' | 'oldest'>('newest')
const currentPage = ref(1)
const pageSize = ref(12)
const images = ref<GalleryImage[]>([])
const total = ref(0)
const loading = ref(false)

const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (path: string) => (!path ? '' : path.startsWith('http') ? path : `${apiBase}${path}`)

const navOpen = ref(false)
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
watch(() => route.fullPath, () => closeNav())

function normalizeColor(raw?: string | null, idx = 0, name = '') {
  if (!raw) return palette[(idx + name.length) % palette.length]
  const hex = raw.match(/^#([0-9a-fA-F]{6})/)
  if (hex) return `#${hex[1]}`
  const rgba = raw.match(/^rgba?\((\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})/)
  if (rgba) {
    const [r, g, b] = rgba.slice(1, 4).map(n => Math.max(0, Math.min(255, Number(n))))
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
  }
  return palette[(idx + name.length) % palette.length]
}

function fallbackToRaw(event: Event, url: string) {
  const img = event.target as HTMLImageElement | null
  if (img && img.src !== url) img.src = url
}

async function fetchImages() {
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/tags/${tagId.value}/images`, {
      params: { page: currentPage.value, page_size: pageSize.value, sort: sortOrder.value },
    })
    const tokenParam = authStore.token ? `?jwt=${authStore.token}` : ''
    const tag = res.data.tag
    if (tag) {
      tagName.value = tag.name
      tagColor.value = normalizeColor(tag.color, 0, tag.name)
      total.value = tag.count || res.data.total || 0
    } else {
      total.value = res.data.total || 0
    }
    images.value = (res.data.items || []).map((item: any) => ({
      ...item,
      thumbUrl: withBase((item.thumb_url || `/api/v1/images/${item.id}/thumb`) + tokenParam),
      fullUrl: withBase((item.raw_url || `/api/v1/images/${item.id}/raw`) + tokenParam),
      displayName: item.name || item.original_name,
    }))
    total.value = res.data.total || total.value
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '获取图片失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  currentPage.value = p
  fetchImages()
}
function changeView(mode: 'grid' | 'masonry' | 'large') {
  viewMode.value = mode
}
function goDetail(id: number) {
  router.push(`/images/${id}`)
}
function goBack() {
  router.push('/tags')
}

watch(
  () => route.params.id,
  () => {
    currentPage.value = 1
    fetchImages()
  }
)

onMounted(() => {
  fetchImages()
})

/* 轮播逻辑 */
const sliderImages = computed(() => images.value.slice(0, 8))
const currentSlide = ref(0)
const sliderTimer = ref<number | null>(null)
const hasSlider = computed(() => sliderImages.value.length > 0)
const nextSlide = () => {
  if (!sliderImages.value.length) return
  currentSlide.value = (currentSlide.value + 1) % sliderImages.value.length
}
const prevSlide = () => {
  if (!sliderImages.value.length) return
  currentSlide.value = (currentSlide.value - 1 + sliderImages.value.length) % sliderImages.value.length
}
const startSlider = () => {
  stopSlider()
  if (!sliderImages.value.length) return
  sliderTimer.value = window.setInterval(nextSlide, 4000)
}
const stopSlider = () => {
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
        <a class="active">🏷️ 标签图片</a>
        <a @click="goBack">↩️ 返回标签管理</a>
      </nav>
    </aside>

    <main>
      <header class="mobile-topbar">
        <button class="icon-btn ghost" @click="toggleNav">☰</button>
        <div class="mobile-brand">
          <span class="logo-mini">🏷️</span>
          <span>{{ tagName || '标签图片' }}</span>
        </div>
        <button class="icon-btn ghost" @click="goBack">↩️</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">包含标签「{{ tagName }}」的图片</div>
          <div class="subtitle">共 {{ total }} 张 · 支持浏览模式切换与排序</div>
        </div>
        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}</span>
          <span class="tag-pill" :style="{ background: tagColor + '33', borderColor: tagColor }">
            <span class="dot" :style="{ background: tagColor }"></span>{{ tagName }}
          </span>
        </div>
      </header>

      <div class="drawer" :class="{ open: navOpen }">
        <div class="drawer-mask" @click="closeNav"></div>
        <div class="drawer-panel">
          <div class="drawer-head">
            <div class="brand">
              <div class="icon">📸</div>
              <div class="text">
                <h1>标签图片</h1>
                <p>{{ tagName }}</p>
              </div>
            </div>
            <button class="icon-btn ghost" @click="closeNav">✕</button>
          </div>
          <nav>
            <a class="active">🏷️ 标签图片</a>
            <a @click="goBack">↩️ 返回标签管理</a>
            <a @click="go('/')">🏠 首页</a>
          </nav>
        </div>
      </div>

      <section v-if="hasSlider" class="carousel" @mouseenter="stopSlider" @mouseleave="startSlider">
        <div class="carousel-head">
          <div class="carousel-title">标签精选轮播</div>
          <div class="carousel-actions">
            <button class="pill ghost" @click="prevSlide">‹</button>
            <button class="pill ghost" @click="nextSlide">›</button>
          </div>
        </div>
        <div class="carousel-window">
          <div class="carousel-track" :style="{ transform: `translateX(-${currentSlide * 100}%)` }">
            <div
              v-for="img in sliderImages"
              :key="img.id"
              class="slide"
              @click="goDetail(img.id)"
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
      </section>

      <section class="gallery-wrap">
        <div :class="['gallery', viewMode]">
          <div v-if="!loading && images.length === 0" class="empty-box">
            <div class="empty-row">
              <span>这个标签下还没有图片哦，快去上传一张吧～</span>
            </div>
          </div>
          <div
            v-for="img in images"
            v-else
            :key="img.id"
            class="photo"
            @click="goDetail(img.id)"
          >
            <img :src="img.thumbUrl" :alt="img.displayName" loading="lazy" @error="fallbackToRaw($event, img.fullUrl)" />
            <div class="caption">
              <div class="title">{{ img.displayName }}</div>
              <div class="date">{{ img.created_at?.slice(0, 10) }}</div>
            </div>
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
.sidebar { width: 200px; background: linear-gradient(180deg, #fff7fb, #ffeef5); border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 18px; position: sticky; top: 0; height: 100vh; }
.logo { display: flex; gap: 10px; margin-bottom: 20px; }
.logo .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 36px; height: 36px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.logo h1 { font-size: 18px; color: #ff4c8a; margin: 0; }
.logo p { font-size: 11px; color: #b6788d; margin: 0; }
nav a { display: block; padding: 8px 12px; border-radius: 12px; font-size: 13px; color: #6b3c4a; margin: 2px 0; cursor: pointer; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }

main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.92); }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.welcome { font-size: 13px; color: #8c546e; }
.tag-pill { padding: 6px 10px; border-radius: 999px; border: 1px solid transparent; color: #b05f7a; display: inline-flex; align-items: center; gap: 6px; }
.tag-pill .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }

/* 轮播 */
.carousel { padding: 10px 20px 8px; display: flex; flex-direction: column; gap: 8px; }
.carousel-head { display: flex; align-items: center; justify-content: space-between; }
.carousel-title { font-weight: 700; color: #ff3f87; }
.carousel-actions { display: flex; gap: 8px; }
.carousel-window { position: relative; overflow: hidden; border-radius: 16px; background: rgba(255, 255, 255, 0.9); box-shadow: 0 12px 24px rgba(255, 165, 199, 0.28); }
.carousel-track { display: flex; transition: transform 0.45s ease; width: 100%; }
.slide { min-width: 100%; position: relative; cursor: pointer; }
.slide img { width: 100%; height: 300px; object-fit: cover; }
.slide-mask { position: absolute; inset: 0; background: linear-gradient(180deg, transparent 55%, rgba(0,0,0,0.35)); display: flex; flex-direction: column; justify-content: flex-end; padding: 12px 14px; color: #fff; gap: 4px; }
.slide-title { font-weight: 600; }
.slide-meta { font-size: 12px; opacity: 0.9; }
.pill { border: 1px solid rgba(255, 180, 205, 0.9); border-radius: 12px; padding: 4px 10px; background: #fff7fb; cursor: pointer; color: #b05f7a; }
.pill.ghost:hover { background: #ffe2ef; }

.toolbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px 6px; flex-wrap: wrap; gap: 10px; }
.view-switch, .sort { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.view-pill, .sort-pill { border: none; border-radius: 16px; padding: 8px 12px; background: #ffeef5; color: #b05f7a; cursor: pointer; }
.view-pill.active, .sort-pill.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }

.gallery-wrap { padding: 6px 18px 10px; flex: 1; display: flex; }
.gallery { flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; align-content: flex-start; }
.gallery.masonry { display: block; column-count: 3; column-gap: 16px; }
.gallery.masonry .photo { display: inline-flex; width: 100%; break-inside: avoid; margin-bottom: 16px; }
.gallery.masonry .photo img { height: auto; }
.gallery.large { display: flex; flex-direction: column; gap: 16px; }
.gallery.large .photo { display: flex; flex-direction: row; height: 190px; }
.gallery.large .photo img { width: 45%; height: 100%; object-fit: cover; }
.gallery.large .caption { flex: 1; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; align-items: flex-start; }
.gallery .empty-box { grid-column: 1 / -1; padding: 40px; text-align: center; color: #b6788d; background: rgba(255, 255, 255, 0.9); border-radius: 14px; }

.photo { background: rgba(255, 255, 255, 0.92); border-radius: 14px; box-shadow: 0 6px 16px rgba(255, 165, 199, 0.3); overflow: hidden; cursor: pointer; display: flex; flex-direction: column; transition: transform 0.1s ease; }
.photo:hover { transform: translateY(-2px); }
.photo img { width: 100%; height: 220px; object-fit: cover; background: #ffeef5; }
.gallery.large .photo img { height: 100%; }
.caption { padding: 10px 12px 12px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #5a2f3d; }
.caption .date { color: #b57a90; }
.empty-row { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; font-size: 18px; color: #a35d76; text-align: center; }

.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding: 8px 0 16px; }
.pagination { display: flex; justify-content: center; }
:deep(.el-pagination.is-background .el-pager li) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination.is-background .el-pager li.is-active) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
:deep(.el-pagination.is-background .el-pager li:hover) { background-color: #ffdce9; }
:deep(.el-pagination button) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination button.is-disabled) { opacity: 0.5; }
footer { text-align: center; font-size: 12px; color: #b57a90; }

/* 移动端 */
.mobile-topbar { display: none; align-items: center; justify-content: space-between; padding: 10px 16px 0; gap: 12px; }
.mobile-brand { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #d2517f; }
.logo-mini { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; border-radius: 10px; padding: 6px; font-size: 12px; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn.ghost { background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(255, 190, 210, 0.7); }

.drawer { position: fixed; inset: 0; pointer-events: none; z-index: 20; }
.drawer.open { pointer-events: auto; }
.drawer-mask { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.35); opacity: 0; transition: opacity 0.2s ease; }
.drawer.open .drawer-mask { opacity: 1; }
.drawer-panel { position: absolute; top: 0; left: -260px; width: 240px; height: 100%; background: #fff7fb; border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 16px; transition: left 0.2s ease; display: flex; flex-direction: column; }
.drawer.open .drawer-panel { left: 0; }
.drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.drawer .brand { display: flex; gap: 10px; align-items: center; }
.drawer .brand .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 32px; height: 32px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.drawer .brand h1 { margin: 0; font-size: 16px; color: #ff4c8a; }
.drawer .brand p { margin: 0; font-size: 12px; color: #b6788d; }

@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .gallery { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }
  .gallery.masonry { column-count: 2; }
  .toolbar { padding-inline: 12px; }
  .gallery-wrap { padding-inline: 12px; }
  .carousel { padding-inline: 12px; }
  .slide img { height: 240px; }
}
@media (max-width: 640px) {
  .gallery { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gallery.masonry { column-count: 1; }
  .topbar .right { display: none; }
  .sort { width: 100%; justify-content: flex-start; }
  .view-switch { width: 100%; }
}
</style>
