<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'
import { useLocale } from '@/composables/useLocale'
import heic2any from 'heic2any'

type UploadStatus = 'waiting' | 'uploading' | 'paused' | 'stopped' | 'success' | 'error'
interface UploadItem {
  id: number
  name: string
  size: number
  status: UploadStatus
  progress: number
  errorMessage?: string
  raw?: File
  previewUrl?: string
  controller?: AbortController
  addedAt: number
  imageId?: number
}
interface TagItem {
  name: string
  color: string
}
interface TagOption {
  id: number
  name: string
  color?: string
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
const { text } = useLocale()

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

const albumOptions = ref<AlbumOption[]>([])
const selectedAlbumIds = ref<number[]>([])
const loadingAlbums = ref(false)
const newAlbumTitle = ref('')
const visibility = ref<'public' | 'private'>('private')
const tagList = ref<TagItem[]>([])
const tagOptions = ref<TagOption[]>([])
const selectedTagNames = ref<string[]>([])
const loadingTags = ref(false)
const newTagName = ref('')
const newTagColor = ref('#ff8bb3')
const customName = ref('')
const description = ref('')
const openDetailAfter = ref(true)
const autoAnalyze = ref(true)

const uploadItems = ref<UploadItem[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)
const displayItems = computed(() => uploadItems.value)
const tagNameSet = computed(() => new Set(tagList.value.map(t => t.name)))

type SupportedExt = 'jpg' | 'jpeg' | 'png' | 'gif' | 'webp' | 'bmp' | 'heic' | 'heif'
const supportedExts: SupportedExt[] = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'heic', 'heif']
const supportedExtLabel = 'JPG / JPEG / PNG / GIF / WebP / BMP / HEIC / HEIF'

function isSupportedImage(file: File) {
  const name = (file.name || '').toLowerCase()
  const ext = name.includes('.') ? name.split('.').pop() || '' : ''
  return !!ext && supportedExts.includes(ext as SupportedExt)
}

function getFileExt(file: File) {
  const name = (file.name || '').toLowerCase()
  return name.includes('.') ? name.split('.').pop() || '' : ''
}

function isHeicFile(file: File) {
  const ext = getFileExt(file)
  const mime = (file.type || '').toLowerCase()
  return ext === 'heic' || ext === 'heif' || mime.includes('heic') || mime.includes('heif')
}

async function createPreviewUrl(file: File): Promise<string | undefined> {
  if (typeof URL === 'undefined') return undefined
  if (!isHeicFile(file)) return URL.createObjectURL(file)
  try {
    const converted = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.82 })
    const blob = (Array.isArray(converted) ? converted[0] : converted) as Blob | undefined
    if (!blob) return undefined
    return URL.createObjectURL(blob)
  } catch {
    return undefined
  }
}

async function resolvePreviewUrl(file: File, itemId: number) {
  const previewUrl = await createPreviewUrl(file)
  if (!previewUrl) return
  const target = uploadItems.value.find(i => i.id === itemId)
  if (!target) {
    try { URL.revokeObjectURL(previewUrl) } catch { /* ignore */ }
    return
  }
  if (target.previewUrl && target.previewUrl !== previewUrl) {
    try { URL.revokeObjectURL(target.previewUrl) } catch { /* ignore */ }
  }
  target.previewUrl = previewUrl
}

function enqueueFiles(files: File[]) {
  const good: File[] = []
  let rejected = 0
  for (const f of files) {
    if (isSupportedImage(f) || (f.type || '').startsWith('image/')) good.push(f)
    else rejected += 1
  }
  if (rejected) ElMessage.warning(text(`已跳过 ${rejected} 个非支持格式文件`, `Skipped ${rejected} unsupported file(s)`))
  const now = Date.now()
  for (const file of good) {
    const item: UploadItem = {
      id: now + Math.random(),
      name: file.name,
      size: file.size,
      status: 'waiting',
      progress: 0,
      raw: file,
      previewUrl: undefined,
      addedAt: Date.now(),
    }
    uploadItems.value.push(item)
    void resolvePreviewUrl(file, item.id)
  }
}

const queueStats = computed(() => {
  const items = displayItems.value
  const totalCount = items.length
  const totalBytes = items.reduce((sum, it) => sum + (it.size || 0), 0)
  const pendingItems = items.filter(it => it.status !== 'success')
  const pendingCount = pendingItems.length
  const pendingBytes = pendingItems.reduce((sum, it) => sum + (it.size || 0), 0)
  return { totalCount, totalBytes, pendingCount, pendingBytes }
})

const queueStatsText = computed(() => {
  const { totalCount, totalBytes, pendingCount, pendingBytes } = queueStats.value
  if (!totalCount) return ''
  const zh =
    pendingCount === 0
      ? `本次上传 ${totalCount} 张，合计 ${formatSize(totalBytes)}（已全部上传）`
      : `本次上传 ${totalCount} 张，合计 ${formatSize(totalBytes)}（待上传 ${pendingCount} 张，${formatSize(pendingBytes)}）`
  const en =
    pendingCount === 0
      ? `This upload: ${totalCount} file(s), ${formatSize(totalBytes)} (all done)`
      : `This upload: ${totalCount} file(s), ${formatSize(totalBytes)} (pending ${pendingCount}, ${formatSize(pendingBytes)})`
  return text(zh, en)
})

function onSelectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files) return
  enqueueFiles(Array.from(files))
  input.value = ''
}
function onSelectFolder(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files) return
  enqueueFiles(Array.from(files))
  input.value = ''
}
function onDrop(event: DragEvent) {
  event.preventDefault()
  const files = event.dataTransfer?.files
  if (!files) return
  enqueueFiles(Array.from(files))
}
function onDragOver(event: DragEvent) {
  event.preventDefault()
}
function triggerSelectFiles() {
  fileInputRef.value?.click()
}
function triggerSelectFolder() {
  folderInputRef.value?.click()
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

function addSelectedTags() {
  const next = selectedTagNames.value.filter(name => name && !tagNameSet.value.has(name))
  if (!next.length) return
  for (const name of next) {
    const matched = tagOptions.value.find(t => t.name === name)
    tagList.value.push({ name, color: matched?.color || '#ff8bb3' })
  }
  selectedTagNames.value = []
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

async function fetchTags() {
  loadingTags.value = true
  try {
    const res = await axios.get('/api/v1/tags', { params: { page: 1, page_size: 200 } })
    tagOptions.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '获取标签列表失败')
    tagOptions.value = []
  } finally {
    loadingTags.value = false
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
      if (!selectedAlbumIds.value.includes(created.id)) {
        selectedAlbumIds.value = [...selectedAlbumIds.value, created.id]
      }
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
    maybeAutoNavigateAfterBatch()
    return
  }
  const form = new FormData()
  form.append('file', item.raw)
  form.append('folder', '默认图库')
  if (selectedAlbumIds.value.length) {
    selectedAlbumIds.value.forEach(id => form.append('album_ids', String(id)))
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
    const uploaded = res.data?.items?.[0] ?? res.data?.item ?? res.data?.image ?? res.data
    const uploadedId = uploaded?.id ?? uploaded?.image_id ?? uploaded?.imageId
    item.progress = 100
    item.status = 'success'
    const normalizedId = typeof uploadedId === 'string' ? Number(uploadedId) : uploadedId
    item.imageId = Number.isFinite(normalizedId) ? normalizedId : undefined
    ElMessage.success(text('上传成功', 'Uploaded'))
  } catch (err: any) {
    if (controller.signal.aborted && (item.status === 'paused' || item.status === 'stopped')) return
    item.status = 'error'
    item.errorMessage = err?.response?.data?.message || '上传失败'
  } finally {
    maybeAutoNavigateAfterBatch()
  }
}

const autoOpenBatchIds = ref<number[]>([])
const autoOpenDone = ref(false)
function isTerminalStatus(status: UploadStatus) {
  return status === 'success' || status === 'error' || status === 'stopped'
}
function maybeAutoNavigateAfterBatch() {
  if (!openDetailAfter.value) return
  if (autoOpenDone.value) return
  if (!autoOpenBatchIds.value.length) return
  const idSet = new Set(autoOpenBatchIds.value)
  const batchItems = uploadItems.value.filter(i => idSet.has(i.id))
  if (!batchItems.length) return
  if (!batchItems.every(i => isTerminalStatus(i.status))) return
  const lastSuccess = [...autoOpenBatchIds.value].reverse().map(id => uploadItems.value.find(i => i.id === id)).find(i => i?.status === 'success' && i.imageId)
  if (lastSuccess?.imageId) {
    autoOpenDone.value = true
    autoOpenBatchIds.value = []
    router.push(`/images/${lastSuccess.imageId}`).catch(() => {})
  } else {
    autoOpenDone.value = true
    autoOpenBatchIds.value = []
  }
}

const batchStatusKey = computed(() => {
  if (!autoOpenBatchIds.value.length) return ''
  return autoOpenBatchIds.value
    .map(id => {
      const item = uploadItems.value.find(i => i.id === id)
      return item ? `${id}:${item.status}:${item.imageId ?? ''}` : `${id}:missing`
    })
    .join('|')
})
watch(batchStatusKey, () => maybeAutoNavigateAfterBatch())

function startUpload() {
  const startable = uploadItems.value.filter(item => ['waiting', 'paused', 'error', 'stopped'].includes(item.status))
  if (!startable.length) {
    ElMessage.warning(text('上传队列为空', 'Upload queue is empty'))
    return
  }
  autoOpenDone.value = false
  autoOpenBatchIds.value = startable.map(i => i.id)
  startable.forEach(item => uploadOne(item))
}

function pauseItem(item: UploadItem) {
  if (item.status !== 'uploading' || !item.controller) return
  item.controller.abort()
  item.status = 'paused'
}
function resumeItem(item: UploadItem) {
  if (item.status !== 'paused') return
  item.progress = 0
  uploadOne(item)
}
function stopItem(item: UploadItem) {
  if (item.controller) item.controller.abort()
  item.status = 'stopped'
  item.progress = 0
}
function removeItem(id: number) {
  const found = uploadItems.value.find(i => i.id === id)
  if (found?.controller) found.controller.abort()
  if (found?.previewUrl) {
    try { URL.revokeObjectURL(found.previewUrl) } catch { /* ignore */ }
  }
  uploadItems.value = uploadItems.value.filter(i => i.id !== id)
}

onUnmounted(() => {
  for (const item of uploadItems.value) {
    if (item.previewUrl) {
      try { URL.revokeObjectURL(item.previewUrl) } catch { /* ignore */ }
    }
  }
})

function logout() {
  authStore.logout()
  router.push('/auth/login')
}

onMounted(() => {
  if (authStore.token) {
    fetchAlbums()
    fetchTags()
  }
})
watch(
  () => authStore.token,
  token => {
    if (token) {
      fetchAlbums()
      fetchTags()
    } else {
      albumOptions.value = []
      selectedAlbumIds.value = []
      tagOptions.value = []
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
          <span>{{ text('上传中心', 'Upload') }}</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏡</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">{{ text('上传中心 · 快来丰富你的专属图库吧！', 'Upload · Grow your personal gallery!') }}</div>
          <div class="subtitle">
            {{
              text(
                '支持丰富的图片格式，网页端支持拖拽或打开本地文件夹选择，移动端可直接拍照或打开相册选择',
                'Supports many formats. On web you can drag & drop or pick a local folder; on mobile you can capture or choose from albums.'
              )
            }}
          </div>
        </div>
        <div class="right">
          <span class="welcome">{{ text('欢迎你，亲爱的 Photory 用户', 'Welcome, dear Photory user') }} {{ username }}</span>
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
                <p>{{ text('随时随地上传', 'Upload anytime') }}</p>
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
            <p>{{ text(`手机端可拍照或选相册，支持 ${supportedExtLabel}`, `Mobile capture/album supported: ${supportedExtLabel}`) }}</p>
            <div v-if="queueStats.totalCount" class="queue-stats">
              {{ queueStatsText }}
            </div>
            <div class="select-row">
              <button class="select-btn" @click="triggerSelectFiles">{{ text('点击选择 / 拍照', 'Choose files / Capture') }}</button>
              <button class="select-btn ghost" @click="triggerSelectFolder">{{ text('选择文件夹', 'Choose folder') }}</button>
            </div>
            <input
              ref="fileInputRef"
              type="file"
              multiple
              :accept="`image/*,.jpg,.jpeg,.png,.gif,.webp,.bmp,.heic,.heif`"
              class="file-input"
              @change="onSelectFiles"
            />
            <input
              ref="folderInputRef"
              type="file"
              multiple
              webkitdirectory
              directory
              class="file-input"
              @change="onSelectFolder"
            />
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
            <el-select
              v-model="selectedAlbumIds"
              class="album-select"
              multiple
              filterable
              clearable
              :loading="loadingAlbums"
              placeholder="选择相册（可多选）"
            >
              <el-option v-for="album in albumOptions" :key="album.id" :label="album.title" :value="album.id" />
            </el-select>
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
            <div class="tag-select-row">
              <el-select
                v-model="selectedTagNames"
                class="tag-select"
                multiple
                filterable
                clearable
                :loading="loadingTags"
                placeholder="选择已有标签"
              >
                <el-option
                  v-for="tag in tagOptions"
                  :key="tag.id"
                  :label="tag.name"
                  :value="tag.name"
                  :disabled="tagNameSet.has(tag.name)"
                >
                  <span class="tag-option">
                    <span class="dot" :style="{ background: tag.color || '#ff8bb3' }"></span>
                    {{ tag.name }}
                  </span>
                </el-option>
              </el-select>
              <button class="pill add-tag-btn" :disabled="!selectedTagNames.length" @click="addSelectedTags">
                + 新增已选
              </button>
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
              <span v-if="!tagList.length" class="muted">点击“新增标签”创建自定义分类管理标签</span>
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
            <img v-if="item.previewUrl" class="file-thumb" :src="item.previewUrl" :alt="item.name" />
            <div v-else class="file-icon">🗂️</div>
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
              <button v-if="item.status === 'uploading' || item.status === 'paused'" class="small-btn danger" @click="stopItem(item)">取消</button>
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
.queue-stats { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 6px 12px; border-radius: 999px; margin: 0 auto 10px; font-size: 12px; color: #8c546e; background: rgba(255, 255, 255, 0.75); border: 1px solid rgba(255, 190, 210, 0.7); box-shadow: 0 8px 18px rgba(255, 165, 199, 0.18); }
.select-row { display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.select-btn { border: none; border-radius: 999px; padding: 10px 22px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 14px; cursor: pointer; box-shadow: 0 8px 18px rgba(255, 120, 165, 0.45); }
.select-btn.ghost { background: #ffeef5; color: #b05f7a; box-shadow: none; border: 1px solid rgba(255, 180, 205, 0.7); }
.select-btn:hover { transform: translateY(-1px); }
.file-input { display: none; }
.upload-settings-card { background: rgba(255, 255, 255, 0.95); border-radius: 24px; padding: 20px 22px; box-shadow: 0 12px 24px rgba(255, 165, 199, 0.3); }
.upload-settings-card h3 { margin: 0 0 10px; color: #ff4c8a; }
.setting-item { margin-bottom: 14px; }
.setting-item label { font-size: 13px; color: #8c546e; display: block; margin-bottom: 6px; }
.setting-item select, .setting-item input, .setting-item textarea { width: 100%; border-radius: 14px; border: 1px solid rgba(255, 190, 210, 0.9); padding: 6px 10px; font-size: 13px; outline: none; background: #fff; box-sizing: border-box; }
.setting-item textarea { min-height: 70px; resize: vertical; }
.setting-item select:focus, .setting-item input:focus, .setting-item textarea:focus { border-color: #ff8bb3; }
.album-select, .tag-select { width: 100%; }
:deep(.album-select .el-select__wrapper),
:deep(.tag-select .el-select__wrapper) {
  border-radius: 14px;
  border: 1px solid rgba(255, 190, 210, 0.9);
  background: #fff;
  box-shadow: none;
}
:deep(.album-select .el-select__placeholder),
:deep(.tag-select .el-select__placeholder) {
  color: #b57a90;
}
.radio-group { display: flex; gap: 8px; }
.pill { border-radius: 999px; border: 1px solid rgba(255, 180, 205, 0.9); background: rgba(255, 255, 255, 0.9); font-size: 12px; padding: 4px 12px; cursor: pointer; }
.pill.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
.tag-create { display: flex; align-items: center; gap: 8px; }
.tag-create .color-picker { width: 46px; height: 36px; padding: 4px; border-radius: 12px; border: 1px solid rgba(255, 190, 210, 0.9); background: #fff; cursor: pointer; }
.add-tag-btn { border: none; color: #b05f7a; }
.tag-select-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center; margin-top: 8px; }
.tag-option { display: inline-flex; align-items: center; gap: 6px; }
.tag-option .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
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
.file-thumb { width: 44px; height: 44px; border-radius: 12px; object-fit: cover; background: #f9edf3; border: 1px solid rgba(255, 190, 210, 0.55); }
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
@media (max-width: 640px) {
  .select-btn, .start-upload-btn { width: 100%; }
  .drop-inner h2 { font-size: 18px; }
  .upload-drop-card { padding: 20px 16px; }
  .upload-settings-card { padding: 16px; }
  .topbar .right { display: none; }
  .upload-item { flex-direction: column; align-items: flex-start; }
  .queue-actions { width: 100%; justify-content: flex-end; }
  .tag-select-row { grid-template-columns: 1fr; }
}
</style>
