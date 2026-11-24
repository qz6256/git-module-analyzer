import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type Theme = 'dark' | 'light'

const THEME_KEY = 'gma_theme'

export const useUiStore = defineStore('ui', () => {
  const theme = ref<Theme>('dark')
  const sidebarCollapsed = ref(false)
  const isDark = computed(() => theme.value === 'dark')

  function applyTheme() {
    const root = document.documentElement
    root.setAttribute('data-theme', theme.value)
    // Element Plus 的暗色 css-vars 以 .dark 类生效
    root.classList.toggle('dark', theme.value === 'dark')
    localStorage.setItem(THEME_KEY, theme.value)
  }

  function initTheme() {
    const stored = localStorage.getItem(THEME_KEY)
    theme.value = stored === 'light' ? 'light' : 'dark'
    applyTheme()
  }

  function setTheme(next: Theme) {
    theme.value = next
    applyTheme()
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return { theme, isDark, sidebarCollapsed, initTheme, setTheme, toggleTheme, toggleSidebar }
})
