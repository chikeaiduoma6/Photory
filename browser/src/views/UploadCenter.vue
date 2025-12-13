<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'

type UploadStatus = 'waiting' | 'uploading' | 'paused' | 'stopped' | 'success' | 'error'
interface UploadItem {
  id: number
  name: string
  size: number
  status: UploadStatus
  progress: number
  errorMessage?: string
  raw?: File
  controller?: AbortController
  addedAt: number
  imageId?: number
}
interface TagItem {
  name: string
  color: string
}
interface AlbumOption {
  id: number
  title: string
  visibility: string
}

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '未登录')

const preferencesStore = usePreferencesStore()
const links = computed(() => getNavLinks(preferencesStore.language))

const navOpen = ref(false)
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

const selectedFiles = ref<File[]>([])
const albumOptions = ref<AlbumOption[]>([])
const selectedAlbumId = ref<number | ''>('')
const loadingAlbums = ref(false)
const newAlbumTitle = ref('')
const visibility = ref<'public' | 'private'>('private')
const tagList = ref<TagItem[]>([])
const newTagName = ref('')
const newTagColor = ref('#ff8bb3')
const customName = ref('')
const description = ref('')
const openDetailAfter = ref(false)
const autoAnalyze = ref(true)

const uploadItems = ref<UploadItem[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const displayItems = computed(() => uploadItems.value.filter(i => Date.now() - i.addedAt < 3600 * 1000))

function onSelectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files) return
  selectedFiles.value = [...selectedFiles.value, ...Array.from(files)]
  input.value = ''
}
function onDrop(event: DragEvent) {
  event.preventDefault()
  const files = event.dataTransfer?.files
  if (!files) return
  selectedFiles.value = [...selectedFiles.value, ...Array.from(files)]
}
function onDragOver(event: DragEvent) {
  event.preventDefault()
}
function triggerSelectFiles() {
  fileInputRef.value?.click()
}

function formatSize(size: number) {
  if (!size) return ''
  const mb = size / 1024 / 1024
  if (mb < 1) return `${(size / 1024).toFixed(1)} KB`
  return `${mb.toFixed(2)} MB`
}

function addTagChip() {
  const name = newTagName.value.trim()
  if (!name) {
    ElMessage.warning('请输入标签名称')
    return
  }
  if (tagList.value.some(t => t.name === name)) {
    ElMessage.warning('标签已存在')
    return
  }
  tagList.value.push({ name, color: newTagColor.value || '#ff8bb3' })
  newTagName.value = ''
  newTagColor.value = '#ff8bb3'
}
function removeTag(name: string) {
  tagList.value = tagList.value.filter(t => t.name !== name)
}

async function fetchAlbums() {
  loadingAlbums.value = true
  try {
    const res = await axios.get('/api/v1/albums', { params: { page: 1, page_size: 100 } })
    albumOptions.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '获取相册列表失败')
    albumOptions.value = []
  } finally {
    loadingAlbums.value = false
  }
}

async function createAlbum() {
  const title = newAlbumTitle.value.trim()
  if (!title) {
    ElMessage.warning('请输入相册名称')
    return
  }
  try {
    const res = await axios.post('/api/v1/albums', { title, visibility: 'private' })
    const created = res.data.album
    if (created) {
      albumOptions.value.unshift(created)
      selectedAlbumId.value = created.id
    }
    ElMessage.success('相册创建成功')
    newAlbumTitle.value = ''
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '创建相册失败')
  }
}

async function uploadOne(item: UploadItem) {
  if (!item.raw) {
    item.status = 'error'
    item.errorMessage = '文件缺失'
    return
  }
  const form = new FormData()
  form.append('file', item.raw)
  form.append('folder', '默认图库')
  if (selectedAlbumId.value) {
    form.append('album_id', String(selectedAlbumId.value))
  }
  form.append('visibility', visibility.value)
  form.append('tags', tagList.value.map(t => t.name).join(','))
  form.append('name', customName.value || item.name.split('.').slice(0, -1).join('.') || item.name)
  form.append('description', description.value || '')
  form.append('auto_ai', autoAnalyze.value ? '1' : '0')

  const controller = new AbortController()
  item.controller = controller
  item.status = 'uploading'
  item.progress = 0
  item.errorMessage = ''

  try {
    const res = await axios.post('/api/v1/images/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      signal: controller.signal,
      onUploadProgress: e => {
        const pct = Math.round((e.loaded / (e.total || 1)) * 100)
        item.progress = pct
      },
    })
    const uploaded = res.data.items?.[0]
    item.progress = 100
    item.status = 'success'
    item.imageId = uploaded?.id
    if (openDetailAfter.value && item.imageId) {
      router.push(`/images/${item.imageId}`)
    }
    ElMessage.success('上传成功')
  } catch (err: any) {
    if (controller.signal.aborted && (item.status === 'paused' || item.status === 'stopped')) return
    item.status = 'error'
    item.errorMessage = err?.response?.data?.message || '上传失败'
  }
}

function startUpload() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请选择文件')
    return
  }
  selectedFiles.value.forEach(file => {
    uploadItems.value.push({
      id: Date.now() + Math.random(),
      name: file.name,
      size: file.size,
      status: 'waiting',
      progress: 0,
      raw: file,
      addedAt: Date.now(),
    })
  })
  selectedFiles.value = []
  uploadItems.value.forEach(item => {
    if (['waiting', 'paused', 'error', 'stopped'].includes(item.status)) {
      uploadOne(item)
    }
  })
}

function pauseItem(item: UploadItem) {
  if (item.status !== 'uploading' || !item.controller) return
  item.controller.abort()
  item.status = 'paused'
}
function resumeItem(item: UploadItem) {
  if (item.status !== 'paused') return
  uploadOne(item)
}
function stopItem(item: UploadItem) {
  if (item.controller) item.controller.abort()
  item.status = 'stopped'
  item.progress = 0
}
function removeItem(id: number) {
  uploadItems.value = uploadItems.value.filter(i => i.id !== id)
}

function logout() {
  authStore.logout()
  router.push('/auth/login')
}

onMounted(() => {
  if (authStore.token) fetchAlbums()
})
watch(
  () => authStore.token,
  token => {
    if (token) {
      fetchAlbums()
    } else {
      albumOptions.value = []
      selectedAlbumId.value = ''
    }
  }
)
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
          <span>上传中心</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏡</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">上传中心 · 快来丰富你的专属图库吧！</div>
          <div class="subtitle">支持多种图片格式，移动端可直接拍照或选相册上传</div>
        </div>
        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}</span>
          <button class="icon-btn" title="返回首页" @click="go('/')">🏡</button>
          <button class="icon-btn" title="退出登录" @click="logout">🚪</button>
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
                <p>随时随地上传</p>
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

      <section class="upload-layout">
        <div class="upload-drop-card" @drop="onDrop" @dragover="onDragOver">
          <div class="drop-inner">
            <div class="upload-icon">⬆️</div>
            <h2>拖拽或轻点选择</h2>
            <p>手机可直接拍照或从相册选图，支持 JPG / PNG / GIF / WebP / HEIC</p>
            <button class="select-btn" @click="triggerSelectFiles">点击选择 / 拍照</button>
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept="image/*"
              class="file-input"
              @change="onSelectFiles"
            />
            <div v-if="selectedFiles.length" class="selected-tip">
              已选择 {{ selectedFiles.length }} 个文件，点击“开始上传”进入队列
            </div>
          </div>
        </div>

        <div class="upload-settings-card">
          <h3>上传设置</h3>

          <div class="setting-item">
            <label>自定义名称</label>
            <input v-model="customName" placeholder="如：美丽的樱花（为空则用文件名）" />
          </div>

          <div class="setting-item">
            <label>描述</label>
            <textarea v-model="description" placeholder="可填写图片描述，支持多行"></textarea>
          </div>

          <div class="setting-item">
            <label>目标相册</label>
            <select v-model="selectedAlbumId">
              <option value="">无（不加入相册）</option>
              <option v-for="album in albumOptions" :key="album.id" :value="album.id">
                {{ album.title }}
              </option>
            </select>
            <div class="album-inline-create">
              <input v-model="newAlbumTitle" placeholder="新相册名称" />
              <button class="pill add-album-btn" :disabled="loadingAlbums" @click="createAlbum">+ 新建相册</button>
            </div>
            <div v-if="loadingAlbums" class="muted">相册列表加载中...</div>
          </div>

          <div class="setting-item">
            <label>可见性</label>
            <div class="radio-group">
              <button class="pill" :class="{ active: visibility === 'public' }" @click="visibility = 'public'">公开</button>
              <button class="pill" :class="{ active: visibility === 'private' }" @click="visibility = 'private'">私密</button>
            </div>
          </div>

          <div class="setting-item">
            <label>自定义分类标签</label>
            <div class="tag-create">
              <input v-model="newTagName" placeholder="输入标签名称" />
              <input type="color" v-model="newTagColor" class="color-picker" />
              <button class="pill add-tag-btn" @click="addTagChip">+ 新增标签</button>
            </div>
            <div class="tags-row chips">
              <span
                v-for="t in tagList"
                :key="t.name"
                class="tag-chip"
                :style="{ background: t.color + '33', color: '#b05f7a', borderColor: t.color }"
                @click="removeTag(t.name)"
              >
                <span class="dot" :style="{ background: t.color }"></span>{{ t.name }} ×
              </span>
              <span v-if="!tagList.length" class="muted">点击“新增标签”创建自定义分类</span>
            </div>
          </div>

          <div class="setting-item toggle-row">
            <label>上传后打开图片</label>
            <label class="switch">
              <input type="checkbox" v-model="openDetailAfter" />
              <span class="slider"></span>
            </label>
          </div>

          <div class="setting-item toggle-row">
            <label>自动AI分析（生成标签和描述）</label>
            <label class="switch">
              <input type="checkbox" v-model="autoAnalyze" />
              <span class="slider"></span>
            </label>
          </div>

          <button class="start-upload-btn" @click="startUpload">开始上传</button>
        </div>
      </section>

      <section class="upload-queue-section">
        <h3>上传队列</h3>

        <div v-if="displayItems.length === 0" class="empty-queue">
          暂时还没有待上传的图片～ 先从上面选择或拖拽一些可爱的小照片吧 💗
        </div>

        <ul v-else class="upload-list">
          <li v-for="item in displayItems" :key="item.id" class="upload-item">
            <div class="file-icon">🗂️</div>
            <div class="file-main">
              <div class="file-name-row">
                <span class="file-name">{{ item.name }}</span>
                <span class="file-size">{{ formatSize(item.size) }}</span>
              </div>
              <div class="progress-row">
                <div class="progress-bar">
                  <div
                    class="progress-inner"
                    :class="{ success: item.status === 'success', error: item.status === 'error' }"
                    :style="{ width: item.progress + '%' }"
                  ></div>
                </div>
                <span class="status-pill" :class="item.status">
                  {{
                    item.status === 'waiting'
                      ? '等待上传'
                      : item.status === 'uploading'
                      ? '上传中'
                      : item.status === 'paused'
                      ? '已暂停'
                      : item.status === 'stopped'
                      ? '已停止'
                      : item.status === 'success'
                      ? '完成'
                      : '失败'
                  }}
                </span>
              </div>
              <div v-if="item.status === 'error' && item.errorMessage" class="error-text">
                {{ item.errorMessage }}
              </div>
            </div>
            <div class="queue-actions">
              <button v-if="item.status === 'uploading'" class="small-btn" @click="pauseItem(item)">暂停</button>
              <button v-else-if="item.status === 'paused'" class="small-btn" @click="resumeItem(item)">继续</button>
              <button class="small-btn danger" @click="stopItem(item)">停止</button>
              <button class="remove-btn" @click="removeItem(item.id)">×</button>
            </div>
          </li>
        </ul>
      </section>

      <div class="footer-wrapper">
        <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* 样式保持原有基础，仅新增 textarea 宽度自适应 */
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
main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; padding-bottom: env(safe-area-inset-bottom, 0); }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.9); }
.topbar .title { font-weight: 600; color: #ff4c8a; }
.topbar .subtitle { font-size: 12px; color: #a36e84; }
.topbar .right { display: flex; align-items: center; gap: 10px; }
.welcome { font-size: 13px; color: #8c546e; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn:hover { background: #ffd6e5; }
.icon-btn.ghost { background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(255, 190, 210, 0.7); }
.upload-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; padding: 20px 24px 10px; }
.upload-drop-card { background: #fff7fb; border-radius: 24px; padding: 28px 24px; box-shadow: 0 16px 32px rgba(255, 165, 199, 0.35); display: flex; align-items: center; justify-content: center; border: 2px dashed rgba(255, 153, 187, 0.35); }
.drop-inner { text-align: center; }
.upload-icon { font-size: 42px; margin-bottom: 10px; }
.drop-inner h2 { margin: 8px 0; color: #ff3f87; }
.drop-inner p { font-size: 13px; color: #a25c77; margin-bottom: 16px; }
.select-btn { border: none; border-radius: 999px; padding: 10px 22px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 14px; cursor: pointer; box-shadow: 0 8px 18px rgba(255, 120, 165, 0.45); }
.select-btn:hover { transform: translateY(-1px); }
.file-input { display: none; }
.selected-tip { margin-top: 10px; font-size: 12px; color: #a35d76; }
.upload-settings-card { background: rgba(255, 255, 255, 0.95); border-radius: 24px; padding: 20px 22px; box-shadow: 0 12px 24px rgba(255, 165, 199, 0.3); }
.upload-settings-card h3 { margin: 0 0 10px; color: #ff4c8a; }
.setting-item { margin-bottom: 14px; }
.setting-item label { font-size: 13px; color: #8c546e; display: block; margin-bottom: 6px; }
.setting-item select, .setting-item input, .setting-item textarea { width: 100%; border-radius: 14px; border: 1px solid rgba(255, 190, 210, 0.9); padding: 6px 10px; font-size: 13px; outline: none; background: #fff; box-sizing: border-box; }
.setting-item textarea { min-height: 70px; resize: vertical; }
.setting-item select:focus, .setting-item input:focus, .setting-item textarea:focus { border-color: #ff8bb3; }
.radio-group { display: flex; gap: 8px; }
.pill { border-radius: 999px; border: 1px solid rgba(255, 180, 205, 0.9); background: rgba(255, 255, 255, 0.9); font-size: 12px; padding: 4px 12px; cursor: pointer; }
.pill.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
.tag-create { display: flex; align-items: center; gap: 8px; }
.tag-create .color-picker { width: 46px; height: 36px; padding: 4px; border-radius: 12px; border: 1px solid rgba(255, 190, 210, 0.9); background: #fff; cursor: pointer; }
.add-tag-btn { border: none; color: #b05f7a; }
.album-inline-create { margin-top: 8px; display: flex; gap: 8px; align-items: center; }
.album-inline-create input { flex: 1; padding: 10px 12px; border-radius: 12px; border: 1px solid #ffd1e2; background: #fff; color: #ff4c8a; }
.add-album-btn { white-space: nowrap; }
.tags-row.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; min-height: 28px; }
.tag-chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; border: 1px solid transparent; font-size: 12px; cursor: pointer; }
.tag-chip .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.muted { color: #b57a90; font-size: 12px; }
.toggle-row { display: flex; align-items: center; justify-content: space-between; }
.switch { position: relative; display: inline-block; width: 42px; height: 22px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; inset: 0; background-color: #ffd7e5; transition: 0.2s; border-radius: 999px; }
.slider:before { position: absolute; content: ''; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: 0.2s; border-radius: 50%; }
.switch input:checked + .slider { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); }
.switch input:checked + .slider:before { transform: translateX(18px); }
.start-upload-btn { width: 100%; margin-top: 8px; border-radius: 999px; border: none; padding: 10px 0; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 14px; cursor: pointer; box-shadow: 0 10px 20px rgba(255, 120, 165, 0.45); }
.upload-queue-section { padding: 10px 24px 10px; }
.upload-queue-section h3 { margin-bottom: 10px; color: #ff4c8a; }
.empty-queue { background: rgba(255, 255, 255, 0.85); border-radius: 18px; padding: 18px; font-size: 13px; color: #a35d76; }
.upload-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.upload-item { display: flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.96); border-radius: 16px; padding: 10px 12px; box-shadow: 0 8px 18px rgba(255, 165, 199, 0.27); }
.file-icon { font-size: 20px; }
.file-main { flex: 1; }
.file-name-row { display: flex; justify-content: space-between; font-size: 13px; color: #613448; gap: 8px; }
.file-size { font-size: 11px; color: #b57a90; }
.progress-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.progress-bar { flex: 1; height: 6px; border-radius: 999px; background: #ffe4f0; overflow: hidden; }
.progress-inner { height: 100%; width: 0; border-radius: 999px; background: linear-gradient(135deg, #ffb5cf, #ff7ca8); transition: width 0.15s ease; }
.progress-inner.success { background: linear-gradient(135deg, #8bd67b, #4fb35a); }
.progress-inner.error { background: linear-gradient(135deg, #ff8a8a, #ff5555); }
.status-pill { min-width: 60px; text-align: center; font-size: 11px; border-radius: 999px; padding: 2px 8px; background: #ffeaf3; color: #b05f7a; }
.status-pill.uploading { background: #ffe3f0; }
.status-pill.success { background: #e4f7e2; color: #4b9d54; }
.status-pill.error { background: #ffe1e1; color: #df4b4b; }
.status-pill.paused { background: #fff3d9; color: #c18a34; }
.status-pill.stopped { background: #f3f3f3; color: #9b9b9b; }
.error-text { margin-top: 4px; font-size: 11px; color: #df4b4b; }
.queue-actions { display: flex; align-items: center; gap: 6px; }
.small-btn { border: 1px solid #ffc8da; background: #ffeaf3; border-radius: 10px; padding: 4px 8px; font-size: 11px; cursor: pointer; color: #b05f7a; }
.small-btn.danger { border-color: #ff9ea9; background: #ffe1e5; color: #d05565; }
.remove-btn { border: none; background: transparent; font-size: 16px; cursor: pointer; color: #c27d98; }
.footer-wrapper { margin-top: auto; display: flex; justify-content: center; padding: 12px 0 16px; }
footer { text-align: center; font-size: 12px; color: #b57a90; }
.mobile-topbar { display: none; align-items: center; justify-content: space-between; padding: 10px 16px 0; gap: 12px; }
.mobile-brand { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #d2517f; }
.logo-mini { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; border-radius: 10px; padding: 6px; font-size: 12px; }
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
@media (max-width: 1100px) { .upload-layout { grid-template-columns: 1.5fr 1fr; } }
@media (max-width: 900px) { .sidebar { display: none; } .mobile-topbar { display: flex; } .topbar { padding: 12px 16px; } .upload-layout { grid-template-columns: 1fr; padding-inline: 16px; } .upload-queue-section { padding-inline: 16px; } }
@media (max-width: 640px) { .select-btn, .start-upload-btn { width: 100%; } .drop-inner h2 { font-size: 18px; } .upload-drop-card { padding: 20px 16px; } .upload-settings-card { padding: 16px; } .topbar .right { display: none; } .upload-item { flex-direction: column; align-items: flex-start; } .queue-actions { width: 100%; justify-content: flex-end; } }
</style>
