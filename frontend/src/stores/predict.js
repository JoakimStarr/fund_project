import { defineStore } from 'pinia'
import { ref } from 'vue'
import { predictFund } from '@/api/predict'

export const usePredictStore = defineStore('predict', () => {
  const predictionResult = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function predictFundAction(data) {
    loading.value = true
    error.value = null
    predictionResult.value = null
    try {
      const result = await predictFund(data)
      predictionResult.value = result
      return result
    } catch (e) {
      error.value = e
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearResult() {
    predictionResult.value = null
    error.value = null
  }

  return {
    predictionResult,
    loading,
    error,
    predictFund: predictFundAction,
    clearResult
  }
})