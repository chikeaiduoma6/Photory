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
const aiLoading = ref(false)
const aiTags = ref<string[]>([])
const aiDescription = ref('这里是 AI 生成的图片描述，点击按钮可更新～')
const newTag = ref('')
const newTagColor = ref(palette[0])

const navOpen = ref(false)
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
watch(() => router.currentRoute.value.fullPath, () => closeNav())

const tokenParam = computed(() => (authStore.token ? `?jwt=${authStore.token}` : ''))
const versionStamp = computed(() => (detail.value?.updated_at ? `&v=${encodeURIComponent(detail.value.updated_at)}` : ''))
const imageUrl = computed(() =>
  detail.value ? withBase(`${detail.value.raw_url}${tokenParam.value}${versionStamp.value}`) : ''
)
const thumbUrl = computed(() =>
  detail.value ? withBase(`${detail.value.thumb_url || detail.value.raw_url}${tokenParam.value}${versionStamp.value}`) : ''
)
const heroUrl = computed(() => imageUrl.value || thumbUrl.value)
const customTags = computed(() => detail.value?.tag_objects || [])
const exifTags = computed(() => {
  if (!detail.value) return []
  const exif = detail.value.exif_tags || []
  const wh = detail.value.width && detail.value.height ? [`${detail.value.width}x${detail.value.height}`] : []
  const arr = [...exif, ...wh].filter(Boolean).map((v: string) => String(v))
  return Array.from(new Set(arr))
})
const historyList = computed(() => detail.value?.version_history || [])

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
function go(path: string) { router.push(path); closeNav() }
function isActive(path: string) { return currentPath.value === path || currentPath.value.startsWith(path + '/') }

function fallbackToRaw(event: Event) {
  const img = event.target as HTMLImageElement | null
  const raw = imageUrl.value
  if (img && raw && img.src !== raw) img.src = raw
}

async function fetchDetail() {
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/images/${route.params.id}`)
    detail.value = res.data
    aiTags.value = res.data.ai_tags || []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '获取图片详情失败')
    router.push('/')
  } finally {
    loading.value = false
  }
}

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

async function addTag() {
  const tag = newTag.value.trim()
  if (!tag) return
  try {
    const res = await axios.post(`/api/v1/images/${route.params.id}/tags`, {
      tags: [...(customTags.value || []), { name: tag, color: newTagColor.value }],
    })
    detail.value.tags = res.data.tags
    detail.value.tag_objects = res.data.tag_objects || []
    newTag.value = ''
    newTagColor.value = palette[Math.floor(Math.random() * palette.length)]
    ElMessage.success('标签已更新')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '添加标签失败')
  }
}

function removeTag(t: string) {
  const left = (customTags.value || []).filter((x: any) => x.name !== t).map((x: any) => x.name)
  axios
    .post(`/api/v1/images/${route.params.id}/tags`, { tags: left })
    .then(res => {
      detail.value.tags = res.data.tags
      detail.value.tag_objects = res.data.tag_objects || []
    })
    .catch(() => ElMessage.error('更新标签失败'))
}

function formatDate(d?: string) {
  if (!d) return '--'
  return d.replace('T', ' ').slice(0, 16)
}
function formatSize(size?: number) {
  if (!size) return '--'
  const mb = size / 1024 / 1024
  return `${mb.toFixed(2)} MB`
}

function generateAiTags() {
  aiLoading.value = true
  setTimeout(() => {
    const base = ['风景', '人物', '动物', '海洋', '城市', '夜景', '花卉', '旅行', '日常']
    aiTags.value = base.sort(() => 0.5 - Math.random()).slice(0, 3)
    aiDescription.value = 'AI 生成：根据图像内容给出的标签与简短描述，后端接入模型后可替换为真实结果。'
    aiLoading.value = false
  }, 800)
}

function goBack() { router.back() }
function logout() { authStore.logout(); router.push('/auth/login') }
function goEdit() { router.push(`/images/${route.params.id}/edit`) }
function download() { if (imageUrl.value) window.open(imageUrl.value, '_blank') }

function confirmPink(title: string, text: string) {
  return ElMessageBox.confirm(text, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
    customClass: 'pink-confirm',
  })
}
async function softDelete() {
  try {
    await confirmPink('删除图片', '确定将此图片移入回收站吗？')
    await axios.post(`/api/v1/images/${route.params.id}/trash`)
    ElMessage.success('已移入回收站')
    router.push('/recycle')
  } catch {
    /* cancelled/failed */
  }
}

onMounted(fetchDetail)
</script>

<template>
  <div class="dashboard" v-if="detail">
    <aside class="sidebar">
      <div class="logo">
        <div class="icon">📸</div>
        <div class="text">
          <h1>Photory</h1>
          <p>记录世间每一份美好，让瞬间永恒～</p>
        </div>
      </div>

      <nav>
        <a
          v-for="item in links"
          :key="item.path"
          :class="{ active: isActive(item.path) }"
          @click="go(item.path)"
        >
          {{ item.icon }} {{ item.label }}
        </a>
      </nav>
    </aside>

    <main>
      <header class="mobile-topbar">
        <button class="icon-btn ghost" @click="toggleNav">☰</button>
        <div class="mobile-brand">
          <span class="logo-mini">📷</span>
          <span>{{ detail.name || detail.original_name || '图片详情' }}</span>
        </div>
        <button class="icon-btn ghost" @click="goBack">↩️</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">{{ detail.name || detail.original_name }}</div>
          <div class="subtitle">来自 {{ detail.folder || '默认图库' }} · {{ formatDate(detail.created_at) }}</div>
        </div>
        <div class="right">
          <button class="pill-btn ghost" @click="goBack">返回</button>
          <button class="pill-btn ghost" @click="goEdit">在线编辑</button>
          <button class="pill-btn ghost" @click="go('/tags')">标签管理</button>
          <button class="pill-btn danger" @click="softDelete">删除到回收站</button>
          <button class="pill-btn ghost" :disabled="!imageUrl" @click="download">下载</button>
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
                <p>随时随地 · 图片详情</p>
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

      <section class="detail-layout">
        <div class="image-card">
          <img :src="heroUrl" :alt="detail.name" class="hero-img" @error="fallbackToRaw" />

          <div class="image-actions">
            <span>{{ formatSize(detail.size) }}</span>
            <span>{{ detail.width }} × {{ detail.height }}</span>
            <span>{{ detail.visibility === 'public' ? '公开' : '私密' }}</span>
          </div>

          <div class="mobile-actions">
            <button class="pill-btn ghost" @click="goEdit">在线编辑</button>
            <button class="pill-btn ghost" @click="download" :disabled="!imageUrl">下载</button>
            <button class="pill-btn danger" @click="softDelete">删除</button>
          </div>
        </div>

        <div class="info-panel">
          <div class="panel">
            <h3>基本信息</h3>
            <div class="field"><label>标题</label><div class="value">{{ detail.name }}</div></div>
            <div class="field"><label>描述</label><div class="value muted">（预留描述，后续可编辑）</div></div>

            <div class="field tags">
              <label>自定义标签</label>
              <div class="tag-list">
                <span
                  v-for="(t, idx) in customTags"
                  :key="t.id || t.name"
                  class="tag"
                  :style="{ background: (t.color || '') + '22', color: '#b05f7a', borderColor: t.color || '#ff9db8' }"
                  @click="removeTag(t.name)"
                >
                  <span class="dot" :style="{ background: normalizeColor(t.color, idx, t.name) }"></span>{{ t.name }} ×
                </span>
                <span v-if="!customTags?.length" class="muted">暂无自定义标签</span>
              </div>
              <div class="tag-input">
                <input v-model="newTag" placeholder="输入新标签后回车" @keyup.enter="addTag" />
                <input v-model="newTagColor" type="color" class="color-picker" />
                <button class="pill-btn mini" @click="addTag">添加</button>
              </div>
            </div>

            <div class="field tags">
              <label>EXIF 标签</label>
              <div class="tag-list readonly">
                <span v-for="t in exifTags" :key="t" class="tag ghost">{{ t }}</span>
                <span v-if="!exifTags.length" class="muted">暂无 EXIF 标签</span>
              </div>
            </div>

            <div class="field tags">
              <label>AI 标签</label>
              <div class="tag-list">
                <span v-for="t in aiTags" :key="t" class="tag alt">{{ t }}</span>
                <span v-if="!aiTags.length" class="muted">暂无 AI 标签</span>
              </div>
              <div class="value">{{ aiDescription }}</div>
              <button class="pill-btn mini" :disabled="aiLoading" @click="generateAiTags">
                {{ aiLoading ? '生成中...' : '更新 AI 分析' }}
              </button>
            </div>

            <div class="field">
              <label>可见性</label>
              <span class="chip" :class="detail.visibility === 'public' ? 'primary' : 'muted'">
                {{ detail.visibility === 'public' ? '公开' : '私密' }}
              </span>
            </div>
          </div>

          <div class="panel">
            <h3>版本历史</h3>
            <div v-if="!historyList.length" class="muted">暂无历史版本（未曾覆盖保存）</div>
            <div v-else class="version-list">
              <div v-for="(v, idx) in historyList" :key="idx" class="version-item">
                <div class="dot"></div>
                <div class="v-body">
                  <div class="v-title">{{ v.name }}</div>
                  <div class="v-note">{{ v.note || '历史版本' }}</div>
                </div>
                <span class="v-time">{{ formatDate(v.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
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
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.9); gap: 10px; }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.topbar .subtitle { font-size: 12px; color: #a36e84; }
.topbar .right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn:hover { background: #ffd6e5; }
.icon-btn.ghost { background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(255, 190, 210, 0.7); }
.pill-btn { border: none; border-radius: 999px; padding: 8px 14px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 13px; cursor: pointer; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.pill-btn.ghost { background: #ffeef5; color: #b05f7a; box-shadow: none; border: 1px solid rgba(255, 180, 205, 0.7); }
.pill-btn.danger { background: linear-gradient(135deg, #ff9c9c, #ff6b6b); }
.pill-btn.mini { padding: 6px 12px; font-size: 12px; }
.pill-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.detail-layout { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; padding: 16px 20px 10px; }
.image-card { background: #fff; border-radius: 22px; padding: 16px; box-shadow: 0 12px 28px rgba(255, 165, 199, 0.25); display: flex; flex-direction: column; gap: 10px; }
.hero-img { width: 100%; border-radius: 18px; object-fit: contain; background: #f9f1f6; max-height: 72vh; }
.image-actions { display: flex; gap: 10px; font-size: 12px; color: #a35d76; flex-wrap: wrap; }
.mobile-actions { display: none; gap: 8px; flex-wrap: wrap; }

.info-panel { display: flex; flex-direction: column; gap: 12px; }
.panel { background: rgba(255, 255, 255, 0.92); border-radius: 20px; padding: 14px 16px; box-shadow: 0 10px 22px rgba(255, 165, 199, 0.2); }
.panel h3 { margin: 0 0 10px; color: #ff4c8a; }
.field { margin-bottom: 10px; }
.field label { font-size: 12px; color: #a35d76; display: block; margin-bottom: 4px; }
.value { font-size: 14px; color: #4b4b4b; }
.muted { color: #b57a90; font-size: 13px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { border-radius: 999px; padding: 4px 10px; font-size: 12px; color: #b05f7a; cursor: pointer; border: 1px solid transparent; display: inline-flex; align-items: center; gap: 6px; }
.tag.alt { background: #ffeef5; }
.tag.ghost { background: #f4f4f4; color: #7a7a7a; cursor: default; border: none; }
.tag .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.tag-input { display: flex; gap: 8px; margin-top: 6px; align-items: center; }
.tag-input input { flex: 1; border-radius: 12px; border: 1px solid rgba(255, 190, 210, 0.9); padding: 6px 10px; font-size: 13px; outline: none; }
.color-picker { width: 44px; height: 32px; padding: 0; border: 1px solid rgba(255, 190, 210, 0.9); border-radius: 8px; background: #fff; }
.chip { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 12px; background: #ffeef5; color: #b05f7a; }
.chip.primary { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }

.version-list { display: flex; flex-direction: column; gap: 8px; }
.version-item { display: flex; align-items: center; gap: 10px; background: #fff5f8; border-radius: 10px; padding: 8px 10px; }
.version-item .dot { width: 10px; height: 10px; border-radius: 50%; background: #7ac7ff; }
.v-body { flex: 1; }
.v-title { font-size: 13px; color: #613448; }
.v-note { font-size: 12px; color: #b57a90; }
.v-time { font-size: 12px; color: #b57a90; }

footer { text-align: center; font-size: 12px; color: #b57a90; padding: 12px 0 16px; }
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

@media (max-width: 1100px) { .detail-layout { grid-template-columns: 1fr; } }
@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .topbar .right { display: none; }
  .detail-layout { padding-inline: 12px; }
  .hero-img { max-height: 60vh; }
  .image-actions { font-size: 12px; }
  .mobile-actions { display: flex; }
}
@media (max-width: 640px) {
  .tag-input { flex-direction: column; align-items: stretch; }
  .tag-input input { width: 100%; }
  .color-picker { width: 100%; max-width: 120px; }
  .panel { padding: 12px; }
}
</style>
