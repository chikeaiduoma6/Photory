<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()

// 模拟用户名
const username = ref('hyk')

// 视图模式：网格 / 瀑布流 / 大卡片
const viewMode = ref<'grid' | 'masonry' | 'large'>('grid')

// 排序方式：最新 / 最早
const sortOrder = ref<'newest' | 'oldest'>('newest')

// 分页控制
const currentPage = ref(1)
const pageSize = ref(12)

// 批量管理
const isBatchMode = ref(false)
const selectedIds = ref<number[]>([])


const allImages = ref([
  { id: 1, title: '樱花', date: '2025-11-05', url: '/demo/sakura.jpg' },
  { id: 2, title: '海浪', date: '2025-11-08', url: '/demo/sea.jpg' },
  { id: 3, title: '小猫', date: '2025-11-06', url: '/demo/kitty.jpg' },
  { id: 4, title: '日落', date: '2025-11-07', url: '/demo/sunset.jpg' },
  { id: 5, title: '雪山', date: '2025-11-03', url: '/demo/mountain.jpg' },
  { id: 6, title: '街角', date: '2025-11-01', url: '/demo/street.jpg' },
  { id: 7, title: '森林', date: '2025-10-31', url: '/demo/forest.jpg' },
  { id: 8, title: '咖啡', date: '2025-11-02', url: '/demo/coffee.jpg' },
  { id: 9, title: '建筑', date: '2025-10-30', url: '/demo/building.jpg' },
  { id: 10, title: '笑脸', date: '2025-10-29', url: '/demo/portrait.jpg' },
  { id: 11, title: '灯光', date: '2025-10-28', url: '/demo/light.jpg' },
  { id: 12, title: '山丘', date: '2025-10-27', url: '/demo/hill.jpg' },
  { id: 13, title: '月亮', date: '2025-10-26', url: '/demo/moon.jpg' },
])

// 排序后的列表
const sortedImages = computed(() => {
  const arr = [...allImages.value]
  arr.sort((a, b) => {
    if (sortOrder.value === 'newest') {
      return b.date.localeCompare(a.date)
    } else {
      return a.date.localeCompare(b.date)
    }
  })
  return arr
})

const total = computed(() => sortedImages.value.length)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

// 当前页图片
const pagedImages = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return sortedImages.value.slice(start, start + pageSize.value)
})

function handlePageChange(p: number) {
  currentPage.value = p
}

// 排序方式切换时回到第一页
watch(sortOrder, () => {
  currentPage.value = 1
})

// 切换视图模式
function changeView(mode: 'grid' | 'masonry' | 'large') {
  viewMode.value = mode
}

// 批量管理
function toggleBatchMode() {
  isBatchMode.value = !isBatchMode.value
  if (!isBatchMode.value) {
    selectedIds.value = []
  }
}

function toggleSelect(id: number) {
  if (!isBatchMode.value) return
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) {
    selectedIds.value.splice(i, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function isSelected(id: number) {
  return selectedIds.value.includes(id)
}

// 登出 → 回登录页
function logout() {
  ElMessage.success('已退出登录 Photory期待和你的再次相遇哦～')
  router.push('/auth/login') 
}

// 上传按钮
function upload() {
  ElMessage.info('')
}
</script>

<template>
  <div class="dashboard">
    <!-- 左侧导航 -->
    <aside class="sidebar">
      <div class="logo">
        <div class="icon">📸</div>
        <div class="text">
          <h1>Photory</h1>
          <p>记录世间每一份美好，让瞬间变成永恒～</p>
        </div>
      </div>

      <nav>
        <a class="active">🏠 首页</a>
        <a>📚 相册</a>
        <a>📁 文件夹</a>
        <a>🏷️ 标签</a>
        <a>✨ 智能文件夹</a>
        <a>🤖 AI 工作台</a>
        <a>✅ 任务</a>
        <a>🗑️ 回收站</a>
        <a>⚙️ 设置</a>
      </nav>
    </aside>

    <!-- 右侧主体 -->
    <main>
      <!-- 顶部栏-->
      <header class="topbar">
        <div class="left">
          <div class="title">今天也要好好记录生活 ✨</div>
          <div class="subtitle">
            Photory 记录你的每一张Photo下的温柔story～
          </div>
        </div>

        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}！</span>
          <el-badge is-dot class="bell">
            <button class="icon-btn">🔔</button>
          </el-badge>
          <button class="icon-btn" @click="logout">🚪</button>
        </div>
      </header>

      <!-- 顶部粉色卡片 + 统计 -->
      <section class="hero">
        <div class="hero-left">
          <div class="badge">今日心情 · 小小记录</div>
          <h2>让美好永远留在心间 🌸</h2>
          <p>
            这里是你的专属回忆小宇宙，生活里的每一朵花、每一片天空、每一场落日，都值得被认真记录。
          </p>
          <div class="stats">
            <div>
              <b>{{ total }}</b>
              <span>图片总数</span>
            </div>
            <div>
              <b>1</b>
              <span>今日上传</span>
            </div>
            <div>
              <b>3</b>
              <span>进行中的任务</span>
            </div>
          </div>
        </div>

        <div class="hero-right">
          <div class="hero-img">
            
            <span>🌷 Photory 等你来探索哦～</span>
          </div>
        </div>
      </section>

      <!-- 工具栏：上传 + 批量管理 + 视图模式 + 排序 -->
      <section class="toolbar">
        <div class="left">
          <button class="upload-btn" @click="upload">
            ☁️ 上传图片
          </button>
          <button
            class="manage-btn"
            :class="{ active: isBatchMode }"
            @click="toggleBatchMode"
          >
            🧺 {{ isBatchMode ? '退出批量管理' : '批量管理' }}
          </button>
          <span v-if="isBatchMode" class="selected-tip">
            已选中 {{ selectedIds.length }} 张图片
          </span>
        </div>

        <div class="right">
          <div class="view-switch">
            <button
              class="view-pill"
              :class="{ active: viewMode === 'grid' }"
              @click="changeView('grid')"
            >
              ⬛ 网格
            </button>
            <button
              class="view-pill"
              :class="{ active: viewMode === 'masonry' }"
              @click="changeView('masonry')"
            >
              🧱 瀑布流
            </button>
            <button
              class="view-pill"
              :class="{ active: viewMode === 'large' }"
              @click="changeView('large')"
            >
              🃏 大卡片
            </button>
          </div>

          <div class="sort">
            <span>排序：</span>
            <button
              class="sort-pill"
              :class="{ active: sortOrder === 'newest' }"
              @click="sortOrder = 'newest'"
            >
              最新上传
            </button>
            <button
              class="sort-pill"
              :class="{ active: sortOrder === 'oldest' }"
              @click="sortOrder = 'oldest'"
            >
              最早记录
            </button>
          </div>
        </div>
      </section>

      <!-- 图库 -->
      <section class="gallery" :class="viewMode">
        <div
          v-for="img in pagedImages"
          :key="img.id"
          class="photo"
          :class="{ selected: isSelected(img.id), 'batch-mode': isBatchMode }"
          @click="toggleSelect(img.id)"
        >
          <div class="select-badge" v-if="isBatchMode">
            <span v-if="isSelected(img.id)">✔</span>
          </div>
          <img :src="img.url" :alt="img.title" loading="lazy" />
          <div class="caption">
            <div class="title">{{ img.title }}</div>
            <div class="date">{{ img.date }}</div>
          </div>
        </div>
      </section>

      <!-- 分页 -->
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
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #ffeef5, #ffe5f0);
  color: #4b4b4b;
}

/* 左侧导航 */
.sidebar {
  width: 220px;
  background: linear-gradient(180deg, #fff7fb, #ffeef5);
  border-right: 1px solid rgba(255, 190, 210, 0.6);
  padding: 20px;
}
.logo {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}
.logo .icon {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo h1 {
  font-size: 18px;
  color: #ff4c8a;
  margin: 0;
}
.logo p {
  font-size: 11px;
  color: #b6788d;
  margin: 0;
}
nav a {
  display: block;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  color: #6b3c4a;
  margin: 2px 0;
  cursor: default;
}
nav a.active,
nav a:hover {
  background: rgba(255, 153, 187, 0.16);
  color: #ff4c8a;
}

/* 主体 */
main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* 顶部栏 */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  border-bottom: 1px solid rgba(255, 190, 210, 0.5);
  background: rgba(255, 255, 255, 0.9);
}
.topbar .title {
  font-weight: 600;
  color: #ff4c8a;
}
.topbar .subtitle {
  font-size: 12px;
  color: #a36e84;
}
.topbar .right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.welcome {
  font-size: 13px;
  color: #8c546e;
}
.icon-btn {
  background: #ffeef5;
  border: none;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  cursor: pointer;
}
.icon-btn:hover {
  background: #ffd6e5;
}

/* 顶部大卡片 */
.hero {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 20px;
  padding: 20px 24px 10px;
}
.hero-left {
  background: linear-gradient(135deg, #ffe9f5, #ffe1f0);
  border-radius: 24px;
  padding: 20px 24px;
  box-shadow: 0 16px 32px rgba(255, 165, 199, 0.35);
}
.hero-left .badge {
  background: #fff;
  display: inline-block;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  color: #c06d8a;
}
.hero-left h2 {
  color: #ff3f87;
  margin: 12px 0 6px;
}
.hero-left p {
  font-size: 13px;
  color: #a25c77;
}
.stats {
  display: flex;
  gap: 18px;
  margin-top: 18px;
}
.stats div {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 14px;
  padding: 10px 16px;
  text-align: center;
  min-width: 90px;
}
.stats b {
  color: #ff4c8a;
  font-size: 18px;
}
.stats span {
  display: block;
  font-size: 11px;
  color: #b6788d;
}


.hero-right {
  display: flex;
  align-items: center;
  justify-content: center;
}
.hero-right .hero-img {
  width: 100%;
  height: 100%;
  min-height: 160px;
  border-radius: 24px;
  background: url('@/assets/pretty_flower.jpg') center/cover no-repeat;
  border: 8px solid rgba(255, 255, 255, 0.95);
  box-shadow: 0 18px 36px rgba(255, 167, 201, 0.45);
  position: relative;
}
.hero-img span {
  position: absolute;
  bottom: 14px;
  left: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 999px;
  font-size: 12px;
  padding: 6px 12px;
  color: #a15773;
  text-align: center;
}

/* 工具栏：上传 + 批量管理 + 浏览模式 + 排序 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 6px 24px 0;
}
.toolbar .left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.upload-btn,
.manage-btn {
  border: none;
  border-radius: 20px;
  padding: 8px 18px;
  cursor: pointer;
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
  font-size: 13px;
  box-shadow: 0 4px 10px rgba(255, 120, 165, 0.4);
}
.manage-btn {
  background: linear-gradient(135deg, #ffb2cc, #ff8db8);
}
.manage-btn.active {
  background: linear-gradient(135deg, #fca9c9, #ff88b3);
}
.selected-tip {
  font-size: 12px;
  color: #a35d76;
}


.toolbar .right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.view-switch,
.sort {
  display: flex;
  align-items: center;
  gap: 8px;
}
.view-pill,
.sort-pill {
  border-radius: 999px;
  border: 1px solid rgba(255, 180, 205, 0.9);
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
}
.view-pill.active,
.sort-pill.active {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
}

/* 图库区域：保持 3 行 4 列 */
.gallery {
  padding: 16px 24px 10px;
}

/* 网格模式 */
.gallery.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}

/* 瀑布流 */
.gallery.masonry {
  column-count: 4;
  column-gap: 18px;
}
.gallery.masonry .photo {
  break-inside: avoid;
  margin-bottom: 18px;
}

/* 大卡片 */
.gallery.large {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.gallery.large .photo {
  display: flex;
  height: 190px;
}
.gallery.large .photo img {
  width: 45%;
  height: 100%;
  object-fit: cover;
}
.gallery.large .caption {
  flex: 1;
  padding: 16px;
}

/* 单个图片卡片 */
.photo {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  background: #ffeaf3;
  box-shadow: 0 10px 20px rgba(255, 153, 187, 0.28);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border 0.15s ease;
}
.gallery.grid .photo {
  height: 230px;
  display: flex;
  flex-direction: column;
}
.photo img {
  width: 100%;
  height: 72%;
  object-fit: cover;
  background: #fce6f0;
}
.gallery.masonry .photo img {
  height: auto;
}
.caption {
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.caption .title {
  font-size: 13px;
  color: #613448;
}
.caption .date {
  font-size: 11px;
  color: #b57a90;
}

/* 批量选择状态 */
.photo.batch-mode::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0);
  transition: background 0.15s ease;
}
.photo.selected {
  border: 2px solid #ff6fa5;
  box-shadow: 0 0 0 2px rgba(255, 152, 201, 0.5),
    0 10px 24px rgba(255, 152, 201, 0.5);
}
.select-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #ff8cb7;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #ff4c8a;
  z-index: 2;
}
.photo:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 26px rgba(255, 153, 187, 0.4);
}

/* 分页 */
.pagination {
  display: flex;
  justify-content: center;
  margin-bottom: 6px;
}


:deep(.el-pagination.is-background .el-pager li) {
  background-color: #ffeef5;
  border-radius: 999px;
  color: #b26a84;
}
:deep(.el-pagination.is-background .el-pager li.is-active) {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
}
:deep(.el-pagination.is-background .el-pager li:hover) {
  background-color: #ffdce9;
}
:deep(.el-pagination button) {
  background-color: #ffeef5;
  border-radius: 999px;
  color: #b26a84;
}
:deep(.el-pagination button.is-disabled) {
  opacity: 0.5;
}

/* 页脚 */
footer {
  text-align: center;
  font-size: 12px;
  color: #b57a90;
  padding-bottom: 16px;
}

/* 简单自适应 */
@media (max-width: 1200px) {
  .gallery.grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .gallery.masonry {
    column-count: 3;
  }
}
@media (max-width: 900px) {
  .sidebar {
    display: none;
  }
  .hero {
    grid-template-columns: 1fr;
  }
  .gallery.grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .gallery.masonry {
    column-count: 2;
  }
}
</style>
