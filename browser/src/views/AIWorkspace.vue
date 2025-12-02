<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')
const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (p: string) => (!p ? '' : p.startsWith('http') ? p : `${apiBase}${p}`)

interface ChatMessage { role: 'user' | 'assistant'; content: string; images?: any[] }
const messages = ref<ChatMessage[]>([
  { role: 'assistant', content: '嗨，我是 AI 图片助理，问我“帮我找夜景的照片”试试？' },
])
const input = ref('请帮我找几张日落或海边的照片')
const sending = ref(false)
const scrollRef = ref<HTMLDivElement | null>(null)
const quickPrompts = [
  '找几张有人物和城市夜景的照片',
  '有哪些动物主题的图片？',
  '列出最近上传的风景照',
  '帮我找有花和微距的作品',
]

function appendMessage(msg: ChatMessage) {
  messages.value.push(msg)
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
async function send() {
  const text = input.value.trim()
  if (!text) return
  appendMessage({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  try {
    const res = await axios.post('/api/v1/images/ai/chat', { messages: messages.value.map(m => ({ role: m.role, content: m.content })) })
    appendMessage({ role: 'assistant', content: res.data.reply || '未找到结果～', images: res.data.images || [] })
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || 'AI 检索失败')
  } finally {
    sending.value = false
  }
}
function usePrompt(p: string) {
  input.value = p
  send()
}
function openImage(id: number) {
  router.push(`/images/${id}`)
}
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
const navOpen = ref(false)
const currentPath = computed(() => router.currentRoute.value.path)
const go = (path: string) => { router.push(path); navOpen.value = false }
const isActive = (path: string) => currentPath.value === path || currentPath.value.startsWith(path + '/')
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)
</script>

<template>
  <div class="dashboard aiworkspace-page">
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
          <span class="logo-mini">📸</span>
          <span>AI 工作台</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏡</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">AI 工作台 · 智能图片检索</div>
          <div class="subtitle">与大模型对话，检索你的图片资产 · 你好，{{ username }}。</div>
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
                <p>智慧对话</p>
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

      <section class="ai-main-card">
        <div class="quick-prompt-row">
          <span>快捷提问：</span>
          <span v-for="p in quickPrompts" :key="p" class="chip" @click="usePrompt(p)">
            {{ p }}
          </span>
        </div>
        <div class="ai-console">
          <div class="chat-area" ref="scrollRef">
            <div v-for="(m, idx) in messages" :key="idx" class="bubble" :class="m.role">
              <div class="role">{{ m.role === 'user' ? '你' : 'AI' }}</div>
              <div class="content" v-html="m.content.replace(/\n/g, '<br/>')"></div>
              <div v-if="m.images?.length" class="thumbs">
                <div v-for="img in m.images" :key="img.id" class="thumb" @click="openImage(img.id)">
                  <img :src="withBase(img.thumb_url)" loading="lazy" />
                  <div class="caption">
                    <div class="name">{{ img.name }}</div>
                    <div class="tags">{{ (img.tags || []).slice(0,3).join(' · ') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="input-bar">
            <textarea v-model="input" :disabled="sending" rows="2" placeholder="和 AI 说点什么吧…"></textarea>
            <button class="send" :disabled="sending" @click="send">{{ sending ? '思考中…' : '发送' }}</button>
          </div>
        </div>
      </section>

      <div class="footer-wrapper">
        <footer>2025 Designed by hyk 用心记录每一份美好~</footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  --pink-main: #ff6fa0;
  --pink-soft: #ffeef5;
  --text-strong: #4b2b3a;
  --text-muted: #9a6c82;
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #ffeef5, #ffe5f0);
  color: var(--text-strong);
}
.sidebar { width: 240px; background: linear-gradient(180deg, #fff7fb, #ffeef5); border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 20px; position: sticky; top: 0; height: 100vh; }
.logo { display: flex; gap: 10px; margin-bottom: 20px; }
.logo .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 36px; height: 36px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.logo h1 { font-size: 18px; color: #ff4c8a; margin: 0; }
.logo p { font-size: 11px; color: #b6788d; margin: 0; }
nav a { display: block; padding: 9px 12px; border-radius: 12px; font-size: 14px; color: #6b3c4a; margin: 4px 0; cursor: pointer; }
nav a.active, nav a:hover { background: rgba(255, 153, 187, 0.16); color: #ff4c8a; }
main { flex: 1; display: flex; flex-direction: column; min-height: 100vh; }

.topbar { display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid rgba(255, 190, 210, 0.5); background: rgba(255,255,255,0.92);}
.topbar .title { font-weight: 600; color: #ff4c8a; font-size: 18px;}
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; }
.welcome { font-size: 13px; color: #8c546e; }

.mobile-topbar { display: none; align-items: center; justify-content: space-between; padding: 10px 16px 0; gap: 12px; }
.mobile-brand { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #d2517f; }
.logo-mini { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; border-radius: 10px; padding: 6px; font-size: 12px; }
.icon-btn { background: #ffeef5; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer;}
.icon-btn.ghost { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); }

.drawer { position: fixed; inset: 0; pointer-events: none; z-index: 20; }
.drawer.open { pointer-events: auto; }
.drawer-mask { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.35); opacity: 0; transition: opacity 0.2s ease; }
.drawer.open .drawer-mask { opacity: 1; }
.drawer-panel { position: absolute; top: 0; left: -260px; width: 240px; height: 100%; background: #fff7fb; border-right: 1px solid rgba(255, 190, 210, 0.6); padding: 16px; transition: left 0.2s ease; display: flex; flex-direction: column; }
.drawer.open .drawer-panel { left: 0; }
.drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.drawer .brand { display: flex; gap: 10px; align-items: center; }
.drawer .brand .icon { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); width: 32px; height: 32px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.drawer .brand h1 { margin: 0; font-size: 16px; color: #ff4c8a;}
.drawer .brand p { margin: 0; font-size: 12px; color: #b6788d;}
/* ---- AI Workspace 核心内容 ---- */
.ai-main-card { margin: 24px 18px 12px; background: rgba(255,255,255,0.98); border-radius: 20px; box-shadow: 0 14px 32px rgba(255,165,199,0.16); padding: 16px 18px; display: flex; flex-direction: column; gap: 16px;}
.quick-prompt-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 5px;}
.chip { padding: 6px 10px; border-radius: 999px; background: #fff; border: 1px solid #ffd0e2; color: #c14e7a; cursor: pointer; margin-right: 4px;}
.ai-console { background: #fff7fb; border-radius: 14px; box-shadow: 0 4px 18px rgba(255, 190, 230, 0.12); padding: 16px 12px; display: flex; flex-direction: column; gap: 10px;}
.chat-area { flex: 1; overflow: auto; max-height: 400px; display: flex; flex-direction: column; gap: 14px; padding-right: 2px;}
.bubble { max-width: 680px; padding: 12px 14px; border-radius: 14px; background: #fff5f9; border: 1px solid #ffd7e8; box-shadow: 0 6px 18px rgba(255, 150, 190, 0.12);}
.bubble.user { margin-left: auto; background: #eef7ff; border-color: #cde2ff; box-shadow: 0 6px 18px rgba(140, 186, 255, 0.16);}
.role { font-size: 12px; color: #b16586; margin-bottom: 4px;}
.bubble.user .role { color: #6c8fd6; text-align: right; }
.content { white-space: pre-wrap; line-height: 1.6; color: #3d2b34;}
.thumbs { margin-top: 8px; display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px;}
.thumb { background: #fff; border: 1px solid #f3ddeb; border-radius: 12px; overflow: hidden; cursor: pointer; display: flex; flex-direction: column;}
.thumb img { width: 100%; height: 120px; object-fit: cover; background: #f7eef4;}
.caption { padding: 6px 8px; }
.name { font-size: 13px; color: #543849;}
.tags { font-size: 12px; color: #9a6b82;}
.input-bar { display: grid; grid-template-columns: 1fr 110px; gap: 8px; margin-top: 6px;}
textarea { width: 100%; border-radius: 12px; border: 1px solid #ffd7e8; padding: 10px; resize: vertical; font-size: 14px; outline: none;}
.send { border: none; border-radius: 12px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-weight: 600; cursor: pointer;}
.send:disabled { opacity: 0.7; cursor: not-allowed; }
.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding: 8px 0 16px;}
footer { text-align: center; font-size: 12px; color: #b57a90;}

@media (max-width: 1100px) { .ai-main-card { margin-inline: 12px; } }
@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .ai-main-card { margin-inline: 7px; padding-inline: 9px;}
}
@media (max-width: 640px) {
  .quick-prompt-row, .ai-console { padding: 6px 2px;}
  .input-bar { grid-template-columns: 1fr; }
  .bubble { padding: 9px 4px; }
  .ai-main-card { padding: 3px; }
  .topbar .right { display: none; }
}
</style>