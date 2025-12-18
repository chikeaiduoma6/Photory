<template>
  <div class="dashboard albums-page">
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
          <span>{{ text('相册', 'Albums') }}</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏡</button>
      </header>
      <header class="topbar">
        <div class="left">
          <div class="title">{{ text('相册 · 珍藏美好回忆', 'Albums · Keep your memories') }}</div>
          <div class="subtitle">{{ text('可按不同主题创建你的专属相册~', 'Create albums by themes you love.') }}</div>
        </div>
        <div class="right">
          <span class="welcome">{{ text('欢迎你，亲爱的 Photory 用户', 'Welcome, dear Photory user') }} {{ username }}</span>
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
                <p>{{ text('专属相册', 'Your albums') }}</p>
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
      
      <section class="albums-section">
        <div v-if="loading" class="empty-box">{{ text('加载中...', 'Loading...') }}</div>
        <div v-else class="albums-list">
          <!-- 新建相册按钮（相册卡片样式） -->
          <div class="album-card create-album-card" @click="showCreateDialog = true">
            <div class="cover create-cover">
              <span class="create-plus">➕</span>
            </div>
            <div class="album-info">
              <div class="name">{{ text('新建相册', 'New album') }}</div>
              <div class="desc">{{ text('创建你的专属相册', 'Create your own album') }}</div>
              <div class="meta-row">
                <span>{{ text('点击创建', 'Click to create') }}</span>
              </div>
            </div>
          </div>
          
          <!-- 现有相册列表 -->
          <div class="album-card" v-for="album in albums" :key="album.id">
            <div class="cover" :style="{ backgroundImage: album.cover_image ? `url('${coverThumb(album)}')` : undefined }" @click="openAlbum(album.id)">
              <span v-if="!album.cover_image" class="cover-placeholder">📚</span>
            </div>
            <div class="album-info" @click="openAlbum(album.id)">
              <div class="name">{{ album.title }}</div>
              <div v-if="album.description" class="desc">{{ album.description }}</div>
              <div class="meta-row">
                <span>共 {{ album.image_count }} 张</span>
                <span>{{ album.created_at.slice(0,10) }}</span>
              </div>
            </div>
            <button class="delete-btn" @click.stop="deleteAlbum(album.id)">
              🗑️
            </button>
          </div>
        </div>
        
        <!-- 空状态提示 -->
        <div v-if="!loading && !albums.length" class="empty-box">
          <div>还没有创建任何相册，点击上方卡片新建一个吧！</div>
        </div>
      </section>
      
      <!-- 创建相册对话框 -->
      <div class="dialog-overlay" v-if="showCreateDialog" @click="showCreateDialog = false">
        <div class="dialog-content" @click.stop>
          <h3>创建新相册</h3>
          <div class="dialog-body">
            <label for="album-title">相册标题</label>
            <input 
              id="album-title" 
              type="text" 
              v-model="newAlbumTitle" 
              placeholder="请输入相册标题"
              class="album-input"
              @keyup.enter="createAlbum"
            />
          </div>
          <div class="dialog-footer">
            <button class="dialog-btn cancel" @click="showCreateDialog = false">取消</button>
            <button class="dialog-btn confirm" @click="createAlbum" :disabled="!newAlbumTitle.trim()">创建</button>
          </div>
        </div>
      </div>
      
      <div class="footer-wrapper">
        <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'
import { useLocale } from '@/composables/useLocale'

interface Image {
  id: number
  name: string
  filename: string
  original_name: string
  thumb_path?: string
  thumb_url?: string
}

interface Album {
  id: number
  title: string
  user_id: number
  description?: string
  visibility: string
  created_at: string
  updated_at: string
  image_count: number
  cover_image?: Image
}

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (path: string) => (!path ? '' : path.startsWith('http') ? path : `${apiBase}${path}`)
const tokenParam = computed(() => (authStore.token ? `?jwt=${authStore.token}` : ''))

const albums = ref<Album[]>([])
const loading = ref(false)
const navOpen = ref(false)
const currentPath = computed(() => router.currentRoute.value.path)
const go = (path: string) => { router.push(path); navOpen.value = false }
const isActive = (path: string) => currentPath.value === path || currentPath.value.startsWith(path + '/')
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)

// 创建相册相关
const showCreateDialog = ref(false)
const newAlbumTitle = ref('')

const coverThumb = (album: Album) => {
  const img = album.cover_image
  if (!img) return ''
  const url = img.thumb_url || (img.thumb_path ? `/api/v1/images/${img.id}/thumb` : '')
  return url ? withBase(url) + tokenParam.value : ''
}

const preferencesStore = usePreferencesStore()
const links = computed(() => getNavLinks(preferencesStore.language))
const { text } = useLocale()

async function fetchAlbums() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/albums')
    albums.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '获取相册失败')
  } finally {
    loading.value = false
  }
}

async function createAlbum() {
  if (!newAlbumTitle.value.trim()) {
    ElMessage.warning('相册标题不能为空')
    return
  }
  
  try {
    await axios.post('/api/v1/albums', {
      title: newAlbumTitle.value.trim(),
      visibility: 'private'
    })
    ElMessage.success('相册创建成功')
    showCreateDialog.value = false
    newAlbumTitle.value = ''
    await fetchAlbums()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '创建相册失败')
  }
}

async function deleteAlbum(id: number) {
  try {
    await ElMessageBox.confirm('确定要删除这个相册吗？删除后无法恢复。', '删除相册', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await axios.delete(`/api/v1/albums/${id}`)
    ElMessage.success('相册删除成功')
    await fetchAlbums()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.message || '删除相册失败')
    }
  }
}

function openAlbum(id: number) {
  router.push(`/albums/${id}`)
}

onMounted(fetchAlbums)
watch(() => authStore.token, fetchAlbums)
</script>

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
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px;}
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; }
.welcome { font-size: 13px; color: #8c546e; }
.mobile-topbar { display: none; align-items: center; justify-content: space-between; padding: 10px 16px 0; gap: 12px; }
.mobile-brand { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #d2517f; }
.logo-mini { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; border-radius: 10px; padding: 6px; font-size: 12px; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer;}
.icon-btn.ghost { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); }
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

.albums-section { margin: 0 16px 14px; }
.albums-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 22px; }
.album-card { display: flex; flex-direction: column; background: rgba(255,255,255,0.95); border-radius: 18px; box-shadow: 0 10px 24px rgba(255,153,187,0.19); cursor: pointer; transition: transform 0.13s, box-shadow 0.13s; position: relative; }
.album-card:hover { transform: translateY(-3px); box-shadow: 0 18px 38px rgba(255,153,187,0.29);}
.cover { min-height: 160px; background: #ffe3f0; border-top-left-radius: 18px; border-top-right-radius: 18px; background-size: cover; background-position: center; display: flex; align-items: center; justify-content: center; }
.cover-placeholder { font-size: 54px; color: #ec7aa7; opacity: 0.32; }
.album-info { padding: 14px 18px 12px 18px; }

/* 删除按钮 */
.delete-btn { position: absolute; top: 8px; right: 8px; background: rgba(255, 255, 255, 0.8); border: none; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 14px; opacity: 0; transition: opacity 0.2s; }
.album-card:hover .delete-btn { opacity: 1; }
.delete-btn:hover { background: rgba(255, 100, 140, 0.8); color: white; }

/* 创建相册对话框 */
.dialog-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.dialog-content { background: white; border-radius: 18px; padding: 24px; width: 90%; max-width: 400px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15); }
.dialog-content h3 { margin: 0 0 20px 0; color: #ff4c8a; font-size: 18px; }
.dialog-body { margin-bottom: 24px; }
.dialog-body label { display: block; margin-bottom: 8px; color: #8c546e; font-size: 14px; font-weight: 600; }
.album-input { width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 190, 210, 0.7); border-radius: 8px; font-size: 14px; color: #4b2b3a; box-sizing: border-box; }
.album-input:focus { outline: none; border-color: #ff6fa0; box-shadow: 0 0 0 2px rgba(255, 153, 187, 0.2); }
.dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }
.dialog-btn { padding: 8px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; }
.dialog-btn.cancel { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); color: #8c546e; }
.dialog-btn.confirm { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: white; }
.dialog-btn.confirm:disabled { opacity: 0.5; cursor: not-allowed; }
.dialog-btn:hover:not(:disabled) { opacity: 0.9; }

.album-info .name { font-size: 16px; font-weight: 600; color: #e45090; margin-bottom: 4px; }
.album-info .desc { font-size: 12px; color: #a25c77; margin-bottom: 8px; }
.meta-row { font-size: 12px; color: #b6788d; display: flex; justify-content: space-between; align-items: center; }
.empty-box { padding: 100px 0; text-align: center; color: #b6788d; background: rgba(255, 255, 255, 0.88); border-radius: 14px; }
.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding: 8px 0 16px; }
footer { text-align: center; font-size: 12px; color: #b57a90;}

/* 新建相册卡片样式 */
.create-album-card { cursor: pointer; border: 2px dashed rgba(255, 153, 187, 0.5); background: rgba(255, 255, 255, 0.9); transition: all 0.3s ease; }
.create-album-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 18px 38px rgba(255, 153, 187, 0.29);
  border-color: rgba(255, 106, 160, 0.8);
  background: rgba(255, 255, 255, 0.95);
}
.create-cover {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(255, 238, 245, 0.8), rgba(255, 229, 240, 0.8));
}
.create-plus {
  font-size: 64px;
  color: #ff6fa0;
  opacity: 0.8;
  transition: transform 0.3s ease;
}
.create-album-card:hover .create-plus {
  transform: scale(1.1);
  opacity: 1;
}
.create-album-card .album-info .name {
  color: #ff6fa0;
  font-weight: 700;
}
.create-album-card .album-info .desc {
  color: #a36e84;
}
.create-album-card .album-info .meta-row {
  justify-content: center;
  color: #b6788d;
  font-style: italic;
}

@media (max-width: 1100px) { .albums-section { margin-inline: 7px; } }
@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .albums-section { margin-inline: 4px;}
}
@media (max-width: 640px) {
  .albums-section { margin-top: 10px; }
  .topbar .right { display: none; }
}
</style>
