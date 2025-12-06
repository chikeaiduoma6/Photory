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
  thumb_url?: string
  tags?: string[]
  tag_objects?: { id: number; name: string; color?: string | null }[]
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
const username = computed(() => authStore.user?.username || '鐠佸灝顓?)

const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (path: string) => (!path ? '' : path.startsWith('http') ? path : `${apiBase}${path}`)
const tokenParam = computed(() => (authStore.token ? `?jwt=${authStore.token}` : ''))
const albumId = computed(() => parseInt(route.params.id as string))
const album = ref<Album | null>(null)
const images = ref<Image[]>([])
const loading = ref(false)
const imageLoading = ref(false)
const page = ref(1)
const pageSize = ref(12)
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
const viewMode = ref('grid') // 濞ｈ濮炲ù蹇氼潔濡€崇础閿涙rid(缂冩垶鐗?閵嗕勾ist(閸掓銆?閵嗕沟asonry(閻庢垵绔峰ù?閵嗕勾arge(婢堆冨幢閻?
const viewModeClass = computed(() => {
  if (viewMode.value === 'grid') return 'images-grid'
  if (viewMode.value === 'list') return 'images-list'
  return viewMode.value
})

const imageThumbUrl = (id?: number) => (id ? withBase(`/api/v1/images/${id}/thumb`) + tokenParam.value : '')
const imageRawUrl = (id?: number) => (id ? withBase(`/api/v1/images/${id}/raw`) + tokenParam.value : '')
const coverThumb = (img?: Image | null) => {
  if (!img) return ''
  const raw = img.thumb_url || `/api/v1/images/${img.id}/thumb`
  return withBase(raw) + tokenParam.value
}

// 濞ｈ濮炴潻娑樺弳鏉烆喗鎸卞Ο鈥崇础閻ㄥ嫬鍤遍弫?
function enterCarouselMode() {
  if (images.value.length > 0) {
    currentImageIndex.value = 0
    carouselVisible.value = true
  } else {
    ElMessage.warning('閻╃鍞芥稉顓熺梾閺堝娴橀悧鍥风礉閺冪姵纭舵潻娑樺弳鏉烆喗鎸卞Ο鈥崇础')
  }
}

const links = [
  { label: '妫ｆ牠銆?, icon: '棣冨綌', path: '/' },
  { label: '閹兼粎鍌ㄥ鏇熸惛', icon: '棣冩敺', path: '/search' },
  { label: '娑撳﹣绱舵稉顓炵妇', icon: '閳戒緤绗?, path: '/upload' },
  { label: '閺嶅洨顒?, icon: '棣冨娇閿?, path: '/tags' },
  { label: '閺傚洣娆㈡径?, icon: '棣冩惂', path: '/folders' },
  { label: '閻╃鍞?, icon: '棣冩憥', path: '/albums' },
  { label: '閺呴缚鍏橀崚鍡欒', icon: '棣冾潵', path: '/smart' },
  { label: 'AI 瀹搞儰缍旈崣?, icon: '棣冾樆', path: '/ai' },
  { label: '娴犺濮熸稉顓炵妇', icon: '棣冃?, path: '/tasks' },
  { label: '閸ョ偞鏁圭粩?, icon: '棣冩閿?, path: '/recycle' },
  { label: '鐠佸墽鐤?, icon: '閳挎瑱绗?, path: '/settings' },
]

async function fetchAlbum() {
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/albums/${albumId.value}`)
    album.value = res.data.album
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '閼惧嘲褰囬惄绋垮斀娣団剝浼呮径杈Е')
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
    ElMessage.error(e?.response?.data?.message || '鑾峰彇鐩稿唽鍥剧墖澶辫触')
  } finally {
    imageLoading.value = false
  }
}

async function removeImageFromAlbum(imageId: number) {
  try {
    await axios.delete(`/api/v1/albums/${albumId.value}/images/${imageId}`)
    ElMessage.success('鍥剧墖宸蹭粠鐩稿唽涓Щ闄?)
    await fetchAlbumImages()
    await fetchAlbum() // 閺囧瓨鏌婇惄绋垮斀娣団剝浼呴敍鍫濇禈閻楀洦鏆熼柌蹇ョ礆
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '缁夊娅庨崶鍓у婢惰精瑙?)
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
    console.error('閼惧嘲褰囬崶鍓у閸掓銆冩径杈Е:', e)
    ElMessage.error(e?.response?.data?.message || '閼惧嘲褰囬崶鍓у閸掓銆冩径杈Е')
  } finally {
    selectingImages.value = false
  }
}

async function addImagesToAlbum() {
  if (selectedImages.value.length === 0) {
    ElMessage.warning('鐠囩兘鈧瀚ㄧ憰浣瑰潑閸旂姷娈戦崶鍓у')
    return
  }
  
  const addingImages = [...selectedImages.value]
  selectedImages.value = []
  addImageModalVisible.value = false
  
  try {
    for (const imageId of addingImages) {
      await axios.post(`/api/v1/albums/${albumId.value}/images/${imageId}`)
    }
    ElMessage.success(`閹存劕濮涘ǎ璇插${addingImages.length}瀵姴娴橀悧鍥у煂閻╃鍞絗)
    await fetchAlbumImages()
    await fetchAlbum()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '濞ｈ濮為崶鍓у婢惰精瑙?)
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
  // 绾喕绻氭い鐢告桨濠婃艾濮╅崚浼淬€婇柈?
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

// 閺嶇厧绱￠崠鏍ㄦ）閺堢喎鍤遍弫?
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
        <div class="icon">棣冩懗</div>
        <div class="text">
          <h1>Photory</h1>
          <p>鐠佹澘缍嶆稉鏍？濮ｅ繋绔存禒鐣岀法婵傛枻绱濈拋鈺冪仜闂傛潙褰夐幋鎰閹帪缍?/p>
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
        <button class="icon-btn ghost" @click="toggleNav">menu</button>
        <div class="mobile-brand">
          <span class="logo-mini">logo</span>
          <span>鐩稿唽璇︽儏</span>
        </div>
        <button class="icon-btn ghost" @click="go('/albums')">back</button>
      </header>
      <header class="topbar">
        <div class="left">
          <button class="back-btn ghost" @click="go('/albums')">鐚拑绗?鏉╂柨娲?/button>
          <div class="title-container">
            <div class="title">{{ album?.title }} 璺?閻╃鍞界拠锔藉剰</div>
            <div class="subtitle">閸掓稑缂撴禍?{{ album?.created_at.slice(0, 10) }} 璺?閸?{{ album?.image_count }} 瀵姴娴橀悧?/div>
          </div>
        </div>
        <div class="right">
          <span class="welcome">濞嗐垼绻嬫担鐙呯礉娴滆尙鍩嶉惃?Photory 閻劍鍩?{{ username }}</span>
        </div>
      </header>
      <div class="drawer" :class="{ open: navOpen }">
        <div class="drawer-mask" @click="closeNav"></div>
        <div class="drawer-panel">
          <div class="drawer-head">
            <div class="brand">
              <div class="icon">棣冩懗</div>
              <div class="text">
                <h1>Photory</h1>
                <p>娑撴挸鐫橀惄绋垮斀</p>
              </div>
            </div>
            <button class="icon-btn ghost" @click="closeNav">閴?/button>
          </div>
          <nav>
            <a v-for="item in links" :key="item.path" :class="{ active: isActive(item.path) }" @click="go(item.path)">
              {{ item.icon }} {{ item.label }}
            </a>
          </nav>
        </div>
      </div>
      
      <section class="album-info-section">
        <div v-if="loading" class="loading-box">閸旂姾娴囨稉?..</div>
        <div v-else class="album-info">
          <div
            class="cover"
            :style="{ backgroundImage: album?.cover_image ? `url('${coverThumb(album?.cover_image)}')` : undefined }"
          >
            <span v-if="!album?.cover_image" class="cover-placeholder">棣冩憥</span>
          </div>
          <div class="info">
            <h2>{{ album?.title }}</h2>
            <p class="meta">閸掓稑缂撴禍?{{ album?.created_at.slice(0, 10) }}</p>
            <p class="count">閸?{{ album?.image_count }} 瀵姴娴橀悧?/p>
            <div class="actions">
              <button class="btn primary" @click="openAddImageModal">
                + 濞ｈ濮為崶鍓у閸掓壆娴夐崘?
              </button>
            </div>
          </div>
        </div>
      </section>
      
      <section class="images-section">
        <div class="section-header">
          <h3>閻╃鍞介崶鍓у</h3>
          <div class="actions-bar">
            <div class="view-options">
              <span>濞村繗顫嶅Ο鈥崇础閿?/span>
              <button 
                class="view-btn" 
                :class="{ active: viewMode === 'grid' }" 
                @click="viewMode = 'grid'"
              >
                棣冩惖 缂冩垶鐗?
              </button>
              <button 
                class="view-btn" 
                :class="{ active: viewMode === 'list' }" 
                @click="viewMode = 'list'"
              >
                棣冩憫 閸掓銆?
              </button>
              <button 
                class="view-btn" 
                :class="{ active: viewMode === 'masonry' }" 
                @click="viewMode = 'masonry'"
              >
                棣冨癄 閻庢垵绔峰ù?
              </button>
              <button 
                class="view-btn" 
                :class="{ active: viewMode === 'large' }" 
                @click="viewMode = 'large'"
              >
                棣冩懖 婢堆冨幢閻?
              </button>
            </div>
            <div class="sort-options">
                <span>閹烘帒绨弬鐟扮础閿?/span>
                <select v-model="sortOrder" @change="fetchAlbumImages" class="sort-select">
                  <optgroup label="濞ｈ濮為弮鍫曟？">
                    <option value="added_desc">閺呮艾鍩岄弮?/option>
                    <option value="added_asc">閺冣晛鍩岄弲?/option>
                  </optgroup>
                  <optgroup label="娑撳﹣绱堕弮鍫曟？">
                    <option value="created_desc">閺呮艾鍩岄弮?/option>
                    <option value="oldest">閺冣晛鍩岄弲?/option>
                  </optgroup>
                  <optgroup label="閸ュ墽澧栭崥宥囆?>
                    <option value="name_asc">A-Z</option>
                    <option value="name_desc">Z-A</option>
                  </optgroup>
                  <optgroup label="閹峰秵鎲氶弮鍫曟？">
                    <option value="taken_desc">閺呮艾鍩岄弮?/option>
                    <option value="taken_asc">閺冣晛鍩岄弲?/option>
                  </optgroup>
                </select>
              </div>
            <button 
              class="btn primary" 
              @click="enterCarouselMode" 
              :disabled="images.length === 0"
            >
              棣冨箑 鏉╂稑鍙嗘潪顔芥尡濡€崇础
            </button>
          </div>
        </div>
        
        <div v-if="imageLoading" class="loading-box">閸旂姾娴囬崶鍓у娑?..</div>
        <div v-else-if="!images.length" class="empty-box">
          <div>閻╃鍞芥稉顓＄箷濞屸剝婀侀崶鍓у閿涘苯鎻╅崢缁樺潑閸旂姴鎯傞敍?/div>
        </div>
        <div v-else class="images-container" :class="viewModeClass">
          <div class="image-card" v-for="(image, index) in images" :key="image.id">
            <div class="image-wrapper" @click="openImageViewer(index)">
              <img :src="imageThumbUrl(image.id)" :alt="image.original_name" />
              <div class="image-actions">
                <button class="icon-btn danger" @click.stop="removeImageFromAlbum(image.id)">棣冩閿?/button>
              </div>
            </div>
            <div class="image-info">
              <div class="image-name">{{ image.original_name }}</div>
              <div class="image-meta basic-meta">
                <span class="meta-item">娑撳﹣绱? {{ formatDate(image.created_at) }}</span>
                <div class="tag-list" v-if="image.tag_objects?.length">
                  <span class="tag-chip" v-for="tag in image.tag_objects" :key="tag.id">
                    {{ tag.name }}
                  </span>
                </div>
              </div>
              <div v-if="viewMode === 'list'" class="image-meta">
                <span class="meta-item">鐏忓搫顕? {{ image.width }} 鑴?{{ image.height }}</span>
                <span class="meta-item">婢堆冪毈: {{ image.size }}</span>
                <span class="meta-item">閸掓稑缂撻弮銉︽埂: {{ formatDate(image.created_at) }}</span>
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
            娑撳﹣绔存い?
          </button>
          <span class="page-info">缁?{{ page }} 妞?/ 閸?{{ Math.ceil(total / pageSize) }} 妞?/span>
          <button 
            class="page-btn" 
            :disabled="page >= Math.ceil(total / pageSize)" 
            @click="handlePageChange(page + 1)"
          >
            娑撳绔存い?
          </button>
        </div>
      </section>
      
      <!-- 濞ｈ濮為崶鍓у濡剝鈧焦顢?-->
      <div class="modal-overlay" v-if="addImageModalVisible" @click="addImageModalVisible = false">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3>濞ｈ濮為崶鍓у閸掓壆娴夐崘?/h3>
            <button class="modal-close" @click="addImageModalVisible = false">閴?/button>
          </div>
          <div class="modal-body">
            <div v-if="selectingImages" class="loading-box">閸旂姾娴囬崶鍓у娑?..</div>
            <div v-else-if="!availableImages.length" class="empty-box">
              <div>濞屸剝婀侀幍鎯у煂閸欘垳鏁ら惃鍕禈閻?/div>
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
                <img :src="imageThumbUrl(image.id)" :alt="image.original_name" />
                  <div class="selection-indicator" v-if="isImageSelected(image.id)">閴?/div>
                </div>
              </div>
            </div>
            
            <div class="modal-pagination" v-if="availableTotal > availablePageSize">
              <button 
                class="page-btn" 
                :disabled="availablePage === 1" 
                @click="handleAvailablePageChange(availablePage - 1)"
              >
                娑撳﹣绔存い?
              </button>
              <span class="page-info">缁?{{ availablePage }} 妞?/ 閸?{{ Math.ceil(availableTotal / availablePageSize) }} 妞?/span>
              <button 
                class="page-btn" 
                :disabled="availablePage >= Math.ceil(availableTotal / availablePageSize)" 
                @click="handleAvailablePageChange(availablePage + 1)"
              >
                娑撳绔存い?
              </button>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn cancel" @click="addImageModalVisible = false">閸欐牗绉?/button>
            <button class="btn primary" @click="addImagesToAlbum" :disabled="selectedImages.length === 0">
              濞ｈ濮為柅澶夎厬閸ュ墽澧?({{ selectedImages.length }})
            </button>
          </div>
        </div>
      </div>
      
      <!-- 閸ュ墽澧栨潪顔芥尡缂佸嫪娆?-->
      <div class="carousel-overlay" v-if="carouselVisible" @click="closeImageViewer">
        <div class="carousel-container" @click.stop>
          <button class="carousel-close" @click="closeImageViewer">閴?/button>
          <div class="carousel-content">
            <img 
              :src="imageRawUrl(images[currentImageIndex].id)" 
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
              閳尖偓閿?
            </button>
            <span class="nav-info">{{ currentImageIndex + 1 }} / {{ images.length }}</span>
            <button 
              class="nav-btn" 
              :disabled="currentImageIndex === images.length - 1" 
              @click="currentImageIndex++"
            >
              閳昏绗?
            </button>
          </div>
        </div>
      </div>
      
      <div class="footer-wrapper">
        <footer>2025 Designed by hyk 閻劌绺剧拋鏉跨秿濮ｅ繋绔存禒鐣岀法婵傜刀</footer>
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

/* 鏉╂柨娲栭幐澶愭尦閺嶅嘲绱?*/
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

/* 濞村繗顫嶅Ο鈥崇础閸滃本鎼锋担婊勭埉閺嶅嘲绱?*/
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

/* 閸掓銆冨Ο鈥崇础閺嶅嘲绱?*/
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
.image-meta.basic-meta {
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-chip {
  background: #ffeef5;
  color: #c25585;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(255, 190, 210, 0.7);
}

/* 閻庢垵绔峰ù浣鼓佸蹇旂壉瀵?*/
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

/* 婢堆冨幢閻楀洦膩瀵繑鐗卞?*/
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

/* 濡剝鈧焦顢嬮弽宄扮础 */
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

/* 鏉烆喗鎸辩紒鍕閺嶅嘲绱?*/
.carousel-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 100; display: flex; align-items: center; justify-content: center; }
.carousel-container { position: relative; max-width: 90vw; max-height: 90vh; }
.carousel-close { position: absolute; top: -40px; right: 0; background: none; border: none; color: white; font-size: 24px; cursor: pointer; z-index: 10; }
.carousel-content { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.carousel-image { max-width: 100%; max-height: 80vh; object-fit: contain; }
.carousel-nav { position: absolute; bottom: -40px; left: 0; right: 0; display: flex; justify-content: center; align-items: center; gap: 16px; color: white; }
.nav-btn { background: rgba(255,255,255,0.2); border: none; color: white; font-size: 24px; cursor: pointer; padding: 8px 16px; border-radius: 8px; }
.nav-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.nav-info { font-size: 16px; }

/* 妞や絻鍓肩敮鍐ㄧ湰娣囶喖顦?*/
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
