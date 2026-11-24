import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '@/api/modules/auth'
import { TOKEN_KEY } from '@/api/request'
import type { LoginRequest, User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const currentUser = ref<User | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdmin = computed(() => {
    const user = currentUser.value
    if (!user) return false
    if (user.is_superuser) return true
    return Boolean(user.roles?.some((role) => role.code === 'admin'))
  })
  const displayName = computed(
    () => currentUser.value?.display_name || currentUser.value?.username || '未登录',
  )

  async function login(payload: LoginRequest) {
    loading.value = true
    try {
      const result = await authApi.login(payload)
      token.value = result.access_token
      localStorage.setItem(TOKEN_KEY, result.access_token)
      currentUser.value = result.user ?? null
      return result
    } finally {
      loading.value = false
    }
  }

  async function fetchMe(): Promise<User | null> {
    if (!token.value) return null
    try {
      currentUser.value = await authApi.getMe()
      return currentUser.value
    } catch {
      logout()
      return null
    }
  }

  function logout() {
    token.value = ''
    currentUser.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  function hasRole(code: string): boolean {
    if (isAdmin.value) return true
    return Boolean(currentUser.value?.roles?.some((role) => role.code === code))
  }

  return {
    token,
    currentUser,
    loading,
    isAuthenticated,
    isAdmin,
    displayName,
    login,
    fetchMe,
    logout,
    hasRole,
  }
})
