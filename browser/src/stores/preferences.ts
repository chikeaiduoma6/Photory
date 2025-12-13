import { defineStore } from 'pinia'
import {
  getLanguage,
  getThemeMode,
  setLanguage as persistLanguage,
  setThemeMode as persistThemeMode,
  type Language,
  type ThemeMode,
} from '../utils/preferences'

export const usePreferencesStore = defineStore('preferences', {
  state: () => ({
    themeMode: getThemeMode() as ThemeMode,
    language: getLanguage() as Language,
  }),
  actions: {
    setThemeMode(mode: ThemeMode) {
      this.themeMode = mode
      persistThemeMode(mode)
    },
    setLanguage(lang: Language) {
      this.language = lang
      persistLanguage(lang)
    },
  },
})
