import request from '@/utils/request'

/**
 * 模型监控 API
 */

// 获取模型健康状态
export function getModelHealth() {
  return request.get('/model/health')
}

// 获取回测服务状态
export function getBacktestHealth() {
  return request.get('/backtest/health')
}
