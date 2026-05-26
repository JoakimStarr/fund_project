import { defineStore } from 'pinia'
import { ref } from 'vue'
import { validateFundCode, searchFunds, getProfile } from '@/api/fund'

export const useFundStore = defineStore('fund', () => {
  const currentFundCode = ref('')
  const validatedFund = ref(null)
  const searchResults = ref([])
  const profile = ref(null)

  async function validateFund(rawInput) {
    const data = await validateFundCode(rawInput)
    validatedFund.value = data
    return data
  }

  async function searchFundsAction(query) {
    const data = await searchFunds(query)
    searchResults.value = data?.results || data || []
    return searchResults.value
  }

  async function fetchProfile(code) {
    const data = await getProfile(code)
    profile.value = data
    return data
  }

  return {
    currentFundCode,
    validatedFund,
    searchResults,
    profile,
    validateFund,
    searchFunds: searchFundsAction,
    fetchProfile
  }
})