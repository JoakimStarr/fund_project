import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 全局加载状态
  const loading = ref(false)
  const loadingText = ref('')

  // 当前选中的基金代码
  const currentFundCode = ref('018956')

  // 全局消息提示
  const showMessage = (message, type = 'success') => {
    // 使用 Element Plus 的 ElMessage
    if (window.ElMessage) {
      window.ElMessage({ message, type, duration: 3000 })
    }
  }

  // 设置加载状态
  const setLoading = (isLoading, text = '') => {
    loading.value = isLoading
    loadingText.value = text
  }

  // 设置当前基金
  const setCurrentFundCode = (code) => {
    currentFundCode.value = code
  }

  return {
    loading,
    loadingText,
    currentFundCode,
    showMessage,
    setLoading,
    setCurrentFundCode
  }
})
