<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

interface TagRecord {
  id: number
  name: string
  color: string
  count: number
  created_at: string
  images: number[]
}

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')
const loading = ref(false)
const filterKeyword = ref('')
const tags = ref<TagRecord[]>([
  { id: 1, name: '自然', color: '#ffb3c8', count: 24, created_at: '2025-11-08', images: [1, 2, 3] },
  { id: 2, name: '旅行', color: '#ff9db8', count: 18, created_at: '2025-11-07', images: [4, 5, 6] },
  { id: 3, name: '美食', color: '#ff86a8', count: 12, created_at: '2025-11-06', images: [7, 8, 9] },
  { id: 4, name: '城市', color: '#ffadc9', count: 15, created_at: '2025-11-05', images: [10, 11] },
  { id: 5, name: '人像', color: '#ff7f9a', count: 8, created_at: '2025-11-04', images: [12] },
  { id: 6, name: '海洋', color: '#8ed0ff', count: 10, created_at: '2025-11-03', images: [13] },
])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const form = ref<{ id?: number; name: string; color: string }>({ name: '', color: '#ff9db8' })

const mergeDialogVisible = ref(false)
const mergeSources = ref<number[]>([])
const mergeTarget = ref<number | null>(null)

const drawerVisible = ref(false)
const activeTag = ref<TagRecord | null>(null)

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

const filteredTags = computed(() =>
  tags.value.filter(t => t.name.toLowerCase().includes(filterKeyword.value.trim().toLowerCase()))
)
const totalImages = computed(() => tags.value.reduce((sum, t) => sum + t.count, 0))
const chartBars = computed(() => {
  const max = Math.max(...tags.value.map(t => t.count), 1)
  return tags.value.map(t => ({ ...t, height: Math.max(24, (t.count / max) * 120) }))
})
const wordCloud = computed(() =>
  tags.value.map(t => ({ ...t, size: 12 + Math.min(14, t.count) }))
)

function openCreate() {
  dialogMode.value = 'create'
  form.value = { name: '', color: '#ff9db8' }
  dialogVisible.value = true
}
function openEdit(tag: TagRecord) {
  dialogMode.value = 'edit'
  form.value = { id: tag.id, name: tag.name, color: tag.color }
  dialogVisible.value = true
}
function saveTag() {
  const name = form.value.name.trim()
  if (!name) {
    ElMessage.warning('请输入标签名称')
    return
  }
  if (dialogMode.value === 'create') {
    const id = Date.now()
    tags.value.unshift({ id, name, color: form.value.color, count: 0, created_at: new Date().toISOString().slice(0, 10), images: [] })
  } else if (form.value.id) {
    const idx = tags.value.findIndex(t => t.id === form.value.id)
    if (idx >= 0) tags.value[idx] = { ...tags.value[idx], name, color: form.value.color }
  }
  dialogVisible.value = false
  ElMessage.success(dialogMode.value === 'create' ? '已创建标签' : '已更新标签')
}
function confirmDelete(tag: TagRecord) {
  ElMessageBox.confirm(`确定删除标签「${tag.name}」吗？该标签下的图片不会被删除。`, '删除标签', { type: 'warning' })
    .then(() => {
      tags.value = tags.value.filter(t => t.id !== tag.id)
      ElMessage.success('已删除')
    })
    .catch(() => {})
}
function openMerge() {
  mergeSources.value = []
  mergeTarget.value = null
  mergeDialogVisible.value = true
}
function submitMerge() {
  if (!mergeTarget.value || mergeSources.value.length === 0) {
    ElMessage.warning('请选择要合并的来源标签')
    return
  }
  if (mergeSources.value.includes(mergeTarget.value)) {
    ElMessage.warning('目标标签不能与来源相同')
    return
  }
  const target = tags.value.find(t => t.id === mergeTarget.value)
  if (!target) return
  let mergedCount = target.count
  mergeSources.value.forEach(id => {
    const tag = tags.value.find(t => t.id === id)
    if (tag) mergedCount += tag.count
  })
  tags.value = tags.value.filter(t => !mergeSources.value.includes(t.id) || t.id === target.id)
  tags.value = tags.value.map(t => (t.id === target.id ? { ...t, count: mergedCount } : t))
  mergeDialogVisible.value = false
  ElMessage.success('合并完成')
}
function openDrawer(tag: TagRecord) {
  activeTag.value = tag
  drawerVisible.value = true
}

// 后端接口替换占位：若提供 /api/v1/tags 列表，可替换此函数加载真实数据
async function fetchFromServer() {
  try {
    loading.value = true
    const res = await axios.get('/api/v1/tags')
    tags.value = res.data.items || tags.value
  } catch (err) {
    // 保留本地 mock，便于先行联调 UI
  } finally {
    loading.value = false
  }
}

onMounted(fetchFromServer)
</script>

<template>
  <div class="dashboard">
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
          <div class="title">标签管理中心</div>
          <div class="subtitle">自定义分类标签，可编辑/删除/合并，和 EXIF / AI 标签分开管理</div>
        </div>
        <div class="right">
          <span class="welcome">欢迎，{{ username }}</span>
          <button class="ghost-btn" @click="openMerge">⤵ 合并标签</button>
          <button class="primary-btn" @click="openCreate">＋ 新建标签</button>
        </div>
      </header>

      <section class="stats-row">
        <div class="stat-card">
          <div class="label">标签总数</div>
          <div class="num">{{ tags.length }}</div>
          <div class="hint">仅自定义分类标签，不含 EXIF / AI 标签</div>
        </div>
        <div class="stat-card">
          <div class="label">关联图片</div>
          <div class="num">{{ totalImages }}</div>
          <div class="hint">用于检索和过滤的图片数量</div>
        </div>
        <div class="chart-card">
          <div class="chart-title">标签分布（示例柱状）</div>
          <div class="chart-grid">
            <div v-for="bar in chartBars" :key="bar.id" class="bar" :style="{ height: bar.height + 'px', background: bar.color }">
              <span class="bar-count">{{ bar.count }}</span>
            </div>
          </div>
          <div class="chart-legend">
            <span v-for="bar in chartBars" :key="bar.id" class="legend-pill" :style="{ background: bar.color }">{{ bar.name }}</span>
          </div>
        </div>
        <div class="cloud-card">
          <div class="chart-title">词云（示意）</div>
          <div class="cloud">
            <span v-for="tag in wordCloud" :key="tag.id" :style="{ color: tag.color, fontSize: tag.size + 'px' }">{{ tag.name }}</span>
          </div>
        </div>
      </section>

      <section class="table-card">
        <div class="table-head">
          <div class="title">标签列表</div>
          <div class="actions">
            <input v-model="filterKeyword" placeholder="搜索标签名称…" />
            <button class="ghost-btn" @click="openMerge">合并</button>
            <button class="primary-btn" @click="openCreate">新建</button>
          </div>
        </div>

        <div class="table">
          <div class="row header">
            <span>标签名称</span>
            <span>颜色</span>
            <span>图片数量</span>
            <span>创建时间</span>
            <span>操作</span>
          </div>
          <div v-for="tag in filteredTags" :key="tag.id" class="row">
            <span class="name">{{ tag.name }}</span>
            <span class="color-cell">
              <span class="color-dot" :style="{ background: tag.color }"></span>
              <span class="pill" :style="{ background: tag.color + '22', color: '#b05f7a' }">{{ tag.name }}</span>
            </span>
            <span>{{ tag.count }} 张</span>
            <span class="muted">{{ tag.created_at }}</span>
            <span class="ops">
              <a @click="openDrawer(tag)">查看图片</a>
              <a @click="openEdit(tag)">编辑</a>
              <a class="danger" @click="confirmDelete(tag)">删除</a>
            </span>
          </div>
        </div>
      </section>

      <footer>2025 Designed by hyk · 标签管理</footer>
    </main>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新建标签' : '编辑标签'" width="360px">
      <div class="form">
        <label>名称</label>
        <el-input v-model="form.name" placeholder="请输入标签名称" />
        <label style="margin-top: 8px">颜色</label>
        <el-color-picker v-model="form.color" show-alpha />
      </div>
      <template #footer>
        <button class="ghost-btn" @click="dialogVisible = false">取消</button>
        <button class="primary-btn" @click="saveTag">保存</button>
      </template>
    </el-dialog>

    <el-dialog v-model="mergeDialogVisible" title="合并标签" width="420px">
      <div class="merge-grid">
        <div>
          <label>来源标签（可多选）</label>
          <el-select v-model="mergeSources" multiple placeholder="选择要合并的标签">
            <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </div>
        <div>
          <label>目标标签</label>
          <el-select v-model="mergeTarget" placeholder="选择合并到的标签">
            <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </div>
      </div>
      <template #footer>
        <button class="ghost-btn" @click="mergeDialogVisible = false">取消</button>
        <button class="primary-btn" @click="submitMerge">开始合并</button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawerVisible" :title="`包含 ${activeTag?.name || ''} 的图片`" size="40%">
      <div v-if="activeTag" class="drawer-list">
        <div v-if="activeTag.images.length === 0" class="muted">暂无图片</div>
        <div v-for="imgId in activeTag.images" :key="imgId" class="thumb">
          <div class="thumb-inner">ID {{ imgId }}</div>
        </div>
      </div>
    </el-drawer>
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
main { flex: 1; display: flex; flex-direction: column; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.92); }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; }
.welcome { font-size: 13px; color: #8c546e; }
.primary-btn, .ghost-btn { border: none; border-radius: 999px; padding: 8px 14px; cursor: pointer; font-size: 13px; }
.primary-btn { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.ghost-btn { background: #ffeef5; color: #b05f7a; border: 1px solid rgba(255, 180, 205, 0.7); }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; padding: 16px 20px 4px; }
.stat-card, .chart-card, .cloud-card { background: rgba(255, 255, 255, 0.94); border-radius: 18px; padding: 14px 16px; box-shadow: 0 10px 22px rgba(255, 165, 199, 0.2); }
.stat-card .label { color: #a35d76; font-size: 12px; }
.stat-card .num { font-size: 26px; color: #ff4c8a; font-weight: 700; }
.hint { color: #b6788d; font-size: 12px; }
.chart-card { grid-column: span 2; }
.chart-title { font-size: 13px; color: #a35d76; margin-bottom: 8px; }
.chart-grid { display: flex; align-items: flex-end; gap: 8px; height: 160px; padding: 6px 4px; background: #fff7fb; border-radius: 14px; }
.bar { flex: 1; border-radius: 10px 10px 4px 4px; position: relative; box-shadow: 0 6px 12px rgba(255, 168, 190, 0.35); }
.bar-count { position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #b05f7a; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.legend-pill { padding: 4px 10px; border-radius: 999px; font-size: 12px; color: #5a2f3d; background: #ffeef5; }
.cloud-card .cloud { display: flex; flex-wrap: wrap; gap: 10px; padding: 10px; background: #fff7fb; border-radius: 12px; min-height: 80px; }
.table-card { margin: 8px 20px 10px; background: rgba(255, 255, 255, 0.95); border-radius: 18px; box-shadow: 0 12px 24px rgba(255, 165, 199, 0.3); padding: 12px 12px 4px; }
.table-head { display: flex; justify-content: space-between; align-items: center; padding: 0 6px 6px; }
.table-head .title { font-weight: 600; color: #ff4c8a; }
.table-head input { border-radius: 12px; border: 1px solid rgba(255, 190, 210, 0.8); padding: 6px 10px; font-size: 13px; outline: none; }
.table { width: 100%; }
.row { display: grid; grid-template-columns: 1.2fr 1fr 1fr 1fr 1fr; align-items: center; padding: 10px 8px; border-bottom: 1px solid #ffe6ef; font-size: 13px; }
.row.header { font-weight: 600; color: #8c546e; background: #fff7fb; border-radius: 12px; }
.name { color: #613448; }
.color-cell { display: flex; align-items: center; gap: 8px; }
.color-dot { width: 16px; height: 16px; border-radius: 6px; border: 1px solid rgba(0,0,0,0.05); }
.pill { padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.ops a { margin-right: 8px; color: #ff4c8a; cursor: pointer; }
.ops a.danger { color: #d95959; }
.muted { color: #b57a90; }
footer { text-align: center; font-size: 12px; color: #b57a90; padding: 10px 0 16px; }
.form label { display: block; font-size: 12px; color: #a35d76; margin: 6px 0 2px; }
.merge-grid { display: flex; flex-direction: column; gap: 12px; }
.drawer-list { display: flex; flex-wrap: wrap; gap: 10px; }
.thumb { width: 80px; height: 80px; border-radius: 12px; background: #ffeef5; display: flex; align-items: center; justify-content: center; color: #a35d76; }
@media (max-width: 1200px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .chart-card { grid-column: span 2; } }
@media (max-width: 900px) { .sidebar { display: none; } .stats-row { grid-template-columns: 1fr; } .row { grid-template-columns: 1fr 1fr 1fr 1fr; grid-auto-rows: auto; } }
</style>
