<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')
const apiBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const withBase = (p: string) => (!p ? '' : p.startsWith('http') ? p : `${apiBase}${p}`)
const tokenParam = computed(() => (authStore.token ? `?jwt=${authStore.token}` : ''))

interface ChatMessage { role: 'user' | 'assistant'; content: string; images?: any[] }
const messages = ref<ChatMessage[]>([
  { role: 'assistant', content: '你好呀，我是你的专属AI图片小助手，可以帮你检索图片哦' },
])
const input = ref('在这里输入你的问题...')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const sending = ref(false)
const scrollRef = ref<HTMLDivElement | null>(null)
const quickPrompts = [
  '请帮我找几张包含花朵的图片',
  '有哪些日落主题的图片？',
  '请列出2025-12-4上传的图片',
]

type HintGroup = { title: string; desc: string; examples: string[] }
const hintsOpen = ref(true)
const hintGroups: HintGroup[] = [
  {
    title: '组合逻辑（AND / OR）',
    desc: '用“并且/同时/以及”做交集，用“或者/或/还是”做并集；支持混合：A 或者 B 并且 C = A OR (B AND C)。',
    examples: [
      '在风景相册里并且上传于2025-12-4并且文件大小小于300KB',
      '上传于2025-12-4或者在风景相册里',
      '在风景相册里或者上传于2025-12-4并且cute',
    ],
  },
  {
    title: '相册 / 文件夹',
    desc: '支持“在…相册/专辑/文件夹里/中”，也支持引号与英文写法。',
    examples: ['在风景相册里', '请找在名为“风景”的相册中的图片', 'album: 风景'],
  },
  {
    title: '时间（上传 / 拍摄）',
    desc: '“上传/上传于”会触发上传时间过滤，“拍摄/摄于”会触发拍摄时间过滤，日期支持多种格式。',
    examples: ['请列出2025-12-4上传的图片', '拍摄于2025年12月4日的照片', '上传于2025/12/4并且日落'],
  },
  {
    title: '文件大小',
    desc: '必须带单位（KB/MB/GB/兆），支持小于/大于/区间。',
    examples: ['文件大小小于300KB的图片', '找大于2MB的图片', '找300KB-2MB之间的图片并且在风景相册里'],
  },
  {
    title: '分辨率',
    desc: '支持“宽x高”、像素/px、4k/2k/1080p 等写法（按至少阈值过滤）。',
    examples: ['分辨率大于1920x1080的图片', '4k并且小于2MB', '1080p并且日落'],
  },
  {
    title: '相机 / 镜头',
    desc: '支持“相机…/镜头…”或“用…拍的”。',
    examples: ['用iPhone拍的图片', '相机 Nikon 并且 4k', '镜头 24-70 并且 拍摄于2025-12-4'],
  },
  {
    title: 'AI 标签 / AI 描述',
    desc: '如果图片已生成 AI 标签/描述，也可以用关键词匹配到。',
    examples: ['AI描述里包含“树木”的图片', 'AI标签包含“sunset”的图片', 'AI描述里包含“海边”并且在风景相册里'],
  },
  {
    title: '图片关键词（名称/标签/描述）',
    desc: '支持图片名称、自定义标签、自定义描述的关键词匹配，也支持 #标签。',
    examples: ['日落', '#日落', '在风景相册里并且日落并且小于1MB'],
  },
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
function fillPrompt(p: string) {
  input.value = p
  nextTick(() => inputRef.value?.focus())
}
async function copyPrompt(p: string) {
  try {
    await navigator.clipboard.writeText(p)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}
function openImage(id: number) {
  router.push(`/images/${id}`)
}
const preferencesStore = usePreferencesStore()
const links = computed(() => getNavLinks(preferencesStore.language))
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

        <section class="hint-card">
          <header class="hint-head">
            <div class="hint-left">
              <div class="hint-title">
                <span class="hint-badge">问法提示</span>
                <span class="hint-sub">结构化条件 + 关键词 + AI 标签/描述 + AND/OR 组合</span>
              </div>
              <div class="hint-tip">点击示例会填入输入框（不自动发送）；双击示例可直接查询。</div>
            </div>
            <div class="hint-actions">
              <button type="button" class="hint-btn ghost" @click="hintsOpen = !hintsOpen">
                {{ hintsOpen ? '收起' : '展开' }}
              </button>
            </div>
          </header>

          <transition name="hint-fade">
            <div v-if="hintsOpen" class="hint-body">
              <div class="hint-grid">
                <div v-for="g in hintGroups" :key="g.title" class="hint-group">
                  <div class="hint-group-title">{{ g.title }}</div>
                  <div class="hint-group-desc">{{ g.desc }}</div>
                  <div class="hint-chips">
                    <button
                      v-for="ex in g.examples"
                      :key="ex"
                      type="button"
                      class="hint-chip"
                      @click="fillPrompt(ex)"
                      @dblclick="usePrompt(ex)"
                      :title="ex"
                    >
                      {{ ex }}
                    </button>
                  </div>
                  <div class="hint-row">
                    <button type="button" class="hint-mini" :disabled="!g.examples.length" @click="copyPrompt(g.examples[0]!)">复制本组首条</button>
                  </div>
                </div>
              </div>
            </div>
          </transition>
        </section>

        <div class="ai-console">
          <div class="chat-area" ref="scrollRef">
            <div v-for="(m, idx) in messages" :key="idx" class="bubble" :class="m.role">
              <div class="role">{{ m.role === 'user' ? '你' : 'AI' }}</div>
              <div class="content" v-html="m.content.replace(/\n/g, '<br/>')"></div>
              <div v-if="m.images?.length" class="thumbs">
                <div v-for="img in m.images" :key="img.id" class="thumb" @click="openImage(img.id)">
                  <img :src="withBase(img.thumb_url || `/api/v1/images/${img.id}/thumb`) + tokenParam" loading="lazy" />
                  <div class="caption">
                    <div class="name">{{ img.name }}</div>
                    <div class="tags">{{ (img.tags || []).slice(0,3).join(' · ') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="input-bar">
            <textarea ref="inputRef" v-model="input" :disabled="sending" rows="2" placeholder="和 AI 说点什么吧…"></textarea>
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
.hint-card { background: linear-gradient(180deg, rgba(255,245,250,0.92), rgba(255,255,255,0.96)); border: 1px solid rgba(255, 200, 220, 0.8); border-radius: 16px; box-shadow: 0 10px 26px rgba(255, 160, 200, 0.12); padding: 12px 12px; }
.hint-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.hint-left { display: flex; flex-direction: column; gap: 6px; }
.hint-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.hint-badge { display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; font-weight: 700; font-size: 12px; letter-spacing: 0.5px; }
.hint-sub { font-size: 12px; color: #a36e84; }
.hint-tip { font-size: 12px; color: #8c546e; }
.hint-actions { display: flex; align-items: center; gap: 8px; }
.hint-btn { border: 1px solid rgba(255, 190, 210, 0.9); background: #fff; color: #c14e7a; border-radius: 999px; padding: 6px 10px; cursor: pointer; font-weight: 600; }
.hint-btn.ghost { background: rgba(255,255,255,0.65); }
.hint-body { margin-top: 10px; }
.hint-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.hint-group { background: rgba(255,255,255,0.9); border: 1px solid rgba(255, 210, 230, 0.8); border-radius: 14px; padding: 10px 10px; }
.hint-group-title { font-weight: 700; color: #d2517f; font-size: 13px; }
.hint-group-desc { font-size: 12px; color: #9a6b82; margin-top: 4px; line-height: 1.45; }
.hint-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.hint-chip { max-width: 100%; text-align: left; border: 1px solid #ffd0e2; background: #fff; color: #7a3a52; border-radius: 12px; padding: 8px 10px; cursor: pointer; font-size: 12px; line-height: 1.35; box-shadow: 0 6px 14px rgba(255, 170, 210, 0.10); }
.hint-chip:hover { border-color: rgba(255, 125, 170, 0.95); box-shadow: 0 8px 18px rgba(255, 150, 195, 0.16); }
.hint-row { display: flex; justify-content: flex-end; margin-top: 8px; }
.hint-mini { border: none; background: transparent; color: #c14e7a; cursor: pointer; font-size: 12px; text-decoration: underline; padding: 4px 0; }
.hint-mini:disabled { opacity: 0.6; cursor: not-allowed; text-decoration: none; }
.hint-fade-enter-active, .hint-fade-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.hint-fade-enter-from, .hint-fade-leave-to { opacity: 0; transform: translateY(-6px); }
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
  .hint-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .quick-prompt-row, .ai-console { padding: 6px 2px;}
  .input-bar { grid-template-columns: 1fr; }
  .bubble { padding: 9px 4px; }
  .ai-main-card { padding: 3px; }
  .topbar .right { display: none; }
}
</style>
