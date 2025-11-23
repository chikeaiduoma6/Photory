<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const detail = ref<any>(null)
const loading = ref(true)
const aiLoading = ref(false)
const aiTags = ref<string[]>([])
const aiDescription = ref('这里是一个 AI 生成的图片描述，点击按钮可更新～')
const newTag = ref('')

const tokenParam = computed(() => (authStore.token ? `?jwt=${authStore.token}` : ''))
const imageUrl = computed(() => (detail.value ? `${detail.value.raw_url}${tokenParam.value}` : ''))
const thumbUrl = computed(() => (detail.value ? `${detail.value.thumb_url || detail.value.raw_url}${tokenParam.value}` : ''))
const heroUrl = computed(() => imageUrl.value || thumbUrl.value)
const exifTags = computed(() => {
  if (!detail.value) return []
  const arr = [detail.value.camera, detail.value.lens, detail.value.iso, detail.value.aperture, detail.value.exposure]
    .filter(Boolean)
    .map((v: string) => String(v))
  return Array.from(new Set(arr))
})

const links = [
  { label: '首页', icon: '🏠', path: '/' },
  { label: '上传中心', icon: '☁️', path: '/upload' },
  { label: '标签', icon: '🏷️', path: '/tags' },
  { label: '文件夹', icon: '📁', path: '/folders' },
  { label: '相册', icon: '📚', path: '/albums' },
  { label: '智能分类', icon: '🧠', path: '/smart' },
  { label: 'AI工作台', icon: '🤖', path: '/ai' },
  { label: '任务中心', icon: '🧾', path: '/tasks' },
  { label: '回收站', icon: '🗑️', path: '/recycle' },
  { label: '设置', icon: '⚙️', path: '/settings' },
]
const currentPath = computed(() => router.currentRoute.value.path)
function go(path: string) { router.push(path) }
function isActive(path: string) { return currentPath.value === path || currentPath.value.startsWith(path + '/') }

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

async function addTag() {
  const tag = newTag.value.trim()
  if (!tag) return
  try {
    const res = await axios.post(`/api/v1/images/${route.params.id}/tags`, {
      tags: [...(detail.value?.tags || []), tag],
    })
    detail.value.tags = res.data.tags
    newTag.value = ''
    ElMessage.success('标签已更新')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '添加标签失败')
  }
}

function removeTag(t: string) {
  const left = (detail.value?.tags || []).filter((x: string) => x !== t)
  axios
    .post(`/api/v1/images/${route.params.id}/tags`, { tags: left })
    .then(res => { detail.value.tags = res.data.tags })
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

function confirmPink(title: string, text: string) {
  return ElMessageBox.confirm(text, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
    customClass: 'pink-confirm',
  })
}
function softDelete() {
  confirmPink('删除图片', '确定将此图片移入回收站吗？').then(() => {
    ElMessage.success('已移入回收站（请接通后端接口实际执行）')
    router.push('/recycle')
  }).catch(() => {})
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
      <header class="topbar">
        <div class="left">
          <div class="title">{{ detail.name || detail.original_name }}</div>
          <div class="subtitle">来自 {{ detail.folder || '默认图库' }} · {{ formatDate(detail.created_at) }}</div>
        </div>
        <div class="right">
          <button class="pill-btn ghost" @click="goBack">返回</button>
          <button class="pill-btn ghost" @click="go('/tags')">标签管理</button>
          <button class="pill-btn" @click="softDelete">删除到回收站</button>
          <button class="pill-btn ghost" :disabled="!imageUrl" @click="() => imageUrl && window.open(imageUrl, '_blank')">下载</button>
          <button class="icon-btn" title="退出登录" @click="logout">🚪</button>
        </div>
      </header>

      <section class="detail-layout">
        <div class="image-card">
          <img :src="heroUrl" :alt="detail.name" class="hero-img" />
          <div class="image-actions">
            <span>{{ formatSize(detail.size) }}</span>
            <span>{{ detail.width }} × {{ detail.height }}</span>
            <span>{{ detail.visibility === 'public' ? '公开' : '私密' }}</span>
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
                <span v-for="t in detail.tags" :key="t" class="tag" @click="removeTag(t)">{{ t }} ×</span>
                <span v-if="!detail.tags?.length" class="muted">暂无自定义标签</span>
              </div>
              <div class="tag-input">
                <input v-model="newTag" placeholder="输入新标签后回车" @keyup.enter="addTag" />
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
                {{ aiLoading ? '生成中…' : '更新 AI 分析' }}
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
            <h3>EXIF 信息</h3>
            <div class="exif-grid">
              <div><label>相机</label><div>{{ detail.camera || '--' }}</div></div>
              <div><label>镜头</label><div>{{ detail.lens || '--' }}</div></div>
              <div><label>光圈</label><div>{{ detail.aperture || '--' }}</div></div>
              <div><label>快门</label><div>{{ detail.exposure || '--' }}</div></div>
              <div><label>ISO</label><div>{{ detail.iso || '--' }}</div></div>
              <div><label>焦距</label><div>{{ detail.focal || '--' }}</div></div>
              <div><label>拍摄时间</label><div>{{ formatDate(detail.taken_at) }}</div></div>
              <div><label>分辨率</label><div>{{ detail.width }} × {{ detail.height }}</div></div>
              <div><label>纬度</label><div>{{ detail.latitude ?? '--' }}</div></div>
              <div><label>经度</label><div>{{ detail.longitude ?? '--' }}</div></div>
            </div>
          </div>

          <div class="panel">
            <h3>版本历史</h3>
            <div class="history-card">
              <img :src="thumbUrl || imageUrl" alt="thumb" />
              <div>
                <div class="value">{{ detail.name }}</div>
                <div class="muted">{{ formatDate(detail.created_at) }}</div>
              </div>
              <span class="chip primary">当前</span>
            </div>
          </div>
        </div>
      </section>

      <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
    </main>
  </div>

  <div v-else class="loading">加载中…</div>
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

main { flex: 1; display: flex; flex-direction: column; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.9); }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.topbar .subtitle { font-size: 12px; color: #a36e84; }
.topbar .right { display: flex; align-items: center; gap: 10px; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn:hover { background: #ffd6e5; }
.pill-btn { border: none; border-radius: 999px; padding: 8px 14px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-size: 13px; cursor: pointer; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.pill-btn.ghost { background: #ffeef5; color: #b05f7a; box-shadow: none; border: 1px solid rgba(255, 180, 205, 0.7); }
.pill-btn.mini { padding: 6px 12px; font-size: 12px; }
.pill-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.detail-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; padding: 16px 20px 10px; }
.image-card { background: #fff; border-radius: 22px; padding: 16px; box-shadow: 0 12px 28px rgba(255, 165, 199, 0.25); display: flex; flex-direction: column; gap: 10px; }
.hero-img { width: 100%; border-radius: 18px; object-fit: contain; background: #f9f1f6; max-height: 68vh; }
.image-actions { display: flex; gap: 10px; font-size: 12px; color: #a35d76; }
.info-panel { display: flex; flex-direction: column; gap: 12px; }
.panel { background: rgba(255, 255, 255, 0.92); border-radius: 20px; padding: 14px 16px; box-shadow: 0 10px 22px rgba(255, 165, 199, 0.2); }
.panel h3 { margin: 0 0 10px; color: #ff4c8a; }
.field { margin-bottom: 10px; }
.field label { font-size: 12px; color: #a35d76; display: block; margin-bottom: 4px; }
.value { font-size: 14px; color: #4b4b4b; }
.muted { color: #b57a90; font-size: 13px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { background: #ffe4f0; border-radius: 999px; padding: 4px 10px; font-size: 12px; color: #b05f7a; cursor: pointer; }
.tag.alt { background: #ffeef5; }
.tag.ghost { background: #f4f4f4; color: #7a7a7a; cursor: default; }
.tag-input { display: flex; gap: 8px; margin-top: 6px; }
.tag-input input { flex: 1; border-radius: 12px; border: 1px solid rgba(255, 190, 210, 0.9); padding: 6px 10px; font-size: 13px; outline: none; }
.chip { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 12px; background: #ffeef5; color: #b05f7a; }
.chip.primary { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
.exif-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 12px; }
.exif-grid label { font-size: 12px; color: #a35d76; }
.history-card { display: flex; align-items: center; gap: 10px; background: #fff4f8; border-radius: 14px; padding: 10px; }
.history-card img { width: 56px; height: 56px; object-fit: cover; border-radius: 10px; }
footer { text-align: center; font-size: 12px; color: #b57a90; padding: 12px 0 16px; }
.loading { display: flex; align-items: center; justify-content: center; height: 100vh; color: #a35d76; }
:deep(.pink-confirm .el-message-box__title) { color: #ff4c8a; }
:deep(.pink-confirm .el-button--primary) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); border: none; }
:deep(.pink-confirm .el-button--default) { border-color: #ffb6cf; color: #b05f7a; }
@media (max-width: 1100px) { .detail-layout { grid-template-columns: 1fr; } }
</style>
