import request from '@/utils/request'

/**
 * 任务相关 API
 */

// 获取任务状态
export function getTaskStatus(taskId) {
  return request.get(`/tasks/${taskId}`)
}

// 获取历史训练任务列表
export function getTasksHistory(params = {}) {
  const { fundCode, limit = 50 } = params
  const queryParams = new URLSearchParams()
  if (fundCode) {
    queryParams.append('fund_code', fundCode)
  }
  if (limit) {
    queryParams.append('limit', limit.toString())
  }
  
  const queryString = queryParams.toString()
  return request.get(`/tasks${queryString ? `?${queryString}` : ''}`)
}
