<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { type Language, type ThemeMode } from '@/utils/preferences'
import { usePreferencesStore } from '@/stores/preferences'
import { getNavLinks } from '@/utils/navLinks'

const router = useRouter()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '访客')

const preferencesStore = usePreferencesStore()
const { themeMode, language } = storeToRefs(preferencesStore)
const links = computed(() => getNavLinks(language.value))
const navOpen = ref(false)
const currentPath = computed(() => router.currentRoute.value.path)
const go = (path: string) => {
  router.push(path)
  navOpen.value = false
}
const isActive = (path: string) => currentPath.value === path || currentPath.value.startsWith(path + '/')
const toggleNav = () => (navOpen.value = !navOpen.value)
const closeNav = () => (navOpen.value = false)

type LoginEvent = { id: number; ip?: string | null; user_agent?: string | null; created_at?: string | null }
const email = computed(() => authStore.user?.email || '')
const loginEvents = ref<LoginEvent[]>([])
const quota = ref<{ image_count: number; used_bytes: number } | null>(null)
const loading = ref(false)

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPwd = ref(false)

const isEnglish = computed(() => language.value === 'en')
const t = computed(() => {
  if (!isEnglish.value) {
    return {
      title: '设置',
      subtitle: '管理账号、安全、存储与外观',
      hello: (name: string) => `管理账号、安全、存储与外观 · 你好，${name}。`,
      logout: '退出登录',
      refresh: '刷新',
      refreshing: '刷新中…',
      sectionAccount: '账号与安全',
      sectionAccountSub: '用户名 / 邮箱 · 修改密码 · 最近登录设备记录',
      accountInfo: '账户信息',
      username: '用户名',
      email: '邮箱',
      changePwd: '修改密码',
      currentPwd: '当前密码',
      newPwd: '新密码（至少 6 位，含字母与数字）',
      confirmPwd: '确认新密码',
      updatePwd: '更新密码',
      submitting: '提交中…',
      lastLogin: '上一次设备登录记录',
      noLogin: '暂无登录记录',
      time: '时间',
      ip: 'IP',
      device: '设备',
      storage: '存储与配额',
      storageSub: '当前图片数量与已用空间（不含回收站）',
      imageCount: '图片数量',
      usedSpace: '已用空间',
      appearance: '外观与体验',
      appearanceSub: '主题色 / 亮暗模式 / 护眼模式 · 系统语言',
      themeColor: '主题色',
      themeFixed: '提示：当前项目主色固定为粉色。',
      displayMode: '显示模式',
      modeLight: '亮色',
      modeDark: '暗色',
      modeEye: '护眼',
      modeHint: '提示：暗色/护眼会影响所有页面背景与对比度。',
      language: '系统语言',
      chinese: '中文',
      english: 'English',
      langHint: '提示：语言切换已保存偏好，界面多语言将在后续版本完善。',
    }
  }
  return {
    title: 'Settings',
    subtitle: 'Account, security, storage and appearance',
    hello: (name: string) => `Account, security, storage and appearance · Hi, ${name}.`,
    logout: 'Log out',
    refresh: 'Refresh',
    refreshing: 'Refreshing…',
    sectionAccount: 'Account & Security',
    sectionAccountSub: 'Username / Email · Change password · Latest login device',
    accountInfo: 'Account',
    username: 'Username',
    email: 'Email',
    changePwd: 'Change Password',
    currentPwd: 'Current password',
    newPwd: 'New password (min 6, letters + digits)',
    confirmPwd: 'Confirm new password',
    updatePwd: 'Update password',
    submitting: 'Submitting…',
    lastLogin: 'Latest login device',
    noLogin: 'No login events yet',
    time: 'Time',
    ip: 'IP',
    device: 'Device',
    storage: 'Storage & Quota',
    storageSub: 'Image count and used space (excluding recycle bin)',
    imageCount: 'Images',
    usedSpace: 'Used space',
    appearance: 'Appearance',
    appearanceSub: 'Theme / Dark mode / Eye comfort · Language',
    themeColor: 'Theme color',
    themeFixed: 'Note: the main theme color is fixed to pink.',
    displayMode: 'Display mode',
    modeLight: 'Light',
    modeDark: 'Dark',
    modeEye: 'Eye comfort',
    modeHint: 'Note: Dark/Eye mode affects all pages.',
    language: 'Language',
    chinese: '中文',
    english: 'English',
    langHint: 'Note: preference is saved; full i18n will be improved later.',
  }
})

function setTheme(mode: ThemeMode) {
  preferencesStore.setThemeMode(mode)
}
function setLang(lang: Language) {
  preferencesStore.setLanguage(lang)
  ElMessage.success(lang === 'en' ? 'Language updated' : '语言已切换')
}

function formatBytes(bytes: number) {
  const b = Math.max(0, bytes || 0)
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let idx = 0
  let val = b
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024
    idx += 1
  }
  return `${val.toFixed(idx === 0 ? 0 : 2)} ${units[idx]}`
}

async function refresh() {
  loading.value = true
  try {
    const [meRes, quotaRes] = await Promise.all([
      axios.get('/api/v1/auth/me'),
      axios.get('/api/v1/images/quota'),
    ])
    if (meRes.data?.user) authStore.user = meRes.data.user
    loginEvents.value = (meRes.data?.login_events || []) as LoginEvent[]
    quota.value = quotaRes.data || null
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '加载设置失败')
  } finally {
    loading.value = false
  }
}

async function changePassword() {
  if (!currentPassword.value || !newPassword.value) return
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次新密码不一致')
    return
  }
  changingPwd.value = true
  try {
    await axios.post('/api/v1/auth/change-password', {
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    ElMessage.success('密码已更新')
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '修改密码失败')
  } finally {
    changingPwd.value = false
  }
}

function logout() {
  authStore.logout()
  router.push('/auth/login')
}

onMounted(() => {
  refresh()
})
</script>

<template>
  <div class="dashboard settings-page">
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
          <span class="logo-mini">⚙️</span>
          <span>{{ t.title }}</span>
        </div>
        <button class="icon-btn ghost" @click="go('/')">🏠</button>
      </header>

      <header class="topbar">
        <div class="left">
          <div class="title">{{ t.title }}</div>
          <div class="subtitle">{{ t.hello(username) }}</div>
        </div>
        <div class="right">
          <button class="pill danger" @click="logout">{{ t.logout }}</button>
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
                <p>{{ t.title }}</p>
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

      <section class="settings-card">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t.sectionAccount }}</div>
            <div class="section-sub">{{ t.sectionAccountSub }}</div>
          </div>
          <button class="pill ghost" :disabled="loading" @click="refresh">{{ loading ? t.refreshing : t.refresh }}</button>
        </div>

        <div class="grid two">
          <div class="panel">
            <div class="panel-title">{{ t.accountInfo }}</div>
            <div class="kv">
              <div class="k">{{ t.username }}</div>
              <div class="v">{{ username }}</div>
            </div>
            <div class="kv">
              <div class="k">{{ t.email }}</div>
              <div class="v">{{ email || '—' }}</div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-title">{{ t.changePwd }}</div>
            <div class="form">
              <input v-model="currentPassword" type="password" :placeholder="t.currentPwd" />
              <input v-model="newPassword" type="password" :placeholder="t.newPwd" />
              <input v-model="confirmPassword" type="password" :placeholder="t.confirmPwd" />
              <button class="pill primary" :disabled="changingPwd" @click="changePassword">
                {{ changingPwd ? t.submitting : t.updatePwd }}
              </button>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title">{{ t.lastLogin }}</div>
          <div v-if="!loginEvents.length" class="empty">{{ t.noLogin }}</div>
          <div v-else class="login-list">
            <div v-for="e in loginEvents.slice(0, 1)" :key="e.id" class="login-item">
              <div class="login-main">
                <div class="login-line">
                  <span class="label">{{ t.time }}</span>
                  <span class="value">{{ e.created_at ? new Date(e.created_at).toLocaleString() : '—' }}</span>
                </div>
                <div class="login-line">
                  <span class="label">{{ t.ip }}</span>
                  <span class="value">{{ e.ip || '—' }}</span>
                </div>
                <div class="login-line">
                  <span class="label">{{ t.device }}</span>
                  <span class="value ua">{{ e.user_agent || '—' }}</span>
                </div>
              </div>
            </div>
            <div v-if="loginEvents.length > 1" class="more-tip">更多记录会在后续版本支持展示。</div>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t.storage }}</div>
            <div class="section-sub">{{ t.storageSub }}</div>
          </div>
        </div>

        <div class="grid two">
          <div class="panel">
            <div class="panel-title">{{ t.imageCount }}</div>
            <div class="big">{{ quota?.image_count ?? '—' }}</div>
          </div>
          <div class="panel">
            <div class="panel-title">{{ t.usedSpace }}</div>
            <div class="big">{{ quota ? formatBytes(quota.used_bytes) : '—' }}</div>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t.appearance }}</div>
            <div class="section-sub">{{ t.appearanceSub }}</div>
          </div>
        </div>

        <div class="grid two">
          <div class="panel">
            <div class="panel-title">{{ t.themeColor }}</div>
            <div class="seg">
              <button class="seg-btn active" disabled>粉色</button>
            </div>
            <div class="hint">{{ t.themeFixed }}</div>
          </div>

          <div class="panel">
            <div class="panel-title">{{ t.displayMode }}</div>
            <div class="seg">
              <button class="seg-btn" :class="{ active: themeMode === 'pink' }" @click="setTheme('pink')">{{ t.modeLight }}</button>
              <button class="seg-btn" :class="{ active: themeMode === 'dark' }" @click="setTheme('dark')">{{ t.modeDark }}</button>
              <button class="seg-btn" :class="{ active: themeMode === 'eye' }" @click="setTheme('eye')">{{ t.modeEye }}</button>
            </div>
            <div class="hint">{{ t.modeHint }}</div>
          </div>

          <div class="panel">
            <div class="panel-title">{{ t.language }}</div>
            <div class="seg">
              <button class="seg-btn" :class="{ active: language === 'zh-CN' }" @click="setLang('zh-CN')">{{ t.chinese }}</button>
              <button class="seg-btn" :class="{ active: language === 'en' }" @click="setLang('en')">{{ t.english }}</button>
            </div>
            <div class="hint">{{ t.langHint }}</div>
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
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #ffeef5, #ffe5f0);
  color: #4b2b3a;
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
.topbar .title { font-weight: 700; color: #ff4c8a; font-size: 18px;}
.subtitle { font-size: 12px; color: #a36e84; }
.right { display: flex; align-items: center; gap: 8px; }

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

.settings-card { margin: 18px 18px 0; background: rgba(255,255,255,0.98); border-radius: 20px; box-shadow: 0 14px 32px rgba(255,165,199,0.16); padding: 16px 18px; display: flex; flex-direction: column; gap: 12px;}
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.section-title { font-weight: 800; color: #d2517f; font-size: 16px; }
.section-sub { font-size: 12px; color: #9a6b82; margin-top: 2px; }

.grid { display: grid; gap: 12px; }
.grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.panel { background: #fff7fb; border: 1px solid rgba(255, 210, 230, 0.8); border-radius: 16px; padding: 12px 12px; }
.panel-title { font-weight: 700; color: #ff4c8a; margin-bottom: 10px; }
.kv { display: grid; grid-template-columns: 84px 1fr; gap: 10px; padding: 6px 0; }
.k { font-size: 12px; color: #9a6b82; }
.v { font-size: 13px; color: #4b2b3a; }

.form { display: grid; gap: 10px; }
input { width: 100%; border-radius: 12px; border: 1px solid #ffd7e8; padding: 10px; font-size: 14px; outline: none; background: rgba(255,255,255,0.95); }
.pill { border: none; border-radius: 999px; padding: 8px 12px; cursor: pointer; font-weight: 700; }
.pill.primary { background: linear-gradient(135deg, #ff8bb3, #ff6fa0); color: #fff; }
.pill.ghost { background: rgba(255,255,255,0.65); border: 1px solid rgba(255, 190, 210, 0.7); color: #c14e7a; }
.pill.danger { background: rgba(255, 60, 120, 0.08); border: 1px solid rgba(255, 60, 120, 0.25); color: #ff3c78; }
.pill:disabled { opacity: 0.7; cursor: not-allowed; }

.login-list { display: flex; flex-direction: column; gap: 10px; }
.login-item { background: rgba(255,255,255,0.85); border: 1px solid rgba(255, 210, 230, 0.7); border-radius: 14px; padding: 10px; }
.login-line { display: grid; grid-template-columns: 42px 1fr; gap: 10px; padding: 4px 0; }
.label { font-size: 12px; color: #9a6b82; }
.value { font-size: 12px; color: #4b2b3a; }
.ua { word-break: break-word; }
.more-tip { font-size: 12px; color: #9a6b82; margin-top: 6px; }
.empty { font-size: 12px; color: #9a6b82; padding: 8px 0; }
.big { font-size: 26px; font-weight: 900; color: #ff4c8a; letter-spacing: 0.2px; }

.seg { display: flex; flex-wrap: wrap; gap: 8px; }
.seg-btn { border: 1px solid rgba(255, 190, 210, 0.9); background: #fff; color: #7a3a52; border-radius: 12px; padding: 8px 10px; cursor: pointer; font-weight: 700; font-size: 13px; }
.seg-btn.active { background: rgba(255, 153, 187, 0.16); border-color: rgba(255, 125, 170, 0.9); color: #ff4c8a; }
.hint { font-size: 12px; color: #9a6b82; margin-top: 10px; }

.footer-wrapper { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-top: auto; padding: 16px 0 16px;}
footer { text-align: center; font-size: 12px; color: #b57a90;}

@media (max-width: 1100px) { .settings-card { margin-inline: 12px; } }
@media (max-width: 900px) {
  .sidebar { display: none; }
  .mobile-topbar { display: flex; }
  .topbar { padding: 12px 16px; }
  .settings-card { margin-inline: 7px; padding-inline: 9px;}
  .grid.two { grid-template-columns: 1fr; }
}
</style>
