import request from '@/utils/request'

/**
 * 训练相关 API
 */

// 触发训练任务
export function startTraining(data) {
  return request.post('/train', data)
}
