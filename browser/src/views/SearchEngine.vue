<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

interface GalleryImage {
  id: number
  displayName: string
  created_at?: string
  uploaded_at?: string
  width?: number
  height?: number
  size?: number
  tags?: string[]
  thumbUrl: string
  fullUrl: string
}
interface TagOption { id: number; name: string; color?: string }

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

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
const go = (path: string) => router.push(path)
const isActive = (path: string) => currentPath.value === path || currentPath.value.startsWith(path + '/')

const keyword = ref('')
const selectedTags = ref<string[]>([])
const tagOptions = ref<TagOption[]>([])
const tagLoading = ref(false)

const dateType = ref<'captured' | 'uploaded'>('captured')
const dateRange = ref<[string, string] | []>([])
const quickPreset = ref('')

const formats = ref<string[]>([])
const formatOptions = [
  { label: 'JPG / JPEG', value: 'jpg' },
  { label: 'PNG', value: 'png' },
  { label: 'WebP', value: 'webp' },
  { label: 'GIF', value: 'gif' },
  { label: 'HEIC / HEIF', value: 'heic' },
  { label: 'BMP', value: 'bmp' },
  { label: 'RAW / DNG', value: 'raw' },
]
const sizeRange = ref<[number, number]>([0, 200]) // MB
const exif = ref({
  camera: '',
  lens: '',
  iso: '',
  aperture: '',
  focal_length: '',
  shutter: '',
})

const viewMode = ref<'grid' | 'masonry' | 'large'>('grid')
const sortBy = ref('captured_desc')
const sortOptions = [
  { value: 'captured_desc', label: '拍摄时间 · 新→旧' },
  { value: 'captured_asc', label: '拍摄时间 · 旧→新' },
  { value: 'uploaded_desc', label: '上传时间 · 新→旧' },
  { value: 'uploaded_asc', label: '上传时间 · 旧→新' },
  { value: 'size_desc', label: '文件大小 · 大→小' },
  { value: 'size_asc', label: '文件大小 · 小→大' },
  { value: 'res_desc', label: '分辨率 · 高→低' },
  { value: 'res_asc', label: '分辨率 · 低→高' },
  { value: 'tag_desc', label: '标签数量 · 多→少' },
  { value: 'name_asc', label: '图片名称 · A-Z' },
]

const currentPage = ref(1)
const pageSize = ref(12)
const total = ref(0)
const loading = ref(false)
const images = ref<GalleryImage[]>([])

const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (path: string) => (!path ? '' : path.startsWith('http') ? path : `${apiBase}${path}`)
const fallbackTagColor = '#ff9db8'
const hasResult = computed(() => images.value.length > 0)

function formatSize(size?: number) {
  if (!size && size !== 0) return ''
  const mb = size / 1024 / 1024
  if (mb < 1) return `${(size / 1024).toFixed(1)} KB`
  return `${mb.toFixed(2)} MB`
}
function formatDate(dateStr?: string) {
  if (!dateStr) return ''
  return dateStr.slice(0, 10)
}
function fallbackToRaw(event: Event, url: string) {
  const img = event.target as HTMLImageElement | null
  if (img && url && img.src !== url) img.src = url
}

async function fetchTags(query = '') {
  tagLoading.value = true
  try {
    const res = await axios.get('/api/v1/tags', { params: { keyword: query, page: 1, page_size: 12 } })
    tagOptions.value = res.data.items || []
  } catch {
    /* ignore */
  } finally {
    tagLoading.value = false
  }
}
function remoteTagMethod(query: string) {
  fetchTags(query)
}

function applyQuickRange(preset: 'today' | '3d' | '7d' | '30d' | '') {
  quickPreset.value = preset
  if (!preset) {
    dateRange.value = []
    return
  }
  const end = new Date()
  end.setHours(23, 59, 59, 999)
  const start = new Date(end)
  if (preset === 'today') start.setHours(0, 0, 0, 0)
  else if (preset === '3d') start.setDate(start.getDate() - 2)
  else if (preset === '7d') start.setDate(start.getDate() - 6)
  else if (preset === '30d') start.setDate(start.getDate() - 29)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  dateRange.value = [fmt(start), fmt(end)]
}

function buildParams() {
  const params: Record<string, any> = {
    page: currentPage.value,
    page_size: pageSize.value,
    sort: sortBy.value,
  }
  const kw = keyword.value.trim()
  if (kw) params.keyword = kw
  if (selectedTags.value.length) params.tags = selectedTags.value.join(',')
  if (formats.value.length) params.formats = formats.value.join(',')
  if (dateRange.value.length === 2) {
    params[`${dateType.value}_start`] = dateRange.value[0]
    params[`${dateType.value}_end`] = dateRange.value[1]
  }
  if (sizeRange.value[0] > 0) params.size_min_mb = sizeRange.value[0]
  if (sizeRange.value[1] < 200) params.size_max_mb = sizeRange.value[1]
  Object.entries(exif.value).forEach(([k, v]) => {
    const val = (v as string).trim()
    if (val) params[k] = val
  })
  return params
}

async function fetchResults() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/images/search', { params: buildParams() })
    const tokenParam = authStore.token ? `?jwt=${authStore.token}` : ''
    images.value = (res.data.items || []).map((item: any) => ({
      ...item,
      thumbUrl: withBase((item.thumb_url || `/api/v1/images/${item.id}/thumb`) + tokenParam),
      fullUrl: withBase((item.raw_url || `/api/v1/images/${item.id}/raw`) + tokenParam),
      displayName: item.name || item.original_name,
      tags: item.tags || item.tag_objects?.map((t: any) => t.name) || [],
    }))
    total.value = res.data.total ?? images.value.length
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '搜索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchResults()
}
function resetFilters() {
  keyword.value = ''
  selectedTags.value = []
  formats.value = []
  sizeRange.value = [0, 200]
  exif.value = { camera: '', lens: '', iso: '', aperture: '', focal_length: '', shutter: '' }
  dateType.value = 'captured'
  dateRange.value = []
  quickPreset.value = ''
  sortBy.value = 'captured_desc'
  viewMode.value = 'grid'
  currentPage.value = 1
  fetchResults()
}
function handlePageChange(p: number) {
  currentPage.value = p
  fetchResults()
}
const changeView = (mode: 'grid' | 'masonry' | 'large') => { viewMode.value = mode }
function changeSort(val: string) {
  sortBy.value = val
  currentPage.value = 1
  fetchResults()
}
const goDetail = (id: number) => router.push(`/images/${id}`)

onMounted(() => {
  fetchTags()
  fetchResults()
})
</script>

<template>
  <div class="dashboard search-page">
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
          <div class="title">搜索引擎 · 全局检索</div>
          <div class="subtitle">名称/标签/EXIF/时间/文件属性等多维度组合筛选，快速命中想要的图片</div>
        </div>
        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}</span>
        </div>
      </header>

      <section class="search-card">
        <div class="main-search">
          <input
            v-model="keyword"
            placeholder="输入图片名称、文件名或关键词（回车搜索）"
            @keyup.enter="handleSearch"
          />
          <el-select
            v-model="selectedTags"
            class="tag-select"
            multiple
            filterable
            remote
            clearable
            :remote-method="remoteTagMethod"
            :loading="tagLoading"
            placeholder="按标签精准筛选（自动补全，可多选）"
          >
            <el-option v-for="tag in tagOptions" :key="tag.id" :label="tag.name" :value="tag.name">
              <span class="tag-option">
                <span class="dot" :style="{ background: tag.color || fallbackTagColor }"></span>
                {{ tag.name }}
              </span>
            </el-option>
          </el-select>
          <button class="primary-btn" @click="handleSearch">搜索</button>
          <button class="ghost-btn" @click="resetFilters">清空条件</button>
        </div>

        <div class="meta-bar">
          <div class="stat-chip">符合条件的图片共 <b>{{ total }}</b> 张</div>
          <div class="controls">
            <div class="view-switch">
              <button class="view-pill" :class="{ active: viewMode === 'grid' }" @click="changeView('grid')">🟦 网格</button>
              <button class="view-pill" :class="{ active: viewMode === 'masonry' }" @click="changeView('masonry')">🧱 瀑布流</button>
              <button class="view-pill" :class="{ active: viewMode === 'large' }" @click="changeView('large')">🃏 大卡片</button>
            </div>
            <el-select class="sort-select" v-model="sortBy" size="small" @change="changeSort">
              <el-option v-for="item in sortOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </div>
        </div>

        <div class="advanced-panel">
          <div class="panel-head">
            <span>高级筛选</span>
            <span class="hint">组合时间/格式/EXIF/文件大小等条件，获得更精准的结果</span>
          </div>

          <div class="time-row">
            <div class="time-left">
              <div class="label">时间维度</div>
              <div class="pill-group">
                <button :class="{ active: dateType === 'captured' }" @click="dateType = 'captured'">拍摄时间</button>
                <button :class="{ active: dateType === 'uploaded' }" @click="dateType = 'uploaded'">上传时间</button>
              </div>
            </div>
            <div class="time-picker">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                unlink-panels
                range-separator="到"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
              />
            </div>
            <div class="quick-pills">
              <button :class="{ active: quickPreset === 'today' }" @click="applyQuickRange('today')">今天</button>
              <button :class="{ active: quickPreset === '3d' }" @click="applyQuickRange('3d')">最近三天</button>
              <button :class="{ active: quickPreset === '7d' }" @click="applyQuickRange('7d')">最近一周</button>
              <button :class="{ active: quickPreset === '30d' }" @click="applyQuickRange('30d')">最近一月</button>
              <button class="ghost" @click="applyQuickRange('')">清空</button>
            </div>
          </div>

          <div class="filter-grid">
            <div class="filter-card">
              <div class="label">图片格式</div>
              <el-select v-model="formats" multiple clearable filterable placeholder="选择需要的文件格式">
                <el-option v-for="fmt in formatOptions" :key="fmt.value" :label="fmt.label" :value="fmt.value" />
              </el-select>
            </div>

            <div class="filter-card exif-card">
              <div class="label">EXIF 维度</div>
              <div class="exif-grid">
                <input v-model="exif.camera" placeholder="相机型号" />
                <input v-model="exif.lens" placeholder="镜头型号" />
                <input v-model="exif.iso" placeholder="ISO (如 100)" />
                <input v-model="exif.aperture" placeholder="光圈 (如 f/1.8)" />
                <input v-model="exif.focal_length" placeholder="焦距 (如 35mm)" />
                <input v-model="exif.shutter" placeholder="快门 (如 1/125s)" />
              </div>
            </div>

            <div class="filter-card size-card">
              <div class="label">文件大小 (MB)</div>
              <el-slider
                v-model="sizeRange"
                range
                :min="0"
                :max="200"
                :marks="{ 0: '0', 50: '50', 100: '100', 150: '150', 200: '200+' }"
              />
              <div class="hint">当前：{{ sizeRange[0] }} MB - {{ sizeRange[1] }} MB</div>
            </div>
          </div>
        </div>
      </section>

      <section class="results">
        <div class="gallery" :class="viewMode">
          <div v-if="loading" class="empty-box">搜索中，请稍候...</div>
          <div v-else-if="!hasResult" class="empty-box">
            还没有符合条件的图片，试试调整搜索词或筛选条件吧～
          </div>
          <div
            v-else
            v-for="img in images"
            :key="img.id"
            class="photo"
            @click="goDetail(img.id)"
          >
            <img :src="img.thumbUrl" :alt="img.displayName" loading="lazy" @error="fallbackToRaw($event, img.fullUrl)" />
            <div class="caption">
              <div class="title">{{ img.displayName }}</div>
              <div class="date">{{ formatDate(img.created_at || img.uploaded_at) }}</div>
            </div>
            <div class="meta-row">
              <span>{{ img.width && img.height ? `${img.width}×${img.height}` : '分辨率未知' }}</span>
              <span>{{ formatSize(img.size) || '大小未知' }}</span>
            </div>
            <div class="tag-line" v-if="img.tags?.length">
              <span v-for="tag in img.tags" :key="tag" class="tag-chip">{{ tag }}</span>
            </div>
          </div>
        </div>

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
      </section>
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
nav a { display: block; padding: 8px 12px; border-radius: 12px; font-size: 13px; color: #6b3c4a; margin: 2px 0; cursor: pointer; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }

main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.92); }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; }
.welcome { font-size: 13px; color: #8c546e; }

.search-card { margin: 14px 18px 10px; background: rgba(255, 255, 255, 0.96); border-radius: 18px; padding: 14px 16px; box-shadow: 0 12px 24px rgba(255, 165, 199, 0.32); }
.main-search { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.main-search input { flex: 1; min-width: 240px; border-radius: 14px; border: 1px solid rgba(255, 190, 210, 0.9); padding: 10px 12px; font-size: 13px; outline: none; }
.main-search input:focus { border-color: #ff8bb3; }
.tag-select { min-width: 240px; flex: 0 0 280px; }
.tag-option { display: inline-flex; align-items: center; gap: 6px; }
.tag-option .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

.primary-btn, .ghost-btn { border: none; border-radius: 999px; padding: 9px 16px; cursor: pointer; font-size: 13px; }
.primary-btn { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 6px 14px rgba(255, 120, 165, 0.4); }
.ghost-btn { background: #ffeef5; color: #b05f7a; border: 1px solid rgba(255, 180, 205, 0.7); }

.meta-bar { margin-top: 10px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.stat-chip { background: #fff2f7; border: 1px dashed #ffc8da; color: #a35d76; padding: 8px 12px; border-radius: 12px; font-size: 13px; }
.controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.view-switch { display: flex; align-items: center; gap: 8px; }
.view-pill { border-radius: 16px; border: 1px solid rgba(255, 180, 205, 0.9); background: rgba(255, 255, 255, 0.9); font-size: 12px; padding: 6px 12px; cursor: pointer; }
.view-pill.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.sort-select { min-width: 200px; }

.advanced-panel { margin-top: 12px; background: #fff7fb; border: 1px solid #ffd6e8; border-radius: 14px; padding: 12px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; color: #a35d76; font-weight: 600; }
.panel-head .hint { font-size: 12px; color: #b6788d; font-weight: 400; }

.time-row { display: grid; grid-template-columns: 1.1fr 1.4fr 1.4fr; gap: 10px; align-items: center; margin-top: 8px; }
.time-left { display: flex; align-items: center; gap: 10px; }
.label { font-size: 13px; color: #8c546e; margin-bottom: 6px; }
.pill-group { display: inline-flex; gap: 6px; }
.pill-group button { border: 1px solid rgba(255, 180, 205, 0.9); background: #fff; color: #b05f7a; border-radius: 12px; padding: 6px 10px; cursor: pointer; }
.pill-group button.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.35); }
.quick-pills { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.quick-pills button { border: 1px solid rgba(255, 180, 205, 0.9); background: #fff; color: #b05f7a; border-radius: 12px; padding: 6px 10px; cursor: pointer; }
.quick-pills button.active { background: #ffe1ef; border-color: #ff8bb3; color: #ff4c8a; }
.quick-pills button.ghost { background: #ffeef5; }

.filter-grid { display: grid; grid-template-columns: 1fr 1.4fr 1fr; gap: 10px; margin-top: 10px; }
.filter-card { background: rgba(255, 255, 255, 0.9); border: 1px solid #ffd6e8; border-radius: 12px; padding: 10px; box-shadow: 0 6px 14px rgba(255, 165, 199, 0.2); }
.filter-card .label { margin: 0 0 6px; }
.exif-card .exif-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.exif-card input { width: 100%; border-radius: 10px; border: 1px solid rgba(255, 190, 210, 0.9); padding: 8px 10px; font-size: 12px; outline: none; background: #fff; }
.exif-card input:focus { border-color: #ff8bb3; }
.size-card .hint { margin-top: 6px; color: #b6788d; font-size: 12px; }

.results { padding: 6px 18px 10px; flex: 1; display: flex; flex-direction: column; }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; align-content: flex-start; flex: 1; }
.gallery.masonry { column-count: 3; column-gap: 16px; }
.gallery.masonry .photo { break-inside: avoid; margin-bottom: 16px; }
.gallery.large { display: flex; flex-direction: column; gap: 16px; }
.gallery.large .photo { display: flex; min-height: 200px; }
.gallery.large .photo img { width: 45%; height: 100%; object-fit: cover; }
.gallery.large .caption { flex: 1; padding: 16px; }

.photo { background: rgba(255, 255, 255, 0.94); border-radius: 14px; box-shadow: 0 10px 20px rgba(255, 165, 199, 0.26); overflow: hidden; cursor: pointer; display: flex; flex-direction: column; transition: transform 0.1s ease; }
.photo:hover { transform: translateY(-2px); }
.photo img { width: 100%; height: 210px; object-fit: cover; background: #ffeef5; }
.caption { padding: 10px 12px 6px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #5a2f3d; }
.caption .date { color: #b57a90; }
.meta-row { display: flex; justify-content: space-between; padding: 0 12px 8px; font-size: 12px; color: #a35d76; }
.tag-line { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 12px 12px; }
.tag-chip { padding: 4px 10px; border-radius: 999px; background: #ffeef5; color: #b05f7a; font-size: 12px; border: 1px solid rgba(255, 180, 205, 0.6); }

.empty-box { grid-column: 1 / -1; padding: 40px; text-align: center; color: #b6788d; background: rgba(255, 255, 255, 0.9); border-radius: 14px; }

.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding: 8px 0 16px; }
.pagination { display: flex; justify-content: center; }
:deep(.el-pagination.is-background .el-pager li) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination.is-background .el-pager li.is-active) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
:deep(.el-pagination.is-background .el-pager li:hover) { background-color: #ffdce9; }
:deep(.el-pagination button) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }

:deep(.el-select .el-input__wrapper) { background: #fff; border-radius: 12px; box-shadow: inset 0 0 0 1px rgba(255, 190, 210, 0.8); }
:deep(.el-date-editor) { width: 100%; }
:deep(.el-slider__bar) { background: linear-gradient(90deg, #ff8bb3, #ff6fa0); }
:deep(.el-slider__button) { border-color: #ff8bb3; }
footer { text-align: center; font-size: 12px; color: #b57a90; }

@media (max-width: 1100px) {
  .sidebar { display: none; }
  .time-row { grid-template-columns: 1fr; }
  .filter-grid { grid-template-columns: 1fr; }
  .gallery { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
  .gallery.masonry { column-count: 2; }
}
</style>
