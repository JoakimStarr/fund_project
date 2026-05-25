import request from '@/utils/request'

/**
 * 盘中估算相关 API
 */

// 获取最新盘中估算数据
export function getLatestIntraday(fundCode) {
  return request.get(`/fund/${fundCode}/intraday/latest`)
}

// 触发盘中估算计算
export function calculateIntraday(fundCode) {
  return request.post(`/fund/${fundCode}/intraday`)
}
