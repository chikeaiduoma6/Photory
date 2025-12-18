import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { usePreferencesStore } from '@/stores/preferences'

export function useLocale() {
  const preferencesStore = usePreferencesStore()
  const { language } = storeToRefs(preferencesStore)
  const isEnglish = computed(() => language.value === 'en')
  const text = (zhCN: string, en: string) => (isEnglish.value ? en : zhCN)
  return { language, isEnglish, text }
}

