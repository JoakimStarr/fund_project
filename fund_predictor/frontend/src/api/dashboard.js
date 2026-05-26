import request from '@/utils/request'

/**
 * 仪表盘相关 API
 */

// 获取统计数据
export function getDashboardStats() {
  return request.get('/dashboard/stats')
}

// 获取最近预测记录
export function getRecentPredictions(params = {}) {
  const { limit = 10 } = params
  return request.get(`/dashboard/recent-predictions?limit=${limit}`)
}

// 获取模型列表
export function getModelList() {
  return request.get('/dashboard/models')
}

// 获取系统资源使用情况
export function getSystemResources() {
  return request.get('/dashboard/system-resources')
}
