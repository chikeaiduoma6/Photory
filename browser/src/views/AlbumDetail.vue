<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface Image {
  id: number
  name: string
  filename: string
  original_name: string
  mime_type: string
  size: number
  width?: number
  height?: number
  taken_at?: string
  created_at: string
  thumb_path?: string
  visibility: string
}

interface Album {
  id: number
  title: string
  user_id: number
  visibility: string
  created_at: string
  image_count: number
  cover_image?: Image
}


const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const albumId = computed(() => parseInt(route.params.id as string))
const album = ref<Album | null>(null)
const images = ref<Image[]>([])
const loading = ref(false)
const imageLoading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const sortOrder = ref('created_desc')
const navOpen = ref(false)
const currentPath = computed(() => router.currentRoute.value.path)
const go = (path: string) => { router.push(path); navOpen.value = false }
const isActive = (path: string) => currentPath.value === path || currentPath.value.startsWith(path + '/')
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
const carouselVisible = ref(false)
const currentImageIndex = ref(0)
const addImageModalVisible = ref(false)
const availableImages = ref<Image[]>([])
const selectedImages = ref<number[]>([])
const selectingImages = ref(false)
const availablePage = ref(1)
const availablePageSize = ref(30)
const availableTotal = ref(0)
const viewMode = ref('grid') // 添加浏览模式：grid(网格)、list(列表)、masonry(瀑布流)、large(大卡片)

// 添加进入轮播模式的函数
function enterCarouselMode() {
  if (images.value.length > 0) {
    currentImageIndex.value = 0
    carouselVisible.value = true
  } else {
    ElMessage.warning('相册中没有图片，无法进入轮播模式')
  }
}

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

async function fetchAlbum() {
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/albums/${albumId.value}`)
    album.value = res.data.album
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '获取相册信息失败')
    router.push('/albums')
  } finally {
    loading.value = false
  }
}

async function fetchAlbumImages() {
  imageLoading.value = true
  try {
    const res = await axios.get(`/api/v1/albums/${albumId.value}/images`, {
      params: {
        page: page.value,
        page_size: pageSize.value,
        sort: sortOrder.value
      }
    })
    images.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '获取相册图片失败')
  } finally {
    imageLoading.value = false
  }
}

async function removeImageFromAlbum(imageId: number) {
  try {
    await axios.delete(`/api/v1/albums/${albumId.value}/images/${imageId}`)
    ElMessage.success('图片已从相册中移除')
    await fetchAlbumImages()
    await fetchAlbum() // 更新相册信息（图片数量）
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '移除图片失败')
  }
}

async function fetchAvailableImages() {
  selectingImages.value = true
  try {
    const res = await axios.get(`/api/v1/images`, {
      params: {
        page: availablePage.value,
        page_size: availablePageSize.value,
        sort: 'newest'
      }
    })
    availableImages.value = res.data.items
    availableTotal.value = res.data.total
  } catch (e: any) {
    console.error('获取图片列表失败:', e)
    ElMessage.error(e?.response?.data?.message || '获取图片列表失败')
  } finally {
    selectingImages.value = false
  }
}

async function addImagesToAlbum() {
  if (selectedImages.value.length === 0) {
    ElMessage.warning('请选择要添加的图片')
    return
  }
  
  const addingImages = [...selectedImages.value]
  selectedImages.value = []
  addImageModalVisible.value = false
  
  try {
    for (const imageId of addingImages) {
      await axios.post(`/api/v1/albums/${albumId.value}/images/${imageId}`)
    }
    ElMessage.success(`成功添加${addingImages.length}张图片到相册`)
    await fetchAlbumImages()
    await fetchAlbum()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '添加图片失败')
  }
}

function toggleImageSelection(imageId: number) {
  const index = selectedImages.value.indexOf(imageId)
  if (index > -1) {
    selectedImages.value.splice(index, 1)
  } else {
    selectedImages.value.push(imageId)
  }
}

function isImageSelected(imageId: number) {
  return selectedImages.value.includes(imageId)
}

function handleAvailablePageChange(newPage: number) {
  availablePage.value = newPage
  fetchAvailableImages()
}

function openImageViewer(index: number) {
  currentImageIndex.value = index
  carouselVisible.value = true
  // 确保页面滚动到顶部
  window.scrollTo(0, 0)
}

function closeImageViewer() {
  carouselVisible.value = false
}

function openAddImageModal() {
  addImageModalVisible.value = true
  fetchAvailableImages()
}



function handlePageChange(newPage: number) {
  page.value = newPage
  fetchAlbumImages()
}

// 格式化日期函数
function formatDate(dateString: string): string {
  if (!dateString) return ''
  return dateString.slice(0, 10)
}

onMounted(() => {
  fetchAlbum()
  fetchAlbumImages()
})

watch(() => albumId.value, () => {
  page.value = 1
  fetchAlbum()
  fetchAlbumImages()
})
</script>

<template>
  <div class="dashboard album-detail-page">
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
          <span>相册详情</span>
        </div>
        <button class="icon-btn ghost" @click="go('/albums')">⬅️</button>
      </header>
      <header class="topbar">
        <div class="left">
          <button class="back-btn ghost" @click="go('/albums')">⬅️ 返回</button>
          <div class="title-container">
            <div class="title">{{ album?.title }} · 相册详情</div>
            <div class="subtitle">创建于 {{ album?.created_at.slice(0, 10) }} · 共 {{ album?.image_count }} 张图片</div>
          </div>
        </div>
        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}</span>
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
                <p>专属相册</p>
              </div>
            </div>
            <button class="icon-btn ghost" @click="closeNav">✕</button>
          </div>
          <nav>
            <a v-for="item in links" :key="item.path" :class="{ active: isActive(item.path) }" @click="go(item.path)">
              {{ item.icon }} {{ item.label }}
            </a>
          </nav>
        </div>
      </div>
      
      <section class="album-info-section">
        <div v-if="loading" class="loading-box">加载中...</div>
        <div v-else class="album-info">
          <div class="cover" :style="{ backgroundImage: album?.cover_image ? `url('/api/v1/images/${album?.cover_image?.id}/thumb')` : undefined }">
            <span v-if="!album?.cover_image" class="cover-placeholder">📚</span>
          </div>
          <div class="info">
            <h2>{{ album?.title }}</h2>
            <p class="meta">创建于 {{ album?.created_at.slice(0, 10) }}</p>
            <p class="count">共 {{ album?.image_count }} 张图片</p>
            <div class="actions">
              <button class="btn primary" @click="openAddImageModal">
                + 添加图片到相册
              </button>
            </div>
          </div>
        </div>
      </section>
      
      <section class="images-section">
        <div class="section-header">
          <h3>相册图片</h3>
          <div class="actions-bar">
            <div class="view-options">
              <span>浏览模式：</span>
              <button 
                class="view-btn" 
                :class="{ active: viewMode.value === 'grid' }" 
                @click="viewMode.value = 'grid'"
              >
                📋 网格
              </button>
              <button 
                class="view-btn" 
                :class="{ active: viewMode.value === 'list' }" 
                @click="viewMode.value = 'list'"
              >
                📝 列表
              </button>
              <button 
                class="view-btn" 
                :class="{ active: viewMode.value === 'masonry' }" 
                @click="viewMode.value = 'masonry'"
              >
                🌊 瀑布流
              </button>
              <button 
                class="view-btn" 
                :class="{ active: viewMode.value === 'large' }" 
                @click="viewMode.value = 'large'"
              >
                📷 大卡片
              </button>
            </div>
            <div class="sort-options">
                <span>排序方式：</span>
                <select v-model="sortOrder" @change="fetchAlbumImages" class="sort-select">
                  <optgroup label="添加时间">
                    <option value="added_desc">晚到早</option>
                    <option value="added_asc">早到晚</option>
                  </optgroup>
                  <optgroup label="上传时间">
                    <option value="created_desc">晚到早</option>
                    <option value="oldest">早到晚</option>
                  </optgroup>
                  <optgroup label="图片名称">
                    <option value="name_asc">A-Z</option>
                    <option value="name_desc">Z-A</option>
                  </optgroup>
                  <optgroup label="拍摄时间">
                    <option value="taken_desc">晚到早</option>
                    <option value="taken_asc">早到晚</option>
                  </optgroup>
                </select>
              </div>
            <button 
              class="btn primary" 
              @click="enterCarouselMode" 
              :disabled="images.length === 0"
            >
              🎬 进入轮播模式
            </button>
          </div>
        </div>
        
        <div v-if="imageLoading" class="loading-box">加载图片中...</div>
        <div v-else-if="!images.length" class="empty-box">
          <div>相册中还没有图片，快去添加吧！</div>
        </div>
        <div v-else class="images-container" :class="viewMode.value">
          <div class="image-card" v-for="(image, index) in images" :key="image.id">
            <div class="image-wrapper" @click="openImageViewer(index)">
              <img :src="`/api/v1/images/${image.id}/thumb`" :alt="image.original_name" />
              <div class="image-actions">
                <button class="icon-btn danger" @click.stop="removeImageFromAlbum(image.id)">🗑️</button>
              </div>
            </div>
            <div class="image-info">
              <div class="image-name">{{ image.original_name }}</div>
              <div v-if="viewMode === 'list'" class="image-meta">
                <span class="meta-item">尺寸: {{ image.width }} × {{ image.height }}</span>
                <span class="meta-item">大小: {{ image.size }}</span>
                <span class="meta-item">创建日期: {{ formatDate(image.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="pagination" v-if="total > pageSize">
          <button 
            class="page-btn" 
            :disabled="page === 1" 
            @click="handlePageChange(page - 1)"
          >
            上一页
          </button>
          <span class="page-info">第 {{ page }} 页 / 共 {{ Math.ceil(total / pageSize) }} 页</span>
          <button 
            class="page-btn" 
            :disabled="page >= Math.ceil(total / pageSize)" 
            @click="handlePageChange(page + 1)"
          >
            下一页
          </button>
        </div>
      </section>
      
      <!-- 添加图片模态框 -->
      <div class="modal-overlay" v-if="addImageModalVisible" @click="addImageModalVisible = false">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3>添加图片到相册</h3>
            <button class="modal-close" @click="addImageModalVisible = false">✕</button>
          </div>
          <div class="modal-body">
            <div v-if="selectingImages" class="loading-box">加载图片中...</div>
            <div v-else-if="!availableImages.length" class="empty-box">
              <div>没有找到可用的图片</div>
            </div>
            <div v-else class="available-images-grid">
              <div 
                class="available-image-card" 
                v-for="image in availableImages" 
                :key="image.id"
                :class="{ selected: isImageSelected(image.id) }"
                @click="toggleImageSelection(image.id)"
              >
                <div class="image-wrapper">
                  <img :src="`/api/v1/images/${image.id}/thumb`" :alt="image.original_name" />
                  <div class="selection-indicator" v-if="isImageSelected(image.id)">✓</div>
                </div>
              </div>
            </div>
            
            <div class="modal-pagination" v-if="availableTotal > availablePageSize">
              <button 
                class="page-btn" 
                :disabled="availablePage === 1" 
                @click="handleAvailablePageChange(availablePage - 1)"
              >
                上一页
              </button>
              <span class="page-info">第 {{ availablePage }} 页 / 共 {{ Math.ceil(availableTotal / availablePageSize) }} 页</span>
              <button 
                class="page-btn" 
                :disabled="availablePage >= Math.ceil(availableTotal / availablePageSize)" 
                @click="handleAvailablePageChange(availablePage + 1)"
              >
                下一页
              </button>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn cancel" @click="addImageModalVisible = false">取消</button>
            <button class="btn primary" @click="addImagesToAlbum" :disabled="selectedImages.length === 0">
              添加选中图片 ({{ selectedImages.length }})
            </button>
          </div>
        </div>
      </div>
      
      <!-- 图片轮播组件 -->
      <div class="carousel-overlay" v-if="carouselVisible" @click="closeImageViewer">
        <div class="carousel-container" @click.stop>
          <button class="carousel-close" @click="closeImageViewer">✕</button>
          <div class="carousel-content">
            <img 
              :src="`/api/v1/images/${images[currentImageIndex].id}/original`" 
              :alt="images[currentImageIndex].original_name"
              class="carousel-image"
            />
          </div>
          <div class="carousel-nav">
            <button 
              class="nav-btn" 
              :disabled="currentImageIndex === 0" 
              @click="currentImageIndex--"
            >
              ◀️
            </button>
            <span class="nav-info">{{ currentImageIndex + 1 }} / {{ images.length }}</span>
            <button 
              class="nav-btn" 
              :disabled="currentImageIndex === images.length - 1" 
              @click="currentImageIndex++"
            >
              ▶️
            </button>
          </div>
        </div>
      </div>
      
      <div class="footer-wrapper">
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
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #ffeef5, #ffe5f0);
  color: var(--text-strong);
}

.sidebar { width: 240px; background: linear-gradient(180deg, #fff7fb, #ffeef5); border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 20px; position: sticky; top: 0; height: 100vh; }
.logo { display: flex; gap: 10px; margin-bottom: 20px; }
.logo .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 36px; height: 36px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.logo h1 { font-size: 18px; color: #ff4c8a; margin: 0; }
.logo p { font-size: 11px; color: #b6788d; margin: 0; }
nav a { display: block; padding: 9px 12px; border-radius: 12px; font-size: 14px; color: #6b3c4a; margin: 4px 0; cursor: pointer; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }

main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }

.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255,255,255,0.92);}
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; margin-top: 4px;}
.subtitle { font-size: 12px; color: #a36e84; }
.left { display: flex; align-items: center; gap: 16px; }
.right { display: flex; align-items: center; gap: 8px; }
.welcome { font-size: 13px; color: #8c546e; }

.mobile-topbar { display: none; align-items: center; justify-content: space-between; padding: 10px 16px 0; gap: 12px; }
.mobile-brand { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #d2517f; }
.logo-mini { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; border-radius: 10px; padding: 6px; font-size: 12px; }

.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.icon-btn.ghost { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); }
.icon-btn.danger { background: #ff6b9d; color: white; }
.icon-btn:hover { opacity: 0.8; }

/* 返回按钮样式 */
.back-btn { background: #ffeef5; border: none; border-radius: 8px; padding: 8px 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 4px; font-size: 14px; }
.back-btn.ghost { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); color: #ff4c8a; }
.back-btn:hover { opacity: 0.8; }

.drawer { position: fixed; inset: 0; pointer-events: none; z-index: 20; }
.drawer.open { pointer-events: auto; }
.drawer-mask { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.35); opacity: 0; transition: opacity 0.2s ease; }
.drawer.open .drawer-mask { opacity: 1; }
.drawer-panel { position: absolute; top: 0; left: -260px; width: 240px; height: 100%; background: #fff7fb; border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 16px; transition: left 0.2s ease; display: flex; flex-direction: column; }
.drawer.open .drawer-panel { left: 0; }
.drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.drawer .brand { display: flex; gap: 10px; align-items: center; }
.drawer .brand .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 32px; height: 32px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.drawer .brand h1 { margin: 0; font-size: 16px; color: #ff4c8a;}
.drawer .brand p { margin: 0; font-size: 12px; color: #b6788d;}

.album-info-section { margin: 20px 24px; background: rgba(255,255,255,0.95); border-radius: 18px; padding: 20px; box-shadow: 0 10px 24px rgba(255,153,187,0.19); }
.album-info { display: flex; gap: 20px; align-items: center; }
.cover { width: 120px; height: 120px; background: #ffe3f0; border-radius: 12px; background-size: cover; background-position: center; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.cover-placeholder { font-size: 48px; color: #ec7aa7; opacity: 0.32; }
.info h2 { margin: 0; color: #ff4c8a; font-size: 24px; }
.info .meta { margin: 4px 0; font-size: 14px; color: #a36e84; }
.info .count { margin: 4px 0; font-size: 14px; color: #8c546e; }

.images-section { margin: 0 24px 24px; background: rgba(255,255,255,0.95); border-radius: 18px; padding: 20px; box-shadow: 0 10px 24px rgba(255,153,187,0.19); }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.section-header h3 { margin: 0; color: #ff4c8a; font-size: 18px; }
.sort-options { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #8c546e; }

.sort-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #ffccd5;
  border-radius: 8px;
  background-color: #fff0f5;
  color: #ff4c8a;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.sort-select:hover {
  background-color: #ffe6ec;
  border-color: #ff69b4;
}

.sort-select:focus {
  outline: none;
  border-color: #ff69b4;
  box-shadow: 0 0 0 2px rgba(255, 105, 180, 0.2);
}
.sort-btn { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); border-radius: 8px; padding: 6px 12px; cursor: pointer; font-size: 13px; color: #8c546e; }
.sort-btn.active { background: #ffeef5; color: #ff4c8a; border-color: #ff8bb3; }
.sort-btn:hover { opacity: 0.8; }

/* 浏览模式和操作栏样式 */
.actions-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.view-options {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #8c546e;
}

.view-btn {
  background: rgba(255,255,255,0.65);
  border: 1px solid rgba(255, 190, 210, 0.7);
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #8c546e;
}

.view-btn.active {
  background: #ffeef5;
  color: #ff4c8a;
  border-color: #ff8bb3;
}

.view-btn:hover {
  opacity: 0.8;
}

/* 列表模式样式 */
.images-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.images-list .image-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px;
  border-radius: 12px;
  background: rgba(255, 240, 245, 0.5);
}

.images-list .image-wrapper {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}

.images-list .image-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.images-list .image-name {
  font-weight: 500;
  color: #ff4c8a;
}

.image-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #a36e84;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 瀑布流模式样式 */
.images-container.masonry {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  grid-auto-rows: minmax(100px, auto);
  grid-gap: 1rem;
  grid-auto-flow: dense;
  margin-bottom: 20px;
}

.images-container.masonry .image-card {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(255,153,187,0.12);
  transition: transform 0.2s ease;
}

.images-container.masonry .image-card:hover {
  transform: translateY(-2px);
}

.images-container.masonry .image-wrapper {
  aspect-ratio: unset;
  overflow: hidden;
}

.images-container.masonry .image-wrapper img {
  width: 100%;
  height: auto;
  object-fit: cover;
}

.images-container.masonry .image-info {
  padding: 8px;
  background: rgba(255, 240, 245, 0.5);
}

.images-container.masonry .image-name {
  font-size: 14px;
  font-weight: 500;
  color: #ff4c8a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 大卡片模式样式 */
.images-container.large {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  margin-bottom: 20px;
}

.images-container.large .image-card {
  background-color: rgba(255,255,255,0.95);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(255,153,187,0.12);
  transition: transform 0.2s ease;
}

.images-container.large .image-card:hover {
  transform: translateY(-2px);
}

.images-container.large .image-wrapper {
  aspect-ratio: unset;
  overflow: hidden;
}

.images-container.large .image-wrapper img {
  width: 100%;
  height: auto;
  max-height: 500px;
  object-fit: cover;
}

.images-container.large .image-info {
  padding: 1rem;
  background: rgba(255, 240, 245, 0.5);
}

.images-container.large .image-name {
  font-size: 1.2rem;
  font-weight: 500;
  color: #ff4c8a;
  margin-bottom: 0.5rem;
}

.images-container.large .image-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 14px;
  color: #a36e84;
}

.images-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px; }
.image-card { position: relative; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(255,153,187,0.12); }
.image-wrapper { cursor: pointer; aspect-ratio: 1; overflow: hidden; }
.image-wrapper img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.2s; }
.image-wrapper:hover img { transform: scale(1.05); }
.image-actions { position: absolute; bottom: 8px; right: 8px; display: flex; gap: 4px; }

.images-grid .image-info {
  padding: 8px;
  background: rgba(255, 240, 245, 0.5);
}

.images-grid .image-name {
  font-size: 14px;
  font-weight: 500;
  color: #ff4c8a;
}

.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; }
.page-btn { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); border-radius: 8px; padding: 6px 16px; cursor: pointer; font-size: 14px; color: #8c546e; }
.page-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.page-btn:hover:not(:disabled) { background: #ffeef5; color: #ff4c8a; border-color: #ff8bb3; }
.page-info { font-size: 14px; color: #8c546e; }

.loading-box, .empty-box { padding: 40px 0; text-align: center; color: #b6788d; }

.actions { margin-top: 12px; }
.btn { padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; border: none; }
.btn.primary { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: white; }
.btn.primary:hover { opacity: 0.9; }
.btn.cancel { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); color: #8c546e; margin-right: 8px; }
.btn.cancel:hover { background: #ffeef5; }

/* 模态框样式 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100; display: flex; align-items: center; justify-content: center; }
.modal-container { position: relative; background: white; border-radius: 16px; width: 90%; max-width: 800px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); }
.modal-header h3 { margin: 0; color: #ff4c8a; font-size: 18px; }
.modal-close { background: none; border: none; font-size: 24px; color: #8c546e; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer { display: flex; justify-content: flex-end; padding: 16px 20px; border-top: 1px solid rgba(255, 190, 210, 0.5); }

.available-images-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin-bottom: 20px; }
.available-image-card { position: relative; border-radius: 8px; overflow: hidden; cursor: pointer; transition: all 0.2s; }
.available-image-card:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(255,153,187,0.2); }
.available-image-card.selected { border: 2px solid #ff6fa0; box-shadow: 0 0 0 2px rgba(255, 111, 160, 0.2); }
.available-image-card .image-wrapper { position: relative; aspect-ratio: 1; overflow: hidden; }
.available-image-card img { width: 100%; height: 100%; object-fit: cover; }
.selection-indicator { position: absolute; bottom: 4px; right: 4px; background: #ff6fa0; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold; }

.modal-pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; }

/* 轮播组件样式 */
.carousel-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 100; display: flex; align-items: center; justify-content: center; }
.carousel-container { position: relative; max-width: 90vw; max-height: 90vh; }
.carousel-close { position: absolute; top: -40px; right: 0; background: none; border: none; color: white; font-size: 24px; cursor: pointer; z-index: 10; }
.carousel-content { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.carousel-image { max-width: 100%; max-height: 80vh; object-fit: contain; }
.carousel-nav { position: absolute; bottom: -40px; left: 0; right: 0; display: flex; justify-content: center; align-items: center; gap: 16px; color: white; }
.nav-btn { background: rgba(255,255,255,0.2); border: none; color: white; font-size: 24px; cursor: pointer; padding: 8px 16px; border-radius: 8px; }
.nav-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.nav-info { font-size: 16px; }

/* 页脚布局修复 */
.footer-wrapper {
  margin-top: auto;
  padding: 16px 24px;
  text-align: center;
  font-size: 12px;
  color: #b6788d;
}

@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .album-info-section, .images-section { margin: 16px; }
  .album-info { flex-direction: column; text-align: center; }
  .images-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
}

@media (max-width: 640px) {
  .topbar .right { display: none; }
  .sort-options { flex-direction: column; align-items: flex-end; gap: 4px; }
  .actions-bar { flex-direction: column; align-items: flex-start; gap: 8px; }
  .images-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
  .image-meta {
    flex-direction: column;
    gap: 2px;
  }
}
</style>