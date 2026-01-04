<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'
import { useLocale } from '@/composables/useLocale'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()
const links = computed(() => getNavLinks(preferencesStore.language))
const { text } = useLocale()

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
  rotation: 0,
  zoom: 1,
  pan: { x: 0, y: 0 },
  adjustments: { ...baseAdjustments },
})

type CropPreset = 'free' | '1:1' | '4:3' | '3:4' | '16:9' | '9:16' | '3:2' | '2:3' | 'custom'
const cropPreset = ref<CropPreset>('free')
const cropCustomW = ref<number | null>(null)
const cropCustomH = ref<number | null>(null)

const rotateHistory = ref([{ rotation: editorState.value.rotation, zoom: editorState.value.zoom, pan: { ...editorState.value.pan } }])
const rotateCursor = ref(0)
const adjustHistory = ref([{ ...editorState.value.adjustments }])
const adjustCursor = ref(0)

const compareMode = ref<'side' | 'main'>('side')
const showOriginal = ref(false)
const exportOption = ref<'override' | 'new'>('override')
const exportName = ref('')
const exportTags = ref<{ name: string; color: string }[]>([])
const newExportTag = ref('')
const newExportColor = ref(palette[0])
const versionHistory = ref<{ id?: number; name: string; created_at: string; note: string; type: 'origin' | 'edit' }[]>([])

interface AlbumOption {
  id: number
  title: string
  visibility?: string
}
const albumOptions = ref<AlbumOption[]>([])
const selectedAlbumIds = ref<number[]>([])
const loadingAlbums = ref(false)
const newAlbumTitle = ref('')

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
const stageRef = ref<HTMLElement | null>(null)
const stageSize = ref({ w: 1, h: 1 })
const panning = ref(false)
const panStart = ref({ x: 0, y: 0, pan: { x: 0, y: 0 } })

function updateStageSize() {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return
  stageSize.value = { w: rect.width || 1, h: rect.height || 1 }
}

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

function clamp01(v: number) {
  if (Number.isNaN(v)) return 0
  return Math.max(-1, Math.min(1, v))
}

type CropBox = { x: number; y: number; w: number; h: number }
const freeCropBox = ref<CropBox | null>(null)
const selectingCrop = ref(false)
const selectStartNorm = ref({ x: 0, y: 0 })
const selectNowNorm = ref({ x: 0, y: 0 })
const selectBoxNorm = ref<CropBox | null>(null)

const viewportRef = ref<HTMLElement | null>(null)
const compareEditedRef = ref<HTMLElement | null>(null)
const compareSize = ref({ w: 1, h: 1 })
function updateCompareSize() {
  const rect = compareEditedRef.value?.getBoundingClientRect()
  if (!rect) return
  compareSize.value = { w: rect.width || 1, h: rect.height || 1 }
}

const imageRatio = computed(() => {
  const w = Number(detail.value?.width || 0)
  const h = Number(detail.value?.height || 0)
  if (!w || !h || !Number.isFinite(w) || !Number.isFinite(h)) return 1
  return w / h
})

const sharpenFilterId = 'pm-sharpen-filter'
const sharpenValue = computed(() => {
  const raw = Number(editorState.value.adjustments.sharpen || 0)
  if (!Number.isFinite(raw)) return 0
  return Math.max(0, Math.min(120, raw))
})
const sharpenKernel = computed(() => {
  const strength = Math.min(1.2, sharpenValue.value / 100)
  const s = Number(strength.toFixed(3))
  const neg = s ? -s : 0
  const center = Number((1 + 4 * s).toFixed(3))
  return `0 ${neg} 0 ${neg} ${center} ${neg} 0 ${neg} 0`
})

const filterCss = computed(() => {
  const a = editorState.value.adjustments
  const brightness = 1 + (a.brightness + a.exposure * 0.6) / 100
  const contrast = 1 + (a.contrast + a.highlights * 0.35 - a.shadows * 0.25) / 100
  const saturation = 1 + a.saturation / 100
  const warmth = 1 + a.temperature / 200
  const hue = a.tint
  const filters = [
    `brightness(${brightness})`,
    `contrast(${contrast})`,
    `saturate(${saturation * warmth})`,
    `hue-rotate(${hue}deg)`,
    `sepia(${Math.max(0, a.temperature) / 140})`,
  ]
  if (sharpenValue.value > 0) {
    filters.push(`url(#${sharpenFilterId})`)
  }
  return filters.join(' ')
})

function clamp01Unit(v: number) {
  if (!Number.isFinite(v)) return 0
  return Math.max(0, Math.min(1, v))
}
function normalizeBox(box: CropBox): CropBox {
  let x = clamp01Unit(box.x)
  let y = clamp01Unit(box.y)
  let w = clamp01Unit(box.w)
  let h = clamp01Unit(box.h)
  if (w <= 0 || h <= 0) return { x: 0, y: 0, w: 1, h: 1 }
  if (x + w > 1) w = 1 - x
  if (y + h > 1) h = 1 - y
  w = Math.max(0.0001, w)
  h = Math.max(0.0001, h)
  return { x, y, w, h }
}
function centerBoxByRatio(targetRatio: number): CropBox {
  const imgRatio = imageRatio.value || 1
  const ratio = Math.max(0.0001, Number(targetRatio) || 1)
  if (imgRatio >= ratio) {
    const w = ratio / imgRatio
    return { x: (1 - w) / 2, y: 0, w, h: 1 }
  }
  const h = imgRatio / ratio
  return { x: 0, y: (1 - h) / 2, w: 1, h }
}

const exifTags = computed(() => Array.from(new Set(detail.value?.exif_tags || [])))

async function fetchDetail() {
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/images/${route.params.id}`)
    detail.value = res.data
    exportName.value = res.data.name || res.data.original_name || '编辑版本'
    exportTags.value = (res.data.tag_objects || []).map((t: any) => ({ name: t.name, color: t.color || palette[0] }))
    selectedAlbumIds.value = Array.isArray(res.data.album_ids) ? res.data.album_ids : []
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
    rotation: 0,
    zoom: 1,
    pan: { x: 0, y: 0 },
    adjustments: { ...baseAdjustments },
  }
  cropPreset.value = 'free'
  cropCustomW.value = null
  cropCustomH.value = null
  freeCropBox.value = null
  selectingCrop.value = false
  selectBoxNorm.value = null
  rotateHistory.value = [{ rotation: 0, zoom: 1, pan: { x: 0, y: 0 } }]
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

function pushRotateHistory() {
  rotateHistory.value = rotateHistory.value.slice(0, rotateCursor.value + 1)
  rotateHistory.value.push({
    rotation: editorState.value.rotation,
    zoom: editorState.value.zoom,
    pan: { ...editorState.value.pan },
  })
  if (rotateHistory.value.length > 30) rotateHistory.value.shift()
  rotateCursor.value = rotateHistory.value.length - 1
}
function rotateUndo() {
  if (rotateCursor.value <= 0) return
  rotateCursor.value -= 1
  const state = rotateHistory.value[rotateCursor.value]
  editorState.value.rotation = state.rotation
  editorState.value.zoom = state.zoom
  editorState.value.pan = { ...state.pan }
}
function rotateReset() {
  editorState.value.rotation = 0
  editorState.value.zoom = 1
  editorState.value.pan = { x: 0, y: 0 }
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

function resetView() {
  editorState.value.zoom = 1
  editorState.value.pan = { x: 0, y: 0 }
  pushRotateHistory()
}

const cropRatio = computed<number | null>(() => {
  const preset = cropPreset.value
  if (!preset || preset === 'free') return null
  if (preset === 'custom') {
    const w = Number(cropCustomW.value)
    const h = Number(cropCustomH.value)
    if (!w || !h || !Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return null
    return w / h
  }
  if (preset.includes(':')) {
    const [a, b] = preset.split(':').map(Number)
    if (!a || !b) return null
    return a / b
  }
  return null
})

const activeViewportRatio = computed(() => {
  if (cropPreset.value === 'free') {
    if (!freeCropBox.value) return imageRatio.value || 1
    const b = normalizeBox(freeCropBox.value)
    return ((b.w / b.h) * (imageRatio.value || 1)) || 1
  }
  return cropRatio.value || imageRatio.value || 1
})
const viewportPx = computed(() => {
  const ratio = activeViewportRatio.value || 1
  const inset = 14 * 2
  const availW = Math.max(1, stageSize.value.w - inset)
  const availH = Math.max(1, stageSize.value.h - inset)
  let w = availW
  let h = w / ratio
  if (h > availH) {
    h = availH
    w = h * ratio
  }
  return { w: Math.round(w), h: Math.round(h) }
})

const viewportStyle = computed(() => {
  return {
    width: `${viewportPx.value.w}px`,
    height: `${viewportPx.value.h}px`,
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%)',
  }
})

const baseBox = computed<CropBox>(() => {
  if (cropPreset.value === 'free') return freeCropBox.value ? normalizeBox(freeCropBox.value) : { x: 0, y: 0, w: 1, h: 1 }
  const ratio = cropRatio.value
  if (!ratio) return { x: 0, y: 0, w: 1, h: 1 }
  return normalizeBox(centerBoxByRatio(ratio))
})

const effectiveBox = computed<CropBox>(() => {
  const zoom = Math.max(1, Number(editorState.value.zoom) || 1)
  const base = baseBox.value
  if (zoom <= 1.000001) return base
  const w = base.w / zoom
  const h = base.h / zoom
  const slackX = Math.max(0, (base.w - w) / 2)
  const slackY = Math.max(0, (base.h - h) / 2)
  const pan = editorState.value.pan || { x: 0, y: 0 }
  const px = clamp01(Number(pan.x) || 0)
  const py = clamp01(Number(pan.y) || 0)
  const cx = base.x + base.w / 2 + px * slackX
  const cy = base.y + base.h / 2 + py * slackY
  let x = cx - w / 2
  let y = cy - h / 2
  x = Math.max(base.x, Math.min(base.x + base.w - w, x))
  y = Math.max(base.y, Math.min(base.y + base.h - h, y))
  return normalizeBox({ x, y, w, h })
})

function surfaceStyle(box: CropBox, size: { w: number; h: number }, applyEdits: boolean) {
  const safe = normalizeBox(box)
  const w = Math.max(1, Number(size.w) || 1)
  const h = Math.max(1, Number(size.h) || 1)
  const bgW = w / safe.w
  const bgH = h / safe.h
  const bgX = -safe.x * bgW
  const bgY = -safe.y * bgH
  return {
    backgroundImage: `url(${previewSrc.value})`,
    backgroundRepeat: 'no-repeat',
    backgroundSize: `${bgW}px ${bgH}px`,
    backgroundPosition: `${bgX}px ${bgY}px`,
    filter: applyEdits ? filterCss.value : 'none',
    transform: applyEdits ? `rotate(${Number(editorState.value.rotation) || 0}deg)` : 'none',
    transformOrigin: 'center center',
  }
}

const stageSurfaceStyle = computed(() => surfaceStyle(showOriginal.value ? { x: 0, y: 0, w: 1, h: 1 } : effectiveBox.value, viewportPx.value, !showOriginal.value))
const compareEditedStyle = computed(() => surfaceStyle(effectiveBox.value, compareSize.value, true))
const compareViewportStyle = computed(() => ({ aspectRatio: String(activeViewportRatio.value || 1) }))

const selectionStyle = computed(() => {
  if (!selectingCrop.value || !selectBoxNorm.value) return null
  const b = normalizeBox(selectBoxNorm.value)
  return {
    left: `${Math.round(b.x * viewportPx.value.w)}px`,
    top: `${Math.round(b.y * viewportPx.value.h)}px`,
    width: `${Math.round(b.w * viewportPx.value.w)}px`,
    height: `${Math.round(b.h * viewportPx.value.h)}px`,
  }
})

function setCropPreset(preset: CropPreset) {
  cropPreset.value = preset
  if (preset !== 'custom') {
    cropCustomW.value = null
    cropCustomH.value = null
  }
  if (preset !== 'free') freeCropBox.value = null
  editorState.value.zoom = 1
  editorState.value.pan = { x: 0, y: 0 }
  showOriginal.value = false
}
function resetCrop() {
  cropPreset.value = 'free'
  cropCustomW.value = null
  cropCustomH.value = null
  freeCropBox.value = null
  editorState.value.zoom = 1
  editorState.value.pan = { x: 0, y: 0 }
  showOriginal.value = false
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
  const next = Math.max(1, Math.min(4, Number(value) || 1))
  editorState.value.zoom = Number(next.toFixed(2))
  if (editorState.value.zoom <= 1) editorState.value.pan = { x: 0, y: 0 }
  if (commit) pushRotateHistory()
}
function bumpZoom(delta: number) {
  const next = Math.max(1, Math.min(4, Number(editorState.value.zoom || 1) + delta))
  editorState.value.zoom = Number(next.toFixed(2))
  if (editorState.value.zoom <= 1) editorState.value.pan = { x: 0, y: 0 }
  pushRotateHistory()
}

function onWheel(e: WheelEvent) {
  const step = e.shiftKey ? 0.2 : 0.1
  const dir = e.deltaY > 0 ? -1 : 1
  updateZoom(Number(editorState.value.zoom || 1) + dir * step, true)
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
      album_ids: selectedAlbumIds.value,
      tags: exportTags.value,
      crop: {
        preset: cropPreset.value,
        width: cropCustomW.value,
        height: cropCustomH.value,
      },
      crop_box: cropPreset.value === 'free' && freeCropBox.value ? normalizeBox(freeCropBox.value) : undefined,
      rotation: editorState.value.rotation,
      zoom: editorState.value.zoom,
      pan: editorState.value.pan,
      adjustments: editorState.value.adjustments,
    }
    if (!payload.crop_box) delete payload.crop_box
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

function startPan(e: PointerEvent) {
  if (e.button !== 0) return
  const rect = viewportRef.value?.getBoundingClientRect()
  if (!rect) return

  const zoom = Math.max(1, Number(editorState.value.zoom) || 1)
  const nx = clamp01Unit((e.clientX - rect.left) / rect.width)
  const ny = clamp01Unit((e.clientY - rect.top) / rect.height)

  if (cropPreset.value === 'free' && zoom <= 1.000001) {
    e.preventDefault()
    selectingCrop.value = true
    selectStartNorm.value = { x: nx, y: ny }
    selectNowNorm.value = { x: nx, y: ny }
    selectBoxNorm.value = { x: nx, y: ny, w: 0.0001, h: 0.0001 }
    ;(e.currentTarget as HTMLElement | null)?.setPointerCapture?.(e.pointerId)
    return
  }

  if (zoom <= 1.000001) return
  e.preventDefault()
  panning.value = true
  panStart.value = { x: e.clientX, y: e.clientY, pan: { ...editorState.value.pan } }
  ;(e.currentTarget as HTMLElement | null)?.setPointerCapture?.(e.pointerId)
}

function onPanMove(e: PointerEvent) {
  const rect = viewportRef.value?.getBoundingClientRect()
  if (!rect) return

  if (selectingCrop.value) {
    const nx = clamp01Unit((e.clientX - rect.left) / rect.width)
    const ny = clamp01Unit((e.clientY - rect.top) / rect.height)
    selectNowNorm.value = { x: nx, y: ny }
    const x0 = selectStartNorm.value.x
    const y0 = selectStartNorm.value.y
    const x1 = nx
    const y1 = ny
    const x = Math.min(x0, x1)
    const y = Math.min(y0, y1)
    const w = Math.abs(x1 - x0)
    const h = Math.abs(y1 - y0)
    selectBoxNorm.value = normalizeBox({ x, y, w, h })
    return
  }

  if (!panning.value) return
  const zoom = Math.max(1, Number(editorState.value.zoom) || 1)
  if (zoom <= 1.000001) return
  const dx = e.clientX - panStart.value.x
  const dy = e.clientY - panStart.value.y
  const denomX = Math.max(1, (zoom - 1) * rect.width)
  const denomY = Math.max(1, (zoom - 1) * rect.height)
  const nextX = panStart.value.pan.x + (dx * 2) / denomX
  const nextY = panStart.value.pan.y + (dy * 2) / denomY
  editorState.value.pan = { x: clamp01(nextX), y: clamp01(nextY) }
}

function endPan() {
  if (selectingCrop.value) {
    selectingCrop.value = false
    const b = selectBoxNorm.value ? normalizeBox(selectBoxNorm.value) : null
    selectBoxNorm.value = null
    if (b && b.w > 0.01 && b.h > 0.01) {
      freeCropBox.value = b
      showOriginal.value = false
      editorState.value.zoom = 1
      editorState.value.pan = { x: 0, y: 0 }
    }
    return
  }
  if (!panning.value) return
  panning.value = false
  pushRotateHistory()
}

onMounted(() => {
  window.addEventListener('resize', updateStageSize)
  window.addEventListener('resize', updateCompareSize)
  fetchAlbums()
  fetchDetail()
  nextTick(() => {
    updateStageSize()
    updateCompareSize()
  })
})
onUnmounted(() => {
  window.removeEventListener('resize', updateStageSize)
  window.removeEventListener('resize', updateCompareSize)
})
watch(previewSrc, () => nextTick(() => {
  updateStageSize()
  updateCompareSize()
}))
watch(activeViewportRatio, () => nextTick(updateCompareSize))
watch(compareMode, () => nextTick(updateCompareSize))

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

let albumRemoteTimer: number | null = null
function remoteAlbumMethod(query: string) {
  if (albumRemoteTimer) window.clearTimeout(albumRemoteTimer)
  albumRemoteTimer = window.setTimeout(() => fetchAlbumsRemote(query), 120)
}
async function fetchAlbumsRemote(keyword: string) {
  loadingAlbums.value = true
  try {
    const res = await axios.get('/api/v1/albums', { params: { page: 1, page_size: 30, keyword: keyword || '' } })
    albumOptions.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '获取相册列表失败')
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
      if (!selectedAlbumIds.value.includes(created.id)) selectedAlbumIds.value.push(created.id)
    }
    ElMessage.success('相册创建成功')
    newAlbumTitle.value = ''
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '创建相册失败')
  }
}

function toggleAlbum(id: number) {
  const idx = selectedAlbumIds.value.indexOf(id)
  if (idx >= 0) selectedAlbumIds.value.splice(idx, 1)
  else selectedAlbumIds.value.push(id)
}
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
        <a v-for="item in links" :key="item.path" :class="{ active: $route.path === item.path || $route.path.startsWith(item.path + '/') }" @click="router.push(item.path)">
          {{ item.icon }} {{ item.label }}
        </a>
      </nav>
    </aside>

    <main>
      <header class="mobile-topbar">
        <button class="icon-btn ghost" @click="toggleNav">☰</button>
        <div class="mobile-brand">
          <span class="logo-mini">✂️</span>
          <span>{{ text('在线编辑', 'Editor') }}</span>
        </div>
        <button class="icon-btn ghost" @click="goDetail">↩️</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">{{ text('在线编辑器', 'Online Editor') }}</div>
          <div class="subtitle">{{ text('支持裁剪 / 旋转 / 色彩调节，灵活对比与导出', 'Crop, rotate, adjust colors, compare and export.') }}</div>
        </div>
        <div class="right">
          <button class="pill-btn ghost" @click="download">{{ text('下载', 'Download') }}</button>
          <button class="pill-btn ghost" @click="restoreOriginal">{{ text('恢复原图', 'Restore') }}</button>
          <button class="pill-btn danger" @click="handleExit">{{ text('退出编辑', 'Exit') }}</button>
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
                <p>{{ text('在线编辑', 'Editor') }}</p>
              </div>
            </div>
            <button class="icon-btn ghost" @click="closeNav">✕</button>
          </div>
          <nav>
            <a v-for="item in links" :key="item.path" :class="{ active: $route.path === item.path || $route.path.startsWith(item.path + '/') }" @click="router.push(item.path)">
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
            <svg class="filter-defs" aria-hidden="true">
              <filter :id="sharpenFilterId" x="-20%" y="-20%" width="140%" height="140%">
                <feConvolveMatrix :kernelMatrix="sharpenKernel" edgeMode="duplicate" />
              </filter>
            </svg>
            <div
              class="image-stage"
              ref="stageRef"
              @mouseleave="showOriginal = false"
              @wheel.prevent="onWheel"
            >
              <div
                class="edit-viewport"
                ref="viewportRef"
                :style="viewportStyle"
                @pointerdown="startPan"
                @pointermove="onPanMove"
                @pointerup="endPan"
                @pointercancel="endPan"
              >
                <div class="edit-surface" :style="stageSurfaceStyle"></div>
                <div v-if="selectionStyle" class="select-rect" :style="selectionStyle"></div>
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
              <div class="compare-viewport" ref="compareEditedRef" :style="compareViewportStyle">
                <div class="edit-surface" :style="compareEditedStyle"></div>
              </div>
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
              <button class="chip-btn" :class="{ active: cropPreset === 'free' }" @click="setCropPreset('free')">自由</button>
              <button class="chip-btn" :class="{ active: cropPreset === '1:1' }" @click="setCropPreset('1:1')">1:1</button>
              <button class="chip-btn" :class="{ active: cropPreset === '4:3' }" @click="setCropPreset('4:3')">4:3</button>
              <button class="chip-btn" :class="{ active: cropPreset === '3:4' }" @click="setCropPreset('3:4')">3:4</button>
              <button class="chip-btn" :class="{ active: cropPreset === '16:9' }" @click="setCropPreset('16:9')">16:9</button>
              <button class="chip-btn" :class="{ active: cropPreset === '9:16' }" @click="setCropPreset('9:16')">9:16</button>
              <button class="chip-btn" :class="{ active: cropPreset === '3:2' }" @click="setCropPreset('3:2')">3:2</button>
              <button class="chip-btn" :class="{ active: cropPreset === '2:3' }" @click="setCropPreset('2:3')">2:3</button>
              <button class="chip-btn" :class="{ active: cropPreset === 'custom' }" @click="setCropPreset('custom')">自定义</button>
            </div>
            <div v-if="cropPreset === 'custom'" class="custom-size">
              <span>宽</span>
              <input class="text-input" type="number" min="1" step="1" v-model.number="cropCustomW" placeholder="W" />
              <span>高</span>
              <input class="text-input" type="number" min="1" step="1" v-model.number="cropCustomH" placeholder="H" />
            </div>
            <div class="module-actions">
              <button class="pill-btn ghost mini" @click="resetCrop">重置裁剪</button>
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
                min="1"
                max="4"
                step="0.01"
                :value="editorState.zoom"
                @input="e => updateZoom(Number((e.target as HTMLInputElement).value))"
                @change="e => updateZoom(Number((e.target as HTMLInputElement).value), true)"
              />
            </div>
            <div class="btn-row">
              <button class="chip-btn ghost" @click="bumpZoom(-0.1)">−</button>
              <button class="chip-btn ghost" @click="bumpZoom(0.1)">+</button>
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
              <label>添加到相册</label>
              <div>
                <el-select
                  v-model="selectedAlbumIds"
                  class="album-select"
                  multiple
                  filterable
                  remote
                  clearable
                  :remote-method="remoteAlbumMethod"
                  :loading="loadingAlbums"
                  placeholder="选择相册（下拉搜索，可多选）"
                >
                  <el-option v-for="album in albumOptions" :key="album.id" :label="album.title" :value="album.id">
                    <span class="tag-option">
                      <span class="dot album-dot"></span>
                      {{ album.title }}
                    </span>
                  </el-option>
                </el-select>
                <div class="album-inline-create">
                  <input class="text-input" v-model="newAlbumTitle" placeholder="新建相册名称" />
                  <button class="pill-btn mini" :disabled="loadingAlbums" @click="createAlbum">+ 新建相册</button>
                </div>
              </div>
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
          </div>

          <div class="control-card">
            <div class="section-title">版本历史</div>
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

.preview-box { position: relative; margin-top: 12px; padding: 12px; background: #fdf6fa; border-radius: 18px; }
.filter-defs { position: absolute; width: 0; height: 0; }
.image-stage { position: relative; border-radius: 16px; background: radial-gradient(circle at 30% 20%, rgba(255, 214, 230, 0.4), rgba(255, 231, 240, 0.95)); height: 520px; display: flex; align-items: center; justify-content: center; overflow: hidden; user-select: none; touch-action: none; cursor: grab; }
.image-stage:active { cursor: grabbing; }
.edit-viewport { position: absolute; border-radius: 14px; overflow: hidden; background: #f6e9f1; box-shadow: inset 0 0 0 1px rgba(255, 180, 205, 0.65); }
.edit-surface { position: absolute; inset: 0; border-radius: inherit; background-color: #f6e9f1; transition: filter 0.12s ease, transform 0.08s ease; will-change: transform, filter, background-position, background-size; }
.select-rect { position: absolute; border: 2px solid rgba(255, 111, 160, 0.95); background: rgba(255, 255, 255, 0.12); border-radius: 12px; pointer-events: none; box-shadow: 0 8px 22px rgba(255, 120, 165, 0.18); }
.main-img { max-width: 100%; max-height: 100%; border-radius: 14px; transition: filter 0.12s ease, transform 0.08s ease; background: #f6e9f1; will-change: transform; }
.crop-guides { position: absolute; inset: 14px; border: 1px dashed transparent; border-radius: 14px; pointer-events: none; }
.crop-guides .area { position: absolute; border: 1px solid rgba(255, 120, 165, 0.8); background: rgba(255, 255, 255, 0.10); border-radius: 10px; pointer-events: none; box-shadow: 0 0 0 9999px rgba(255, 255, 255, 0.06); }
.crop-guides.active { border-color: rgba(255, 157, 184, 0.6); }
.compare-panel { margin-top: 12px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.compare-card { background: #fff8fb; border-radius: 14px; padding: 10px; box-shadow: 0 10px 18px rgba(255, 152, 201, 0.25); }
.compare-card img { width: 100%; border-radius: 10px; object-fit: cover; background: #f9edf3; }
.compare-viewport { position: relative; width: 100%; border-radius: 10px; overflow: hidden; background: #f9edf3; }
.compare-viewport .edit-surface { border-radius: 10px; }
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

.album-select { width: 100%; }
:deep(.album-select .el-select__wrapper) { border-radius: 14px; border: 1px solid rgba(255, 180, 205, 0.9); background: rgba(255, 255, 255, 0.92); box-shadow: none; }
:deep(.album-select .el-select__placeholder) { color: #b57a90; }
.tag-option { display: inline-flex; align-items: center; gap: 8px; }
.album-dot { background: #ff9db8; }

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
.album-checks { display: flex; flex-wrap: wrap; gap: 8px; padding: 6px 0; }
.album-check { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; background: rgba(255, 255, 255, 0.92); border: 1px solid rgba(255, 180, 205, 0.8); color: #b05f7a; cursor: pointer; }
.album-check input { accent-color: #ff6fa0; }
.album-inline-create { margin-top: 8px; display: flex; gap: 8px; align-items: center; }
.album-inline-create input { flex: 1; }
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
