<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'

interface TagRecord {
  id: number
  name: string
  color: string
  count: number
  created_at: string
}

interface Summary {
  total_tags: number
  total_images: number
  distribution: TagRecord[]
  word_cloud: Array<TagRecord & { size?: number }>
}

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const palette = ['#ff9db8', '#8ed0ff', '#ffd27f', '#9dd0a5', '#c3a0ff', '#f7a3ff']

const loading = ref(false)
const saving = ref(false)
const filterKeyword = ref('')
const chartMode = ref<'bar' | 'pie'>('bar')
const page = ref(1)
const pageSize = 6
const total = ref(0)
const tags = ref<TagRecord[]>([])
const summary = ref<Summary>({ total_tags: 0, total_images: 0, distribution: [], word_cloud: [] })
const selectedIds = ref<number[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const form = ref<{ id?: number; name: string; color: string }>({ name: '', color: '#ff9db8' })

const mergeDialogVisible = ref(false)
const mergeSources = ref<number[]>([])
const mergeTarget = ref<number | null>(null)

const preferencesStore = usePreferencesStore()
const links = computed(() => getNavLinks(preferencesStore.language))

const currentPath = computed(() => router.currentRoute.value.path)
function go(path: string) { router.push(path); navOpen.value = false }
function isActive(path: string) { return currentPath.value === path || currentPath.value.startsWith(path + '/') }
const navOpen = ref(false)
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
watch(() => router.currentRoute.value.fullPath, () => closeNav())

function normalizeColor(raw?: string | null, idx = 0, name = '') {
  if (!raw) {
    const code = name ? [...name].reduce((s, c) => s + c.charCodeAt(0), idx) : idx
    return palette[code % palette.length]
  }
  const val = raw.trim()
  const hex = val.match(/^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$/)
  if (hex) return `#${hex[1]}`
  const rgba = val.match(/^rgba?\((\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})(?:,\s*[\d.]+)?\)$/)
  if (rgba) {
    const [r, g, b] = rgba.slice(1, 4).map(n => Math.max(0, Math.min(255, Number(n))))
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
  }
  const code = name ? [...name].reduce((s, c) => s + c.charCodeAt(0), idx) : idx
  return palette[code % palette.length]
}

const listView = computed(() =>
  tags.value.map((t, i) => ({ ...t, color: normalizeColor(t.color, i, t.name) }))
)
const chartData = computed(() =>
  summary.value.distribution.map((t, i) => ({ ...t, color: normalizeColor(t.color, i, t.name) }))
)
const wordCloud = computed(() => {
  const src = summary.value.word_cloud.length ? summary.value.word_cloud : summary.value.distribution
  const maxCount = Math.max(...src.map(t => t.count || 0), 1)
  return src.map((t, i) => ({
    ...t,
    color: normalizeColor(t.color, i, t.name),
    size: 14 + Math.round(((t.count || 0) / maxCount) * 18),
  }))
})
const barMax = computed(() => Math.max(...chartData.value.map(t => t.count || 0), 1))
const allSelected = computed(() => listView.value.length > 0 && selectedIds.value.length === listView.value.length)

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  return dateStr.slice(0, 10)
}

async function loadTags() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/tags', {
      params: { page: page.value, page_size: pageSize, keyword: filterKeyword.value.trim() },
    })
    tags.value = res.data.items || []
    total.value = res.data.total || 0
    selectedIds.value = []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '获取标签失败')
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const res = await axios.get('/api/v1/tags/summary')
    summary.value = res.data || summary.value
  } catch {
    /* ignore */
  }
}

function handleSearch() {
  page.value = 1
  loadTags()
  loadSummary()
}

function openCreate() {
  dialogMode.value = 'create'
  form.value = { name: '', color: '#ff9db8' }
  dialogVisible.value = true
}
function openEdit(tag: TagRecord) {
  dialogMode.value = 'edit'
  form.value = { id: tag.id, name: tag.name, color: tag.color || '#ff9db8' }
  dialogVisible.value = true
}

async function saveTag() {
  const name = form.value.name.trim()
  if (!name) {
    ElMessage.warning('请输入标签名称')
    return
  }
  const color = normalizeColor(form.value.color, 0, name)
  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      await axios.post('/api/v1/tags', { name, color })
      ElMessage.success('已创建标签')
    } else if (form.value.id) {
      await axios.put(`/api/v1/tags/${form.value.id}`, { name, color })
      ElMessage.success('已更新标签')
    }
    dialogVisible.value = false
    await loadTags()
    await loadSummary()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function confirmDelete(tag: TagRecord) {
  try {
    await ElMessageBox.confirm(`确定删除标签「${tag.name}」吗？该标签下的图片不会被删除。`, '删除标签', { type: 'warning' })
    await axios.delete(`/api/v1/tags/${tag.id}`)
    ElMessage.success('已删除')
    await loadTags()
    await loadSummary()
  } catch {
    /* cancelled */
  }
}

function toggleSelect(id: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter(x => x !== id)
  }
}

function toggleSelectAll(checked: boolean) {
  if (checked) selectedIds.value = listView.value.map(t => t.id)
  else selectedIds.value = []
}

async function deleteBatch() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要删除的标签')
    return
  }
  try {
    await ElMessageBox.confirm(`确定批量删除选中的 ${selectedIds.value.length} 个标签吗？`, '批量删除', { type: 'warning' })
    await axios.post('/api/v1/tags/batch-delete', { ids: selectedIds.value })
    ElMessage.success('已批量删除')
    await loadTags()
    await loadSummary()
  } catch {
    /* cancelled */
  }
}

function openMerge() {
  mergeSources.value = []
  mergeTarget.value = null
  mergeDialogVisible.value = true
}

async function submitMerge() {
  if (!mergeTarget.value || mergeSources.value.length === 0) {
    ElMessage.warning('请选择来源和目标标签')
    return
  }
  if (mergeSources.value.includes(mergeTarget.value)) {
    ElMessage.warning('目标标签不能与来源相同')
    return
  }
  try {
    await axios.post('/api/v1/tags/merge', { source_ids: mergeSources.value, target_id: mergeTarget.value })
    ElMessage.success('合并完成')
    mergeDialogVisible.value = false
    await loadTags()
    await loadSummary()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '合并失败')
  }
}

function handlePageChange(p: number) {
  page.value = p
  loadTags()
}

function goTagImages(tag: TagRecord) {
  router.push(`/tags/${tag.id}/images?name=${encodeURIComponent(tag.name)}`)
}

onMounted(() => {
  loadTags()
  loadSummary()
})
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
      <header class="mobile-topbar">
        <button class="icon-btn ghost" @click="toggleNav">☰</button>
        <div class="mobile-brand">
          <span class="logo-mini">📸</span>
          <span>标签</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏡</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">标签管理中心</div>
          <div class="subtitle">支持自定义分类标签，可编辑/删除/合并，包含可视化统计，与 EXIF/AI 标签分开管理</div>
        </div>
        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}</span>
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
                <p>随时随地 · 标签管理</p>
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

      <section class="stats-panel">
        <div class="stat-card">
          <div class="label">标签总数</div>
          <div class="num">{{ summary.total_tags }}</div>
          <div class="hint">仅自定义分类标签，不含 EXIF / AI 标签</div>
        </div>

        <div class="visual-row">
          <div class="chart-card">
            <div class="chart-head">
              <div>
                <div class="chart-title">标签分布</div>
                <div class="hint">可视化浏览标签使用次数</div>
              </div>
              <div class="mode-switch">
                <button :class="{ active: chartMode === 'bar' }" @click="chartMode = 'bar'">柱状图</button>
                <button :class="{ active: chartMode === 'pie' }" @click="chartMode = 'pie'">饼图</button>
              </div>
            </div>

            <div v-if="chartMode === 'bar'" class="chart-grid">
              <div
                v-for="item in chartData"
                :key="item.id"
                class="bar"
                :style="{ height: (8 + (item.count || 0) / barMax * 140) + 'px', background: item.color }"
              >
                <span class="bar-count">{{ item.count }}</span>
                <span class="bar-name">{{ item.name }}</span>
              </div>
            </div>

            <div v-else class="pie-wrapper">
              <div
                class="pie"
                :style="{
                  background: 'conic-gradient(' + chartData.map((s, i) => {
                    const total = chartData.reduce((sum, c) => sum + (c.count || 0), 0) || 1
                    const from = chartData.slice(0, i).reduce((sum, c) => sum + (c.count || 0), 0) / total * 100
                    const to = (chartData.slice(0, i).reduce((sum, c) => sum + (c.count || 0), 0) + (s.count || 0)) / total * 100
                    return `${s.color} ${from}% ${to}%`
                  }).join(', ') + ')'
                }"
              ></div>
              <div class="pie-slices">
                <div v-for="slice in chartData" :key="slice.id" class="slice-row">
                  <span class="dot" :style="{ background: slice.color }"></span>
                  <span class="name">{{ slice.name }}</span>
                  <span class="pct">
                    {{
                      chartData.reduce((sum, c) => sum + (c.count || 0), 0)
                        ? (((slice.count || 0) / chartData.reduce((sum, c) => sum + (c.count || 0), 0)) * 100).toFixed(1)
                        : '0.0'
                    }}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="cloud-card">
            <div class="chart-title">词云</div>
            <div class="cloud">
              <span
                v-for="tag in wordCloud"
                :key="tag.id"
                :style="{ color: tag.color, fontSize: (tag.size || 16) + 'px' }"
              >
                {{ tag.name }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section class="table-card">
        <div class="table-head">
          <div class="title">标签列表</div>
          <div class="actions">
            <input v-model="filterKeyword" placeholder="搜索标签名称..." @keyup.enter="handleSearch" />
            <button class="ghost-btn" @click="handleSearch">搜索</button>
            <button class="ghost-btn" @click="openMerge">合并</button>
            <button class="ghost-btn danger" @click="deleteBatch">批量删除</button>
            <button class="primary-btn" @click="openCreate">新建</button>
          </div>
        </div>

        <div class="table">
          <div class="row header">
            <span class="check-col">
              <input type="checkbox" :checked="allSelected" @change="toggleSelectAll(($event.target as HTMLInputElement).checked)" />
            </span>
            <span>标签名称</span>
            <span>颜色</span>
            <span>图片数量</span>
            <span>创建时间</span>
            <span>操作</span>
          </div>
          <div v-if="!loading && listView.length === 0" class="empty-row">暂无标签，点击右上角「新建」创建吧～</div>
          <div v-for="(tag, idx) in listView" :key="tag.id" class="row">
            <span class="check-col">
              <input
                type="checkbox"
                :checked="selectedIds.includes(tag.id)"
                @change="toggleSelect(tag.id, ($event.target as HTMLInputElement).checked)"
              />
            </span>
            <span class="name">{{ tag.name }}</span>
            <span class="color-cell">
              <span class="color-dot" :style="{ background: tag.color }"></span>
              <span class="pill" :style="{ background: tag.color + '22', color: '#b05f7a' }">{{ tag.name }}</span>
            </span>
            <span>{{ tag.count }} 张</span>
            <span class="muted">{{ formatDate(tag.created_at) }}</span>
            <span class="ops">
              <a @click="goTagImages(tag)">查看图片</a>
              <a @click="openEdit(tag)">编辑</a>
              <a class="danger" @click="confirmDelete(tag)">删除</a>
            </span>
          </div>
        </div>

        <div class="pager">
          <el-pagination
            background
            :page-size="pageSize"
            layout="prev, pager, next"
            :total="total"
            :current-page="page"
            @current-change="handlePageChange"
          />
        </div>
      </section>

      <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
    </main>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新建标签' : '编辑标签'" width="380px">
      <div class="form">
        <label>名称</label>
        <el-input v-model="form.name" placeholder="请输入标签名称" />
        <label style="margin-top: 8px">颜色</label>
        <el-color-picker v-model="form.color" show-alpha />
      </div>
      <template #footer>
        <button class="ghost-btn" @click="dialogVisible = false">取消</button>
        <button class="primary-btn" :disabled="saving" @click="saveTag">{{ saving ? '保存中..' : '保存' }}</button>
      </template>
    </el-dialog>

    <el-dialog v-model="mergeDialogVisible" title="合并标签" width="440px">
      <div class="merge-grid">
        <div>
          <label>来源标签（可多选）</label>
          <el-select v-model="mergeSources" multiple placeholder="选择要合并的标签">
            <el-option v-for="tag in listView" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </div>
        <div>
          <label>目标标签</label>
          <el-select v-model="mergeTarget" placeholder="选择合并到的标签">
            <el-option v-for="tag in listView" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </div>
      </div>
      <template #footer>
        <button class="ghost-btn" @click="mergeDialogVisible = false">取消</button>
        <button class="primary-btn" @click="submitMerge">开始合并</button>
      </template>
    </el-dialog>
  </div>
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
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.92); }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; }
.welcome { font-size: 13px; color: #8c546e; }

.stats-panel { padding: 16px 20px 4px; display: flex; flex-direction: column; gap: 12px; }
.stat-card { background: rgba(255, 255, 255, 0.94); border-radius: 16px; padding: 14px 16px; box-shadow: 0 10px 22px rgba(255, 165, 199, 0.2); width: 240px; }
.stat-card .label { color: #a35d76; font-size: 12px; }
.stat-card .num { font-size: 28px; color: #ff4c8a; font-weight: 700; }
.hint { color: #b6788d; font-size: 12px; }
.visual-row { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; }
.chart-card, .cloud-card { background: rgba(255, 255, 255, 0.94); border-radius: 18px; padding: 14px 16px; box-shadow: 0 10px 22px rgba(255, 165, 199, 0.2); min-height: 240px; }
.chart-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.chart-title { font-size: 14px; color: #a35d76; margin-bottom: 6px; }
.mode-switch button { border: none; padding: 6px 10px; border-radius: 12px; background: #ffeef5; color: #b05f7a; cursor: pointer; margin-left: 6px; }
.mode-switch button.active { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.35); }
.chart-grid { display: flex; align-items: flex-end; gap: 10px; min-height: 200px; padding: 8px 10px; background: #fff7fb; border-radius: 14px; overflow-x: auto; }
.bar { flex: 1; min-width: 60px; border-radius: 10px 10px 4px 4px; position: relative; box-shadow: 0 6px 12px rgba(255, 168, 190, 0.35); display: flex; align-items: flex-end; justify-content: center; }
.bar-count { position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #b05f7a; }
.bar-name { font-size: 12px; color: #5a2f3d; margin-bottom: 6px; }
.pie-wrapper { display: grid; grid-template-columns: 1fr 1fr; align-items: center; gap: 12px; }
.pie { width: 180px; height: 180px; border-radius: 50%; box-shadow: 0 6px 12px rgba(255, 168, 190, 0.35); background: #ffeef5; margin: 0 auto; }
.pie-slices { display: flex; flex-direction: column; gap: 6px; }
.slice-row { display: grid; grid-template-columns: 16px 1fr 60px; align-items: center; font-size: 13px; color: #5a2f3d; }
.slice-row .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.slice-row .pct { color: #a35d76; text-align: right; }
.cloud { display: flex; flex-wrap: wrap; gap: 10px; padding: 10px; background: #fff7fb; border-radius: 12px; min-height: 160px; }

.table-card { margin: 8px 20px 10px; background: rgba(255, 255, 255, 0.95); border-radius: 18px; box-shadow: 0 12px 24px rgba(255, 165, 199, 0.3); padding: 12px 12px 4px; }
.table-head { display: flex; justify-content: space-between; align-items: center; padding: 0 6px 6px; gap: 10px; flex-wrap: wrap; }
.table-head .title { font-weight: 600; color: #ff4c8a; }
.table-head input { border-radius: 12px; border: 1px solid rgba(255, 190, 210, 0.8); padding: 6px 10px; font-size: 13px; outline: none; min-width: 180px; }
.table { width: 100%; }
.row { display: grid; grid-template-columns: 60px 1.5fr 1fr 1fr 1fr 1fr; align-items: center; padding: 10px 8px; border-bottom: 1px solid #ffe6ef; font-size: 13px; }
.row.header { font-weight: 600; color: #8c546e; background: #fff7fb; border-radius: 12px; }
.name { color: #613448; }
.color-cell { display: flex; align-items: center; gap: 8px; }
.color-dot { width: 16px; height: 16px; border-radius: 6px; border: 1px solid rgba(0,0,0,0.05); }
.pill { padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.ops a { margin-right: 8px; color: #ff4c8a; cursor: pointer; }
.ops a.danger { color: #d95959; }
.muted { color: #b57a90; }
.check-col { display: flex; justify-content: center; }
.empty-row { padding: 18px; color: #b6788d; text-align: center; }
.pager { padding: 10px 8px; display: flex; justify-content: flex-end; }

footer { text-align: center; font-size: 12px; color: #b57a90; padding: 10px 0 16px; }
.form label { display: block; font-size: 12px; color: #a35d76; margin: 6px 0 2px; }
.merge-grid { display: flex; flex-direction: column; gap: 12px; }
.primary-btn, .ghost-btn { border: none; border-radius: 999px; padding: 8px 14px; cursor: pointer; font-size: 13px; }
.primary-btn { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.ghost-btn { background: #ffeef5; color: #b05f7a; border: 1px solid rgba(255, 180, 205, 0.7); }
.ghost-btn.danger { color: #d95959; border-color: #f4a6a6; }

/* 移动端 */
.mobile-topbar { display: none; align-items: center; justify-content: space-between; padding: 10px 16px 0; gap: 12px; }
.mobile-brand { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #d2517f; }
.logo-mini { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; border-radius: 10px; padding: 6px; font-size: 12px; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }
.icon-btn.ghost { background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(255, 190, 210, 0.7); }

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

@media (max-width: 1200px) { .visual-row { grid-template-columns: 1fr; } .row { grid-template-columns: 50px 1fr 1fr 1fr 1fr 1fr; } }
@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .row { grid-template-columns: 40px 1fr 1fr 1fr; grid-auto-rows: auto; }
  .chart-head { flex-direction: column; align-items: flex-start; }
  .stats-panel { padding-inline: 12px; }
  .table-card { margin-inline: 12px; }
}
@media (max-width: 640px) {
  .actions { width: 100%; gap: 8px; display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
  .row { grid-template-columns: 32px 1fr; grid-row-gap: 6px; }
  .row span:nth-child(n+3) { font-size: 12px; color: #8c546e; }
  .ops { display: flex; gap: 8px; }
}
</style>
