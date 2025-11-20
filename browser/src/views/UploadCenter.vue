<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// 模拟当前用户
const username = ref('hyk')

// 上传设置
const targetFolder = ref('我的图库')
const visibility = ref<'public' | 'private'>('public')
const tags = ref<string[]>(['旅行'])
const newTag = ref('')
const openDetailAfter = ref(true)

// 上传文件队列
type UploadStatus = 'waiting' | 'uploading' | 'success' | 'error'

interface UploadItem {
  id: number
  name: string
  size: number
  status: UploadStatus
  progress: number
  errorMessage?: string
  raw?: File
}

const uploadItems = ref<UploadItem[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)

// 选择文件
function onSelectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files) return

  for (const file of Array.from(files)) {
    addFileToQueue(file)
  }

  // 选完文件后重置 input，方便下次重复选择同一个文件名
  input.value = ''
}

// 拖拽上传
function onDrop(event: DragEvent) {
  event.preventDefault()
  const files = event.dataTransfer?.files
  if (!files) return

  for (const file of Array.from(files)) {
    addFileToQueue(file)
  }
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
}

function addFileToQueue(file: File) {
  uploadItems.value.push({
    id: Date.now() + Math.random(),
    name: file.name,
    size: file.size,
    status: 'waiting',
    progress: 0,
    raw: file,
  })
}

function triggerSelectFiles() {
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
}

function formatSize(size: number) {
  if (!size) return ''
  const mb = size / 1024 / 1024
  if (mb < 1) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${mb.toFixed(2)} MB`
}

// 标签
function addTag() {
  const val = newTag.value.trim()
  if (!val) return
  if (!tags.value.includes(val)) {
    tags.value.push(val)
  }
  newTag.value = ''
}
function removeTag(tag: string) {
  tags.value = tags.value.filter((t) => t !== tag)
}


function startUpload() {
  uploadItems.value.forEach((item) => {
    if (item.status === 'success') return

    item.status = 'uploading'
    item.progress = 0
    item.errorMessage = ''

    const timer = setInterval(() => {
      if (item.progress >= 100) {
        clearInterval(timer)
        
        item.status = 'success'
      } else {
        item.progress += 5
      }
    }, 80)
  })
}

// 删除单个队列项
function removeItem(id: number) {
  uploadItems.value = uploadItems.value.filter((i) => i.id !== id)
}


function logout() {
  router.push('/auth/login')
}
function goBackHome() {
  router.push('/')
}
</script>

<template>
  <div class="dashboard">
    <!-- 左侧导航-->
    <aside class="sidebar">
      <div class="logo">
        <div class="icon">📸</div>
        <div class="text">
          <h1>Photory</h1>
          <p>记录世间每一份美好，让瞬间变成永恒～</p>
        </div>
      </div>

      <nav>
        <a @click="goBackHome">🏠 首页</a>
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
      <!-- 顶部导航 -->
      <header class="topbar">
        <div class="left">
          <div class="title">上传中心 · 快来丰富你的专属图库吧！ ✨</div>
          <div class="subtitle">
            支持拖拽上传、多张图片批量导入，上传后可以愉快浏览～
          </div>
        </div>
        <div class="right">
          <span class="welcome">欢迎你，亲爱的 Photory 用户 {{ username }}！</span>
          <button class="icon-btn" title="返回首页" @click="goBackHome">🏡</button>
          <button class="icon-btn" title="退出登录" @click="logout">🚪</button>
        </div>
      </header>

      <!-- 主体内容 -->
      <section class="upload-layout">
        <!-- 左侧：拖拽上传区域 -->
        <div
          class="upload-drop-card"
          @drop="onDrop"
          @dragover="onDragOver"
        >
          <div class="drop-inner">
            <div class="upload-icon">⬆️</div>
            <h2>拖拽文件到这里</h2>
            <p>支持 JPG、PNG等格式～</p>
            <button class="select-btn" @click="triggerSelectFiles">点击选择文件</button>
            <input
              ref="fileInputRef"
              type="file"
              multiple
              class="file-input"
              @change="onSelectFiles"
            />
          </div>
        </div>

        <!-- 右侧：上传设置 -->
        <div class="upload-settings-card">
          <h3>上传设置</h3>

          <div class="setting-item">
            <label>目标文件夹</label>
            <select v-model="targetFolder">
              <option value="我的图库">我的图库</option>
              <option value="旅行相册">旅行相册</option>
              <option value="日常碎片">日常碎片</option>
            </select>
          </div>

          <div class="setting-item">
            <label>可见性</label>
            <div class="radio-group">
              <button
                class="pill"
                :class="{ active: visibility === 'public' }"
                @click="visibility = 'public'"
              >
                公开
              </button>
              <button
                class="pill"
                :class="{ active: visibility === 'private' }"
                @click="visibility = 'private'"
              >
                私密
              </button>
            </div>
          </div>

          <div class="setting-item">
            <label>添加标签</label>
            <div class="tags-row">
              <span
                v-for="tag in tags"
                :key="tag"
                class="tag"
                @click="removeTag(tag)"
              >
                {{ tag }} ×
              </span>
            </div>
            <div class="tag-input-row">
              <input
                v-model="newTag"
                placeholder="输入标签后回车或点击 + 新增"
                @keyup.enter="addTag"
              />
              <button class="add-tag-btn" @click="addTag">+ 新增</button>
            </div>
          </div>

          <div class="setting-item toggle-row">
            <label>上传后打开图片详情</label>
            <label class="switch">
              <input type="checkbox" v-model="openDetailAfter" />
              <span class="slider"></span>
            </label>
          </div>

          <button class="start-upload-btn" @click="startUpload">
            开始上传
          </button>
        </div>
      </section>

      <!-- 上传队列 -->
      <section class="upload-queue-section">
        <h3>上传队列</h3>

        <div
          v-if="uploadItems.length === 0"
          class="empty-queue"
        >
          暂时还没有待上传的图片～ 先从上面选择或拖拽一些可爱的小照片吧 💗
        </div>

        <ul v-else class="upload-list">
          <li
            v-for="item in uploadItems"
            :key="item.id"
            class="upload-item"
          >
            <div class="file-icon">🗂️</div>
            <div class="file-main">
              <div class="file-name-row">
                <span class="file-name">{{ item.name }}</span>
                <span class="file-size">{{ formatSize(item.size) }}</span>
              </div>
              <div class="progress-row">
                <div class="progress-bar">
                  <div
                    class="progress-inner"
                    :class="{
                      success: item.status === 'success',
                      error: item.status === 'error'
                    }"
                    :style="{ width: item.progress + '%' }"
                  ></div>
                </div>
                <span class="status-pill" :class="item.status">
                  {{
                    item.status === 'waiting'
                      ? '等待上传'
                      : item.status === 'uploading'
                      ? '上传中…'
                      : item.status === 'success'
                      ? '完成'
                      : '失败'
                  }}
                </span>
              </div>
              <div
                v-if="item.status === 'error' && item.errorMessage"
                class="error-text"
              >
                {{ item.errorMessage }}
              </div>
            </div>
            <button class="remove-btn" @click="removeItem(item.id)">×</button>
          </li>
        </ul>
      </section>

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

/* 左侧导航*/
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
  cursor: pointer;
}
nav a:hover {
  background: rgba(255, 153, 187, 0.16);
  color: #ff4c8a;
}

/* 主体布局 */
main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* 顶部栏*/
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

/* 上传布局 */
.upload-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  padding: 20px 24px 10px;
}

/* 左侧拖拽卡片 */
.upload-drop-card {
  background: #fff7fb;
  border-radius: 24px;
  padding: 28px 24px;
  box-shadow: 0 16px 32px rgba(255, 165, 199, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}
.drop-inner {
  text-align: center;
}
.upload-icon {
  font-size: 42px;
  margin-bottom: 10px;
}
.drop-inner h2 {
  margin: 8px 0;
  color: #ff3f87;
}
.drop-inner p {
  font-size: 13px;
  color: #a25c77;
  margin-bottom: 16px;
}
.select-btn {
  border: none;
  border-radius: 999px;
  padding: 8px 22px;
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(255, 120, 165, 0.45);
}
.select-btn:hover {
  transform: translateY(-1px);
}
.file-input {
  display: none;
}

/* 右侧设置卡片 */
.upload-settings-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  padding: 20px 22px;
  box-shadow: 0 12px 24px rgba(255, 165, 199, 0.3);
}
.upload-settings-card h3 {
  margin: 0 0 10px;
  color: #ff4c8a;
}
.setting-item {
  margin-bottom: 14px;
}
.setting-item label {
  font-size: 13px;
  color: #8c546e;
  display: block;
  margin-bottom: 6px;
}
.setting-item select,
.setting-item input {
  width: 100%;
  border-radius: 14px;
  border: 1px solid rgba(255, 190, 210, 0.9);
  padding: 6px 10px;
  font-size: 13px;
  outline: none;
  background: #fff;
}
.setting-item select:focus,
.setting-item input:focus {
  border-color: #ff8bb3;
}

/* 可见性 pill */
.radio-group {
  display: flex;
  gap: 8px;
}
.pill {
  border-radius: 999px;
  border: 1px solid rgba(255, 180, 205, 0.9);
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
}
.pill.active {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
}

/* 标签 */
.tags-row {
  min-height: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag {
  background: #ffe4f0;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 11px;
  color: #b05f7a;
  cursor: pointer;
}
.tag-input-row {
  margin-top: 6px;
  display: flex;
  gap: 6px;
}
.add-tag-btn {
  border-radius: 999px;
  border: none;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  background: #ffe3f0;
  color: #b05f7a;
}

/* 开关 */
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.switch {
  position: relative;
  display: inline-block;
  width: 42px;
  height: 22px;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: #ffd7e5;
  transition: 0.2s;
  border-radius: 999px;
}
.slider:before {
  position: absolute;
  content: '';
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.2s;
  border-radius: 50%;
}
.switch input:checked + .slider {
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
}
.switch input:checked + .slider:before {
  transform: translateX(18px);
}

/* 上传按钮 */
.start-upload-btn {
  width: 100%;
  margin-top: 8px;
  border-radius: 999px;
  border: none;
  padding: 8px 0;
  background: linear-gradient(135deg, #ff8bb3, #ff6fa0);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  box-shadow: 0 10px 20px rgba(255, 120, 165, 0.45);
}

/* 上传队列 */
.upload-queue-section {
  padding: 10px 24px 10px;
}
.upload-queue-section h3 {
  margin-bottom: 10px;
  color: #ff4c8a;
}
.empty-queue {
  background: rgba(255, 255, 255, 0.85);
  border-radius: 18px;
  padding: 18px;
  font-size: 13px;
  color: #a35d76;
}
.upload-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.upload-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 16px;
  padding: 10px 12px;
  box-shadow: 0 8px 18px rgba(255, 165, 199, 0.27);
}
.file-icon {
  font-size: 20px;
}
.file-main {
  flex: 1;
}
.file-name-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #613448;
}
.file-size {
  font-size: 11px;
  color: #b57a90;
}
.progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: #ffe4f0;
  overflow: hidden;
}
.progress-inner {
  height: 100%;
  width: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #ffb5cf, #ff7ca8);
  transition: width 0.15s ease;
}
.progress-inner.success {
  background: linear-gradient(135deg, #8bd67b, #4fb35a);
}
.progress-inner.error {
  background: linear-gradient(135deg, #ff8a8a, #ff5555);
}
.status-pill {
  min-width: 60px;
  text-align: center;
  font-size: 11px;
  border-radius: 999px;
  padding: 2px 8px;
  background: #ffeaf3;
  color: #b05f7a;
}
.status-pill.uploading {
  background: #ffe3f0;
}
.status-pill.success {
  background: #e4f7e2;
  color: #4b9d54;
}
.status-pill.error {
  background: #ffe1e1;
  color: #df4b4b;
}
.error-text {
  margin-top: 4px;
  font-size: 11px;
  color: #df4b4b;
}
.remove-btn {
  border: none;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
  color: #c27d98;
}

/* 页脚 */
footer {
  text-align: center;
  font-size: 12px;
  color: #b57a90;
  padding: 10px 0 16px;
}

/* 简单自适应 */
@media (max-width: 1100px) {
  .upload-layout {
    grid-template-columns: 1.5fr 1fr;
  }
}

@media (max-width: 900px) {
  .sidebar {
    display: none;
  }
  .upload-layout {
    grid-template-columns: 1fr;
  }
}
</style>
