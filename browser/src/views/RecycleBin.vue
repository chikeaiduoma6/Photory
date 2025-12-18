<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'
import { useLocale } from '@/composables/useLocale'

interface RecycleItem {
  id: number
  name: string
  thumbUrl: string
  fullUrl: string
  deletedAt: string
  daysLeft: number
}

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const preferencesStore = usePreferencesStore()
const links = computed(() => getNavLinks(preferencesStore.language))
const { text } = useLocale()

const currentPath = computed(() => router.currentRoute.value.path)
function go(path: string) { router.push(path); navOpen.value = false }
function isActive(path: string) { return currentPath.value === path || currentPath.value.startsWith(path + '/') }
const navOpen = ref(false)
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
watch(() => router.currentRoute.value.fullPath, () => closeNav())

const items = ref<RecycleItem[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(12)
const selected = ref<number[]>([])
const total = ref(0)

const pagedItems = computed(() => items.value)
const allSelected = computed(() => selected.value.length === items.value.length && items.value.length > 0)

function toggleSelect(id: number) {
  const idx = selected.value.indexOf(id)
  if (idx >= 0) selected.value.splice(idx, 1)
  else selected.value.push(id)
}
function toggleAll() {
  if (allSelected.value) selected.value = []
  else selected.value = items.value.map(i => i.id)
}

function confirmPink(title: string, text: string) {
  return ElMessageBox.confirm(text, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
    customClass: 'pink-confirm',
  })
}

function fallbackToRaw(event: Event, url: string) {
  const img = event.target as HTMLImageElement | null
  if (img && img.src !== url) img.src = url
}

async function fetchRecycle() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/images/recycle', { params: { page: currentPage.value, page_size: pageSize.value } })
    const tokenParam = authStore.token ? `?jwt=${authStore.token}` : ''
    items.value = (res.data.items || []).map((item: any) => ({
      id: item.id,
      name: item.name || item.original_name,
      thumbUrl: (item.thumb_url || `/api/v1/images/${item.id}/thumb`) + tokenParam,
      fullUrl: (item.raw_url || `/api/v1/images/${item.id}/raw`) + tokenParam,
      deletedAt: (item.deleted_at || '').slice(0, 10),
      daysLeft: item.deleted_at ? Math.max(0, 7 - Math.floor((Date.now() - new Date(item.deleted_at).getTime()) / (1000 * 60 * 60 * 24))) : 7,
    }))
    total.value = res.data.total || 0
  } catch (err) {
    ElMessage.error('获取回收站失败')
  } finally {
    loading.value = false
  }
}

async function restore(ids: number[]) {
  if (!ids.length) return
  try {
    await confirmPink('还原图片', `确定还原选中的 ${ids.length} 张图片吗？`)
    await axios.post('/api/v1/images/recycle/restore', { ids })
    selected.value = []
    await fetchRecycle()
  } catch {
    /* cancelled/failed */
  }
}
async function purge(ids: number[]) {
  if (!ids.length) return
  try {
    await confirmPink('永久删除', `确定要永久删除选中的 ${ids.length} 张图片吗？此操作不可恢复。`)
    await axios.post('/api/v1/images/recycle/purge', { ids })
    selected.value = []
    await fetchRecycle()
  } catch {
    /* cancelled/failed */
  }
}
async function clearAll() {
  if (!items.value.length) return
  try {
    await confirmPink('清空回收站', '确定清空回收站中的所有图片吗？此操作不可恢复。')
    await axios.post('/api/v1/images/recycle/clear')
    selected.value = []
    await fetchRecycle()
  } catch {
    /* cancelled/failed */
  }
}
function handleRestoreOne(id: number) { restore([id]) }
function handlePurgeOne(id: number) { purge([id]) }

function handlePageChange(p: number) { currentPage.value = p; fetchRecycle() }

watch(() => authStore.token, token => { if (token) fetchRecycle() })
onMounted(() => { if (authStore.token) fetchRecycle() })
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
          <span class="logo-mini">🗑️</span>
          <span>{{ text('回收站', 'Recycle Bin') }}</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏡</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">{{ text('回收站', 'Recycle Bin') }}</div>
          <div class="subtitle">{{ text('被暂时删除的图片都存储在这里哦！', 'Temporarily deleted photos are stored here.') }}</div>
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
                <h1>{{ text('回收站', 'Recycle Bin') }}</h1>
                <p>{{ text('7 天后自动清空', 'Auto purge in 7 days') }}</p>
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

      <section class="info-row">
        <div class="notice">
          {{ text('回收站中的项目将于 7 天后永久删除 · 请及时处理重要的图片', 'Items here will be permanently deleted after 7 days · Please handle important photos in time.') }}
        </div>
        <div class="stat-card">
          <div class="stat-num">{{ total }}</div>
          <div class="stat-text">{{ text('回收站图片总数', 'Total in recycle bin') }}</div>
        </div>
      </section>

      <section class="toolbar">
        <div class="left">
          <label class="checkbox">
            <input type="checkbox" :checked="allSelected" @change="toggleAll" />
            <span>{{ text('全选', 'Select all') }}</span>
          </label>
        </div>
        <div class="right">
          <button class="pill-btn ghost" @click="restore(selected)" :disabled="!selected.length">{{ text('还原所选', 'Restore selected') }}</button>
          <button class="pill-btn danger" @click="purge(selected)" :disabled="!selected.length">{{ text('永久删除所选', 'Delete selected') }}</button>
          <button class="pill-btn danger strong" @click="clearAll" :disabled="!items.length">{{ text('清空回收站', 'Empty recycle bin') }}</button>
        </div>
      </section>

      <section class="gallery" :class="{ empty: !pagedItems.length }">
        <div v-if="!loading && !pagedItems.length" class="empty-box">回收站目前是空的</div>
        <div
          v-for="img in pagedItems"
          v-else
          :key="img.id"
          class="photo"
          @click="toggleSelect(img.id)"
          :class="{ selected: selected.includes(img.id) }"
        >
          <div class="select-dot" :class="{ on: selected.includes(img.id) }"></div>
          <div class="img-wrapper">
            <img :src="img.thumbUrl" :alt="img.name" loading="lazy" @error="fallbackToRaw($event, img.fullUrl)" />

            <div class="overlay">
              <button class="pill-btn" @click.stop="handleRestoreOne(img.id)">🔄 还原</button>
              <button class="pill-btn danger" @click.stop="handlePurgeOne(img.id)">🗑️ 永久删除</button>
            </div>
          </div>
          <div class="caption">
            <div class="title">{{ img.name }}</div>
            <div class="deleted">删除于 {{ img.deletedAt }}</div>
            <div class="danger-text">{{ img.daysLeft }} 天后永久删除</div>
          </div>
        </div>
      </section>

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
    </main>
  </div>
</template>

<style scoped>
.dashboard { display: flex; min-height: 100vh; background: linear-gradient(135deg, #ffeef5, #ffe5f0); color: #4b4b4b; }
.sidebar { width: 220px; background: linear-gradient(180deg, #fff7fb, #ffeef5); border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 20px; position: sticky; top: 0; height: 100vh; }
.logo { display: flex; gap: 10px; margin-bottom: 20px; }
.logo .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 36px; height: 36px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.logo h1 { font-size: 18px; color: #ff4c8a; margin: 0; }
.logo p { font-size: 11px; color: #b6788d; margin: 0; }
nav a { display: block; padding: 8px 12px; border-radius: 12px; font-size: 13px; color: #6b3c4a; margin: 2px 0; cursor: pointer; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }

main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }
.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255, 255, 255, 0.9); }
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px; }
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.welcome { font-size: 13px; color: #8c546e; }

.info-row { display: grid; grid-template-columns: 2fr 1fr; gap: 10px; padding: 12px 24px 0; }
.notice { background: #fff3d8; color: #b86b00; border: 1px solid #ffd7a0; border-radius: 12px; padding: 10px 14px; font-size: 13px; }
.stat-card { background: #ffeef8; border: 1px solid #ffd2e6; border-radius: 12px; padding: 10px 14px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; box-shadow: 0 6px 14px rgba(255, 145, 180, 0.22); }
.stat-num { font-size: 22px; font-weight: 700; color: #ff4c8a; line-height: 1.1; }
.stat-text { font-size: 12px; color: #a35d76; }

.toolbar { display: flex; justify-content: space-between; align-items: center; padding: 6px 24px; flex-wrap: wrap; gap: 8px; }
.checkbox { display: flex; align-items: center; gap: 6px; color: #8c546e; font-size: 13px; cursor: pointer; }

.gallery { padding: 16px 24px 10px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.gallery.empty { display: flex; justify-content: center; align-items: center; }
.empty-box { background: rgba(255, 255, 255, 0.85); border-radius: 18px; padding: 30px 40px; color: #a35d76; font-size: 14px; }

.photo { position: relative; border-radius: 18px; overflow: hidden; background: #fff; box-shadow: 0 12px 24px rgba(255, 165, 199, 0.28); transition: transform 0.2s ease, box-shadow 0.2s ease; cursor: pointer; }
.photo:hover { transform: translateY(-4px); box-shadow: 0 16px 28px rgba(255, 153, 187, 0.35); }
.photo.selected { box-shadow: 0 0 0 2px rgba(255, 120, 165, 0.7); }
.img-wrapper { position: relative; overflow: hidden; height: 200px; }
.img-wrapper img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.2s ease, filter 0.2s ease; }
.photo:hover img { transform: scale(1.04); filter: brightness(0.9); }
.overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 10px; opacity: 0; transition: opacity 0.2s ease; background: linear-gradient(180deg, rgba(0,0,0,0.15), rgba(0,0,0,0.35)); }
.photo:hover .overlay { opacity: 1; }
.select-dot { position: absolute; top: 10px; left: 10px; width: 16px; height: 16px; border-radius: 50%; background: rgba(255,255,255,0.9); border: 1px solid #ff8bb3; z-index: 2; }
.select-dot.on { background: #ff8bb3; box-shadow: 0 0 0 3px rgba(255,140,183,0.35); }

.caption { padding: 10px 14px 14px; }
.caption .title { font-weight: 600; color: #4b4b4b; }
.deleted { color: #8c546e; font-size: 12px; margin-top: 4px; }
.danger-text { color: #e65d7a; font-size: 12px; margin-top: 2px; }

.pill-btn { border: none; border-radius: 999px; padding: 8px 14px; background: linear-gradient(135deg, #ffa3c3, #ff7fb0); color: #fff; font-size: 13px; cursor: pointer; box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4); }
.pill-btn.ghost { background: #ffeef5; color: #b05f7a; box-shadow: none; border: 1px solid rgba(255, 180, 205, 0.7); }
.pill-btn.danger { background: linear-gradient(135deg, #ff9c9c, #ff6b6b); color: #fff; }
.pill-btn.danger.strong { background: linear-gradient(135deg, #ff6fa0, #ff3f87); }
.pill-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding-bottom: 16px; }
.pagination { display: flex; justify-content: center; }
:deep(.el-pagination.is-background .el-pager li) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination.is-background .el-pager li.is-active) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
:deep(.el-pagination.is-background .el-pager li:hover) { background-color: #ffdce9; }
:deep(.el-pagination button) { background-color: #ffeef5; border-radius: 999px; color: #b26a84; }
:deep(.el-pagination button.is-disabled) { opacity: 0.5; }
footer { text-align: center; font-size: 12px; color: #b57a90; }

:deep(.pink-confirm) { border-radius: 12px; }
:deep(.pink-confirm .el-message-box__title) { color: #ff4c8a; }
:deep(.pink-confirm .el-button--primary) { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); border: none; }
:deep(.pink-confirm .el-button--default) { border-color: #ffb6cf; color: #b05f7a; }

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

@media (max-width: 1200px) { .gallery { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .sidebar { display: none; } .mobile-topbar { display: flex; } .gallery { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) { .gallery { grid-template-columns: repeat(2, minmax(0, 1fr)); } .gallery.masonry { column-count: 1; } .topbar .right { display: none; } }
</style>
