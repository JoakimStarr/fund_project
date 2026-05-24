import request from '@/utils/request'

/**
 * 任务相关 API
 */

// 获取任务状态
export function getTaskStatus(taskId) {
  return request.get(`/tasks/${taskId}`)
}
