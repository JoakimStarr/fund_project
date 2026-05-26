import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMarketSession } from '@/utils/marketTime'
import { getProviderStatus } from '@/api/ai'

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const sidebarCollapsed = ref(false)
  const marketSession = ref(getMarketSession())
  const aiProviderStatus = ref(null)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function updateMarketSession() {
    marketSession.value = getMarketSession()
  }

  async function fetchAiProviderStatus() {
    try {
      const data = await getProviderStatus()
      aiProviderStatus.value = data
    } catch {
      aiProviderStatus.value = { available: false }
    }
  }

  return {
    loading,
    sidebarCollapsed,
    marketSession,
    aiProviderStatus,
    toggleSidebar,
    updateMarketSession,
    fetchAiProviderStatus
  }
})