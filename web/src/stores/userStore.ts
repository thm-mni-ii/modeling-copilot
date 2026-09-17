import { defineStore } from 'pinia'
import { ref } from 'vue'
import authService from '@/services/auth/auth.service'

export const useUserStore = defineStore('user', () => {
  const globalRole = ref<string | null>(null)
  const userId = ref<string | null>(null)
  const loaded = ref(false)

  // Fetches the token claims from the backend only once, then serves them from state
  const ensureGlobalRole = async () => {
    if (!loaded.value) {
      try {
        const response = await authService.getMe()
        globalRole.value = response.data.globalRole ?? null
        userId.value = response.data.id === undefined || response.data.id === null ? null : String(response.data.id)
      } catch {
        globalRole.value = null
        userId.value = null
      }
      loaded.value = true
    }
    return globalRole.value
  }

  const reset = () => {
    globalRole.value = null
    userId.value = null
    loaded.value = false
  }

  return { globalRole, userId, loaded, ensureGlobalRole, reset }
})
