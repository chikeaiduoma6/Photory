<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const palette = ['#ff9db8', '#8ed0ff', '#ffd27f', '#9dd0a5', '#c3a0ff', '#f7a3ff']

const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (path: string) => (!path ? '' : path.startsWith('http') ? path : `${apiBase}${path}`)

const detail = ref<any>(null)
const loading = ref(true)
const saving = ref(false)

const baseAdjustments = {
  brightness: 0,
  contrast: 0,
  saturation: 0,
  exposure: 0,
  shadows: 0,
  highlights: 0,
  temperature: 0,
  tint: 0,
  sharpen: 0,
}

const editorState = ref({
  cropPreset: 'free',
  customCrop: { width: 1920, height: 1080 },
  rotation: 0,
  zoom: 1,
  adjustments: { ...baseAdjustments },
  cropBox: { x: 0, y: 0, w: 1, h: 1 },
})

const cropHistory = ref([{ ...editorState.value }])
const cropCursor = ref(0)
const rotateHistory = ref([{ rotation: editorState.value.rotation, zoom: editorState.value.zoom }])
const rotateCursor = ref(0)
const adjustHistory = ref([{ ...editorState.value.adjustments }])
const adjustCursor = ref(0)

const compareMode = ref<'side' | 'main'>('side')
const showOriginal = ref(false)
const exportOption = ref<'override' | 'new'>('override')
const exportName = ref('')
const exportFolder = ref('')
const exportTags = ref<{ name: string; color: string }[]>([])
const newExportTag = ref('')
const newExportColor = ref(palette[0])
const versionHistory = ref<{ id?: number; name: string; created_at: string; note: string; type: 'origin' | 'edit' }[]>([])

const navOpen = ref(false)
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
watch(() => router.currentRoute.value.fullPath, () => closeNav())

const fallbackImage = new URL('../assets/pink_sky.jpg', import.meta.url).href
const tokenParam = computed(() => (authStore.token ? `?jwt=${authStore.token}` : ''))
const versionStamp = computed(() => (detail.value?.updated_at ? `&v=${encodeURIComponent(detail.value.updated_at)}` : ''))
const originalUrl = computed(() => (detail.value ? withBase(`${detail.value.raw_url}${tokenParam.value}${versionStamp.value}`) : ''))
const thumbUrl = computed(() => (detail.value ? withBase(`${detail.value.thumb_url || detail.value.raw_url}${tokenParam.value}${versionStamp.value}`) : ''))
const previewSrc = computed(() => originalUrl.value || thumbUrl.value || fallbackImage)

const cropPresets = [
  { label: '自由', value: 'free', aspect: 'auto' },
  { label: '1:1', value: '1:1', aspect: '1 / 1' },
  { label: '4:3', value: '4:3', aspect: '4 / 3' },
  { label: '3:2', value: '3:2', aspect: '3 / 2' },
  { label: '16:9', value: '16:9', aspect: '16 / 9' },
  { label: '9:16', value: '9:16', aspect: '9 / 16' },
  { label: '自定义', value: 'custom', aspect: 'custom' },
]

const adjustmentDefs = [
  { key: 'brightness', label: '亮度', min: -100, max: 100 },
  { key: 'contrast', label: '对比度', min: -100, max: 100 },
  { key: 'saturation', label: '饱和度', min: -100, max: 100 },
  { key: 'exposure', label: '曝光', min: -100, max: 100 },
  { key: 'shadows', label: '阴影', min: -100, max: 100 },
  { key: 'highlights', label: '高光', min: -100, max: 100 },
  { key: 'temperature', label: '色温', min: -100, max: 100 },
  { key: 'tint', label: '色调', min: -180, max: 180 },
  { key: 'sharpen', label: '锐化', min: 0, max: 120 },
]

const cropAspect = computed(() => {
  if (editorState.value.cropPreset === 'custom') {
    const w = Number(editorState.value.customCrop.width)
    const h = Number(editorState.value.customCrop.height)
    return w > 0 && h > 0 ? `${w} / ${h}` : 'auto'
  }
  const preset = cropPresets.find(p => p.value === editorState.value.cropPreset)
  return preset?.aspect || 'auto'
})
const cropAspectLabel = computed(() => {
  if (editorState.value.cropPreset === 'custom') {
    const { width, height } = editorState.value.customCrop
    return width && height ? `${width}:${height}` : '自定义'
  }
  return cropPresets.find(p => p.value === editorState.value.cropPreset)?.label || '自由'
})
const cropGuideStyle = computed(() => {
  const box = editorState.value.cropBox
  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.w * 100}%`,
    height: `${box.h * 100}%`,
    aspectRatio: cropAspect.value === 'auto' ? 'unset' : cropAspect.value,
  }
})
const clipStyle = computed(() => {
  const box = editorState.value.cropBox
  const top = box.y * 100
  const left = box.x * 100
  const bottom = (1 - box.y - box.h) * 100
  const right = (1 - box.x - box.w) * 100
  return {
    clipPath: `inset(${top}% ${right}% ${bottom}% ${left}%)`,
  }
})

const editedStyle = computed(() => {
  const a = editorState.value.adjustments
  const brightness = 1 + (a.brightness + a.exposure * 0.6) / 100
  const contrast = 1 + (a.contrast + a.highlights * 0.35 - a.shadows * 0.25) / 100
  const saturation = 1 + a.saturation / 100
  const warmth = 1 + a.temperature / 200
  const hue = a.tint
  const sharpen = Math.max(0, a.sharpen) / 200
  return {
    filter: `brightness(${brightness}) contrast(${contrast}) saturate(${saturation * warmth}) hue-rotate(${hue}deg) sepia(${Math.max(
      0,
      a.temperature
    ) / 140}) drop-shadow(0 8px 18px rgba(0,0,0,${0.08 + sharpen}))`,
    transform: `rotate(${editorState.value.rotation}deg) scale(${editorState.value.zoom})`,
    ...clipStyle.value,
  }
})
const exifTags = computed(() => Array.from(new Set(detail.value?.exif_tags || [])))

async function fetchDetail() {
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/images/${route.params.id}`)
    detail.value = res.data
    exportName.value = res.data.name || res.data.original_name || '编辑版本'
    exportFolder.value = res.data.folder || '默认图库'
    exportTags.value = (res.data.tag_objects || []).map((t: any) => ({ name: t.name, color: t.color || palette[0] }))
    versionHistory.value = (res.data.version_history || []).map((v: any) => ({ ...v, type: 'edit' as const }))
    resetHistories()
  } catch (err) {
    ElMessage.error('获取图片详情失败')
    router.push('/')
  } finally {
    loading.value = false
  }
}

function resetHistories() {
  editorState.value = {
    cropPreset: 'free',
    customCrop: { width: 1920, height: 1080 },
    rotation: 0,
    zoom: 1,
    adjustments: { ...baseAdjustments },
    cropBox: { x: 0, y: 0, w: 1, h: 1 },
  }
  cropHistory.value = [{ ...editorState.value }]
  cropCursor.value = 0
  rotateHistory.value = [{ rotation: 0, zoom: 1 }]
  rotateCursor.value = 0
  adjustHistory.value = [{ ...baseAdjustments }]
  adjustCursor.value = 0
  compareMode.value = 'side'
  showOriginal.value = false
}

function restoreOriginal() {
  resetHistories()
  ElMessage.success('已恢复到初始编辑状态')
}

function pushCropHistory() {
  cropHistory.value = cropHistory.value.slice(0, cropCursor.value + 1)
  cropHistory.value.push({
    ...editorState.value,
    customCrop: { ...editorState.value.customCrop },
    cropBox: { ...editorState.value.cropBox },
    adjustments: { ...editorState.value.adjustments },
  })
  if (cropHistory.value.length > 30) cropHistory.value.shift()
  cropCursor.value = cropHistory.value.length - 1
}
function cropUndo() {
  if (cropCursor.value <= 0) return
  cropCursor.value -= 1
  const state: any = cropHistory.value[cropCursor.value]
  editorState.value = {
    ...state,
    customCrop: { ...state.customCrop },
    cropBox: { ...state.cropBox },
    adjustments: { ...state.adjustments },
  }
}
function cropReset() {
  editorState.value.cropPreset = 'free'
  editorState.value.customCrop = { width: 1920, height: 1080 }
  editorState.value.cropBox = { x: 0, y: 0, w: 1, h: 1 }
  pushCropHistory()
}

function pushRotateHistory() {
  rotateHistory.value = rotateHistory.value.slice(0, rotateCursor.value + 1)
  rotateHistory.value.push({ rotation: editorState.value.rotation, zoom: editorState.value.zoom })
  if (rotateHistory.value.length > 30) rotateHistory.value.shift()
  rotateCursor.value = rotateHistory.value.length - 1
}
function rotateUndo() {
  if (rotateCursor.value <= 0) return
  rotateCursor.value -= 1
  const state = rotateHistory.value[rotateCursor.value]
  editorState.value.rotation = state.rotation
  editorState.value.zoom = state.zoom
}
function rotateReset() {
  editorState.value.rotation = 0
  editorState.value.zoom = 1
  pushRotateHistory()
}

function pushAdjustHistory() {
  adjustHistory.value = adjustHistory.value.slice(0, adjustCursor.value + 1)
  adjustHistory.value.push({ ...editorState.value.adjustments })
  if (adjustHistory.value.length > 30) adjustHistory.value.shift()
  adjustCursor.value = adjustHistory.value.length - 1
}
function adjustUndo() {
  if (adjustCursor.value <= 0) return
  adjustCursor.value -= 1
  editorState.value.adjustments = { ...adjustHistory.value[adjustCursor.value] }
}
function adjustReset() {
  editorState.value.adjustments = { ...baseAdjustments }
  pushAdjustHistory()
}

function centerBoxForRatio(ratio: number) {
  ratio = Math.max(0.01, ratio)
  let w = 0.9
  let h = w / ratio
  if (h > 0.9) {
    h = 0.9
    w = h * ratio
  }
  const x = (1 - w) / 2
  const y = (1 - h) / 2
  editorState.value.cropBox = { x, y, w, h }
}

function applyCropPreset(value: string) {
  editorState.value.cropPreset = value
  if (value === 'free') {
    editorState.value.cropBox = { x: 0, y: 0, w: 1, h: 1 }
  } else if (value === 'custom') {
    const w = Number(editorState.value.customCrop.width) || 1
    const h = Number(editorState.value.customCrop.height) || 1
    centerBoxForRatio(w / h)
  } else {
    const preset = cropPresets.find(p => p.value === value)
    if (preset && preset.aspect !== 'auto') {
      const parts = preset.aspect.split('/').map(s => Number(s.trim()))
      const a = parts[0]
      const b = parts[1]
      if (a > 0 && b > 0) centerBoxForRatio(a / b)
    }
  }
  pushCropHistory()
}
function updateCustomCrop() {
  if (editorState.value.cropPreset !== 'custom') return
  const w = Number(editorState.value.customCrop.width) || 1
  const h = Number(editorState.value.customCrop.height) || 1
  centerBoxForRatio(w / h)
  pushCropHistory()
}

function applyRotation(delta: number) {
  editorState.value.rotation = (editorState.value.rotation + delta + 360) % 360
  pushRotateHistory()
}
function updateRotation(value: number, commit = false) {
  editorState.value.rotation = value
  if (commit) pushRotateHistory()
}
function updateZoom(value: number, commit = false) {
  editorState.value.zoom = value
  if (commit) pushRotateHistory()
}

function setAdjustment(key: string, value: number, commit = false) {
  ;(editorState.value.adjustments as any)[key] = value
  if (commit) pushAdjustHistory()
}

function goDetail() { router.push(`/images/${route.params.id}`) }
function logout() { authStore.logout(); router.push('/auth/login') }

function confirmExit() {
  return ElMessageBox.confirm(
    '确定要退出编辑吗？对图片所做的所有修改将不能被保存，恢复到原图状态。',
    '退出编辑',
    {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
      customClass: 'pink-confirm',
    }
  )
}
async function handleExit() {
  try {
    await confirmExit()
    goDetail()
  } catch {
    /* cancelled */
  }
}

function download() { if (originalUrl.value) window.open(originalUrl.value, '_blank') }

function addExportTag() {
  const name = newExportTag.value.trim()
  if (!name) return
  if (exportTags.value.some(t => t.name === name)) {
    ElMessage.warning('标签已存在')
    return
  }
  exportTags.value.push({ name, color: newExportColor.value })
  newExportTag.value = ''
  newExportColor.value = palette[Math.floor(Math.random() * palette.length)]
}
function removeExportTag(name: string) {
  exportTags.value = exportTags.value.filter(t => t.name !== name)
}

async function saveVersion(mode?: 'override' | 'new') {
  const target = mode || exportOption.value
  saving.value = true
  try {
    const payload: any = {
      option: target,
      name: exportName.value || detail.value?.name,
      folder: exportFolder.value || detail.value?.folder,
      tags: exportTags.value,
      crop: {
        preset: editorState.value.cropPreset,
        width: editorState.value.customCrop.width,
        height: editorState.value.customCrop.height,
      },
      rotation: editorState.value.rotation,
      zoom: editorState.value.zoom,
      adjustments: editorState.value.adjustments,
    }
    if (editorState.value.cropPreset === 'free') {
      payload.crop_box = editorState.value.cropBox
    }
    const res = await axios.post(`/api/v1/images/${route.params.id}/export`, payload)
    const item = res.data.item
    detail.value = item
    versionHistory.value = (item.version_history || []).map((v: any) => ({ ...v, type: 'edit' as const }))
    ElMessage.success(target === 'override' ? '已覆盖当前版本' : '已另存为新图片')
    if (target === 'new' && item.id && item.id !== Number(route.params.id)) {
      router.replace(`/images/${item.id}/edit`)
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const stageRef = ref<HTMLElement | null>(null)
const dragging = ref(false)
const dragMode = ref<'move' | 'draw'>('move')
const dragStart = ref({ x: 0, y: 0, box: { x: 0, y: 0, w: 1, h: 1 } })

function stagePos(e: MouseEvent) {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return { x: 0, y: 0 }
  return {
    x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
    y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
  }
}

function startCrop(e: MouseEvent) {
  if (editorState.value.cropPreset !== 'free') return
  dragging.value = true
  dragMode.value = (e.target as HTMLElement).classList.contains('area') ? 'move' : 'draw'
  dragStart.value = { x: stagePos(e).x, y: stagePos(e).y, box: { ...editorState.value.cropBox } }
  window.addEventListener('mousemove', onCropMove)
  window.addEventListener('mouseup', endCrop)
}

function onCropMove(e: MouseEvent) {
  if (!dragging.value) return
  const pos = stagePos(e)
  const box = { ...editorState.value.cropBox }
  if (dragMode.value === 'move') {
    const dx = pos.x - dragStart.value.x
    const dy = pos.y - dragStart.value.y
    box.x = Math.min(1 - box.w, Math.max(0, dragStart.value.box.x + dx))
    box.y = Math.min(1 - box.h, Math.max(0, dragStart.value.box.y + dy))
  } else {
    const x1 = Math.min(pos.x, dragStart.value.x)
    const y1 = Math.min(pos.y, dragStart.value.y)
    const w = Math.abs(pos.x - dragStart.value.x)
    const h = Math.abs(pos.y - dragStart.value.y)
    box.x = Math.max(0, Math.min(1, x1))
    box.y = Math.max(0, Math.min(1, y1))
    box.w = Math.min(1 - box.x, w)
    box.h = Math.min(1 - box.y, h)
  }
  editorState.value.cropBox = box
}

function endCrop() {
  if (!dragging.value) return
  dragging.value = false
  window.removeEventListener('mousemove', onCropMove)
  window.removeEventListener('mouseup', endCrop)
  pushCropHistory()
}

onMounted(fetchDetail)
</script>

<template>
  <div class="dashboard editor-page" v-if="detail">
    <aside class="sidebar">
      <div class="logo">
        <div class="icon">📸</div>
        <div class="text">
          <h1>Photory</h1>
          <p>记录世间每一份美好，让瞬间永恒～</p>
        </div>
      </div>

      <nav>
        <a v-for="item in [
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
        ]" :key="item.path" :class="{ active: $route.path === item.path || $route.path.startsWith(item.path + '/') }" @click="router.push(item.path)">
          {{ item.icon }} {{ item.label }}
        </a>
      </nav>
    </aside>

    <main>
      <header class="mobile-topbar">
        <button class="icon-btn ghost" @click="toggleNav">☰</button>
        <div class="mobile-brand">
          <span class="logo-mini">✂️</span>
          <span>在线编辑</span>
        </div>
        <button class="icon-btn ghost" @click="goDetail">↩️</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">在线编辑器</div>
          <div class="subtitle">支持裁剪 / 旋转 / 色彩调节，灵活对比与导出</div>
        </div>
        <div class="right">
          <button class="pill-btn ghost" @click="download">下载</button>
          <button class="pill-btn ghost" @click="restoreOriginal">恢复原图</button>
          <button class="pill-btn danger" @click="handleExit">退出编辑</button>
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
                <p>在线编辑</p>
              </div>
            </div>
            <button class="icon-btn ghost" @click="closeNav">✕</button>
          </div>
          <nav>
            <a v-for="item in [
              { label: '首页', icon: '🏠', path: '/' },
              { label: '搜索引擎', icon: '🔎', path: '/search' },
              { label: '上传中心', icon: '☁️', path: '/upload' },
              { label: '标签', icon: '🏷️', path: '/tags' },
              { label: '回收站', icon: '🗑️', path: '/recycle' },
            ]" :key="item.path" :class="{ active: $route.path === item.path || $route.path.startsWith(item.path + '/') }" @click="router.push(item.path)">
              {{ item.icon }} {{ item.label }}
            </a>
          </nav>
        </div>
      </div>

      <section class="editor-layout">
        <div class="canvas-panel">
          <div class="info-inline">
            <div class="name-tags">
              <div class="img-name">{{ detail.name || detail.original_name }}</div>
              <div class="tag-line">
                <span v-for="t in detail.tag_objects || []" :key="t.id || t.name" class="tag-chip" :style="{ background: (t.color || '') + '22', color: '#b05f7a', borderColor: t.color || '#ff9db8' }">
                  <span class="dot" :style="{ background: t.color }"></span>{{ t.name }}
                </span>
                <span v-if="!detail.tag_objects?.length" class="muted">暂无自定义标签</span>
              </div>
              <div class="tag-line exif-line">
                <span v-for="t in exifTags" :key="t" class="tag-chip exif">{{ t }}</span>
                <span v-if="!exifTags.length" class="muted">暂无 EXIF 标签</span>
              </div>
            </div>
            <div class="view-buttons">
              <button class="pill-btn mini" :class="{ active: compareMode === 'side' }" @click="compareMode = compareMode === 'side' ? 'main' : 'side'">
                {{ compareMode === 'side' ? '隐藏对比' : '双栏对比' }}
              </button>
              <button class="pill-btn mini ghost" @click="showOriginal = true">查看原图</button>
              <button class="pill-btn mini ghost" @click="showOriginal = false">显示编辑版</button>
            </div>
          </div>

          <div class="preview-box">
            <div class="image-stage" ref="stageRef" @mouseleave="showOriginal = false" @mousedown="startCrop">
              <img :src="previewSrc" :alt="detail.name" class="main-img" :style="showOriginal ? {} : editedStyle" />
              <div class="crop-guides" :class="{ active: cropAspect !== 'auto' }">
                <div class="area" :style="cropGuideStyle">
                  <span>{{ cropAspectLabel }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="compare-panel" v-if="compareMode === 'side'">
            <div class="compare-card">
              <div class="card-title">原图</div>
              <img :src="previewSrc" :alt="detail.name" />
            </div>
            <div class="compare-card">
              <div class="card-title">编辑版</div>
              <img :src="previewSrc" :alt="detail.name" :style="editedStyle" />
            </div>
          </div>

          <div class="mobile-actions">
            <button class="pill-btn ghost" @click="download">下载</button>
            <button class="pill-btn ghost" @click="restoreOriginal">恢复原图</button>
            <button class="pill-btn danger" @click="handleExit">退出编辑</button>
          </div>
        </div>

        <div class="controls">
          <div class="control-card">
            <div class="section-title">裁剪</div>
            <div class="preset-grid">
              <button
                v-for="preset in cropPresets"
                :key="preset.value"
                class="chip-btn"
                :class="{ active: editorState.cropPreset === preset.value }"
                @click="applyCropPreset(preset.value)"
              >
                {{ preset.label }}
              </button>
            </div>
            <div class="custom-size" v-if="editorState.cropPreset === 'custom'">
              <label>宽</label>
              <input type="number" v-model.number="editorState.customCrop.width" min="1" @change="updateCustomCrop" />
              <label>高</label>
              <input type="number" v-model.number="editorState.customCrop.height" min="1" @change="updateCustomCrop" />
            </div>
            <div class="module-actions">
              <button class="pill-btn ghost mini" @click="cropUndo">撤销一步</button>
              <button class="pill-btn ghost mini" @click="cropReset">全部重置</button>
            </div>
          </div>

          <div class="control-card">
            <div class="section-title">旋转</div>
            <div class="btn-row">
              <button class="chip-btn" @click="applyRotation(-90)">-90°</button>
              <button class="chip-btn" @click="applyRotation(90)">+90°</button>
              <button class="chip-btn ghost" @click="updateRotation(0, true)">归零</button>
            </div>
            <div class="slider-row">
              <div class="label">角度</div>
              <div class="value">{{ editorState.rotation }}°</div>
              <input
                type="range"
                min="-180"
                max="180"
                :value="editorState.rotation"
                @input="e => updateRotation(Number((e.target as HTMLInputElement).value))"
                @change="e => updateRotation(Number((e.target as HTMLInputElement).value), true)"
              />
            </div>
            <div class="slider-row">
              <div class="label">缩放</div>
              <div class="value">{{ editorState.zoom.toFixed(2) }}×</div>
              <input
                type="range"
                min="0.7"
                max="1.4"
                step="0.01"
                :value="editorState.zoom"
                @input="e => updateZoom(Number((e.target as HTMLInputElement).value))"
                @change="e => updateZoom(Number((e.target as HTMLInputElement).value), true)"
              />
            </div>
            <div class="module-actions">
              <button class="pill-btn ghost mini" @click="rotateUndo">撤销一步</button>
              <button class="pill-btn ghost mini" @click="rotateReset">全部重置</button>
            </div>
          </div>

          <div class="control-card adjustments">
            <div class="section-title">调节</div>
            <div v-for="def in adjustmentDefs" :key="def.key" class="slider-row">
              <div class="label">{{ def.label }}</div>
              <div class="value">{{ editorState.adjustments[def.key as keyof typeof baseAdjustments] }}</div>
              <input
                type="range"
                :min="def.min"
                :max="def.max"
                step="1"
                :value="editorState.adjustments[def.key as keyof typeof baseAdjustments]"
                @input="e => setAdjustment(def.key, Number((e.target as HTMLInputElement).value))"
                @change="e => setAdjustment(def.key, Number((e.target as HTMLInputElement).value), true)"
              />
            </div>
            <div class="module-actions">
              <button class="pill-btn ghost mini" @click="adjustUndo">撤销一步</button>
              <button class="pill-btn ghost mini" @click="adjustReset">全部重置</button>
            </div>
          </div>

          <div class="control-card export-card">
            <div class="section-title">导出 / 版本</div>
            <div class="export-options">
              <label class="radio"><input type="radio" value="override" v-model="exportOption" /> 覆盖当前版本</label>
              <label class="radio"><input type="radio" value="new" v-model="exportOption" /> 另存为新图片</label>
            </div>
            <div class="form-grid">
              <label>图片名称</label>
              <input class="text-input" v-model="exportName" placeholder="输入图片名称" />
              <label>文件夹</label>
              <input class="text-input" v-model="exportFolder" placeholder="如：默认图库" />
            </div>
            <div class="tag-add">
              <input class="text-input" v-model="newExportTag" placeholder="输入标签名称" @keyup.enter="addExportTag" />
              <input v-model="newExportColor" type="color" class="color-picker" />
              <button class="pill-btn mini" @click="addExportTag">添加标签</button>
            </div>
            <div class="tag-line export-tags">
              <span
                v-for="t in exportTags"
                :key="t.name"
                class="tag-chip"
                :style="{ background: (t.color || '') + '22', color: '#b05f7a', borderColor: t.color || '#ff9db8' }"
                @click="removeExportTag(t.name)"
              >
                <span class="dot" :style="{ background: t.color }"></span>{{ t.name }} ×
              </span>
              <span v-if="!exportTags.length" class="muted">暂无标签，点击上方添加</span>
            </div>
            <div class="history-actions">
              <button class="pill-btn" :disabled="saving" @click="saveVersion(exportOption)">应用保存</button>
            </div>

            <div class="version-list">
              <div v-if="!versionHistory.length" class="muted">暂无历史版本（仅覆盖操作会记录）</div>
              <div v-for="(version, index) in versionHistory" :key="index" class="version-item">
                <div class="dot" :class="version.type"></div>
                <div class="v-body">
                  <div class="v-title">{{ version.name }}</div>
                  <div class="v-note">{{ version.note || '历史版本' }}</div>
                </div>
                <span class="v-time">{{ version.created_at?.slice(0, 16) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <div v-else class="loading">加载中...</div>
</template>

<style scoped>
.dashboard { display: flex; min-height: 100vh; background: linear-gradient(135deg, #ffeef5, #ffe5f0); color: #4b4b4b; }
.sidebar { width: 240px; background: linear-gradient(180deg, #fff7fb, #ffeef5); border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 20px; position: sticky; top: 0; height: 100vh; }
.logo { display: flex; gap: 10px; margin-bottom: 20px; }
.logo .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 36px; height: 36px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.logo h1 { font-size: 18px; color: #ff4c8a; margin: 0; }
.logo p { font-size: 11px; color: #b6788d; margin: 0; }
nav a { display: block; padding: 9px 12px; border-radius: 12px; font-size: 14px; color: #6b3c4a; margin: 4px 0; cursor: pointer; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }

main { flex: 1; display: flex; flex-direction: column; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.92); gap: 10px; }
.topbar .left { display: flex; flex-direction: column; gap: 4px; }
.title { font-weight: 700; color: #ff4c8a; font-size: 18px; }
.subtitle { font-size: 12px; color: #a36e84; }
.topbar .right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }

.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn.ghost { background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(255, 190, 210, 0.7); }

.pill-btn { border: none; border-radius: 999px; padding: 8px 14px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 13px; cursor: pointer; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.pill-btn.ghost { background: #ffeef5; color: #b05f7a; box-shadow: none; border: 1px solid rgba(255, 180, 205, 0.7); }
.pill-btn.danger { background: linear-gradient(135deg, #ff9c9c, #ff6b6b); }
.pill-btn.mini { padding: 6px 10px; font-size: 12px; }
.pill-btn.mini.ghost { background: #fff; }
.pill-btn:disabled { opacity: 0.65; cursor: not-allowed; }

.editor-layout { display: grid; grid-template-columns: 1.6fr 1fr; gap: 14px; padding: 16px 18px 14px; }
.canvas-panel { background: #fff; border-radius: 24px; padding: 16px; box-shadow: 0 14px 28px rgba(255, 165, 199, 0.28); }
.info-inline { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; gap: 10px; flex-wrap: wrap; }
.img-name { font-size: 16px; color: #613448; font-weight: 600; }
.tag-line { display: flex; gap: 6px; flex-wrap: wrap; }
.tag-line.exif-line { margin-top: 4px; }
.tag-chip { background: #ffe4f0; border-radius: 999px; padding: 4px 10px; font-size: 12px; color: #b05f7a; border: 1px solid transparent; display: inline-flex; align-items: center; gap: 6px; }
.tag-chip .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.tag-chip.exif { background: #e9f4ff; color: #5a6f8c; border-color: #b6d6ff; }
.muted { color: #b57a90; font-size: 12px; }
.view-buttons { display: flex; gap: 8px; flex-wrap: wrap; }

.preview-box { margin-top: 12px; padding: 12px; background: #fdf6fa; border-radius: 18px; }
.image-stage { position: relative; border-radius: 16px; background: radial-gradient(circle at 30% 20%, rgba(255, 214, 230, 0.4), rgba(255, 231, 240, 0.95)); height: 520px; display: flex; align-items: center; justify-content: center; overflow: hidden; user-select: none; }
.main-img { max-width: 100%; max-height: 100%; border-radius: 14px; transition: filter 0.12s ease, transform 0.12s ease; background: #f6e9f1; }
.crop-guides { position: absolute; inset: 14px; border: 1px dashed transparent; border-radius: 14px; pointer-events: none; }
.crop-guides .area { position: absolute; border: 1px solid rgba(255, 120, 165, 0.8); background: rgba(255, 255, 255, 0.14); display: flex; align-items: center; justify-content: center; color: #ff6fa0; font-size: 12px; border-radius: 10px; pointer-events: auto; }
.crop-guides.active { border-color: rgba(255, 157, 184, 0.6); }
.compare-panel { margin-top: 12px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.compare-card { background: #fff8fb; border-radius: 14px; padding: 10px; box-shadow: 0 10px 18px rgba(255, 152, 201, 0.25); }
.compare-card img { width: 100%; border-radius: 10px; object-fit: cover; background: #f9edf3; }
.card-title { font-size: 13px; color: #b05f7a; margin-bottom: 6px; }
.mobile-actions { display: none; gap: 8px; flex-wrap: wrap; margin-top: 12px; }

.controls { display: flex; flex-direction: column; gap: 12px; }
.control-card { background: rgba(255, 255, 255, 0.96); border-radius: 20px; padding: 14px; box-shadow: 0 12px 26px rgba(255, 165, 199, 0.22); }
.section-title { color: #ff4c8a; font-weight: 700; margin-bottom: 6px; }
.preset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 4px; }
.chip-btn { border-radius: 12px; border: 1px solid rgba(255, 180, 205, 0.8); background: #fff; color: #b05f7a; padding: 6px 10px; font-size: 12px; cursor: pointer; }
.chip-btn.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 6px 14px rgba(255, 120, 165, 0.35); }
.chip-btn.ghost { background: #ffeef5; }
.custom-size { display: grid; grid-template-columns: auto 1fr auto 1fr; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; color: #a35d76; }
.custom-size input { width: 100%; border-radius: 10px; border: 1px solid rgba(255, 180, 205, 0.9); padding: 6px 10px; outline: none; }

.btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.slider-row { display: grid; grid-template-columns: 70px 48px 1fr; align-items: center; gap: 10px; font-size: 13px; margin-top: 8px; }
.slider-row .label { color: #a35d76; }
.slider-row .value { color: #b05f7a; text-align: right; }
.slider-row input[type="range"] { width: 100%; accent-color: #ff6fa0; height: 6px; border-radius: 10px; background: linear-gradient(90deg, #ff8bb3, #ffeef5); }
.adjustments .slider-row { grid-template-columns: 70px 40px 1fr; }

.module-actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

.export-options { display: flex; gap: 12px; margin: 8px 0; color: #a35d76; font-size: 13px; flex-wrap: wrap; }
.radio { display: flex; align-items: center; gap: 6px; }
.form-grid { display: grid; grid-template-columns: 100px 1fr; gap: 6px 10px; font-size: 13px; color: #a35d76; }
.text-input { width: 100%; border-radius: 12px; border: 1px solid rgba(255, 180, 205, 0.9); padding: 8px 10px; font-size: 13px; color: #4b4b4b; outline: none; }
.tag-add { display: grid; grid-template-columns: 1fr 100px auto; gap: 12px; margin: 8px 0; align-items: center; }
.tag-line.export-tags { margin-top: 6px; }
.history-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
.version-list { display: flex; flex-direction: column; gap: 8px; max-height: 220px; overflow: auto; }
.version-item { display: flex; align-items: center; gap: 8px; background: #fff5f8; border-radius: 12px; padding: 8px 10px; }
.version-item .dot { width: 10px; height: 10px; border-radius: 50%; background: #ff8bb3; }
.version-item .dot.origin { background: #7ac7ff; }
.v-body { flex: 1; }
.v-title { font-size: 13px; color: #613448; }
.v-note { font-size: 12px; color: #b57a90; }
.v-time { font-size: 12px; color: #b57a90; }

.loading { display: flex; align-items: center; justify-content: center; height: 100vh; color: #a35d76; background: linear-gradient(135deg, #ffeef5, #ffe5f0); }
:deep(.pink-confirm .el-message-box__title) { color: #ff4c8a; }
:deep(.pink-confirm .el-button--primary) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); border: none; }
:deep(.pink-confirm .el-button--default) { border-color: #ffb6cf; color: #b05f7a; }

/* 移动端 */
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

@media (max-width: 1180px) { .editor-layout { grid-template-columns: 1fr; } .topbar { align-items: flex-start; flex-direction: column; } .canvas-panel { order: -1; } }
@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .topbar .right { display: none; }
  .editor-layout { padding-inline: 12px; }
  .image-stage { height: 440px; }
  .compare-panel { grid-template-columns: 1fr; }
  .mobile-actions { display: flex; }
}
@media (max-width: 640px) {
  .preset-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .custom-size { grid-template-columns: repeat(2, 1fr); row-gap: 8px; }
  .form-grid { grid-template-columns: 1fr; }
  .tag-add { grid-template-columns: 1fr; }
  .slider-row { grid-template-columns: 60px 40px 1fr; }
  .tag-line, .view-buttons { width: 100%; }
  .image-stage { height: 360px; }
}
</style>
