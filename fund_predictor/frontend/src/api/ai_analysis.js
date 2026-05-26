import request from '@/utils/request'

/**
 * AI 分析相关 API
 */

// 获取AI分析（含新闻）
export function getAIAnalysis(fundCode, params) {
  return request.get(`/fund/${fundCode}/ai-analysis`, { params })
}

// 获取基金相关新闻列表
export function getFundNews(fundCode, params) {
  return request.get(`/fund/${fundCode}/news`, { params })
}

// AI Provider 可用性检测
export function getProviderStatus() {
  return request.get('/ai/provider-status')
}
