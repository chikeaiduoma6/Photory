import type { Language } from './preferences'

export type NavLink = { label: string; icon: string; path: string }

const NAV_LABELS: Record<Language, Record<string, string>> = {
  'zh-CN': {
    home: '首页',
    search: '搜索引擎',
    upload: '上传中心',
    tags: '标签',
    albums: '相册',
    ai: 'AI 工作台',
    recycle: '回收站',
    settings: '设置',
  },
  en: {
    home: 'Home',
    search: 'Search',
    upload: 'Upload',
    tags: 'Tags',
    albums: 'Albums',
    ai: 'AI Workspace',
    recycle: 'Recycle Bin',
    settings: 'Settings',
  },
}

export function getNavLinks(lang: Language): NavLink[] {
  const t = NAV_LABELS[lang] ?? NAV_LABELS['zh-CN']
  return [
    { label: t.home, icon: '🏠', path: '/' },
    { label: t.search, icon: '🔎', path: '/search' },
    { label: t.upload, icon: '☁️', path: '/upload' },
    { label: t.tags, icon: '🏷️', path: '/tags' },
    { label: t.albums, icon: '📚', path: '/albums' },
    { label: t.ai, icon: '🤖', path: '/ai' },
    { label: t.recycle, icon: '🗑️', path: '/recycle' },
    { label: t.settings, icon: '⚙️', path: '/settings' },
  ]
}
