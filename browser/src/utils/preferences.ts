export type ThemeMode = 'pink' | 'dark' | 'eye'

const THEME_KEY = 'theme_mode'
const LANG_KEY = 'lang'

export function getThemeMode(): ThemeMode {
  const raw = (localStorage.getItem(THEME_KEY) || '').trim()
  if (raw === 'dark' || raw === 'eye' || raw === 'pink') return raw
  return 'pink'
}

export function applyThemeMode(mode: ThemeMode) {
  const root = document.documentElement
  root.classList.remove('theme-dark', 'theme-eye')
  if (mode === 'dark') root.classList.add('theme-dark')
  if (mode === 'eye') root.classList.add('theme-eye')
}

export function setThemeMode(mode: ThemeMode) {
  localStorage.setItem(THEME_KEY, mode)
  applyThemeMode(mode)
}

export type Language = 'zh-CN' | 'en'

export function getLanguage(): Language {
  const raw = (localStorage.getItem(LANG_KEY) || '').trim()
  if (raw === 'en' || raw === 'zh-CN') return raw
  return 'zh-CN'
}

export function applyLanguage(lang: Language) {
  if (typeof document === 'undefined') return
  document.documentElement.lang = lang
}

export function setLanguage(lang: Language) {
  localStorage.setItem(LANG_KEY, lang)
  applyLanguage(lang)
}
