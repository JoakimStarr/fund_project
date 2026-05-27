import request from '@/utils/request'

/**
 * 基金相关 API
 */

// 预测基金净值
export function predictFund(data) {
  return request.post('/fund/predict', data)
}

// 获取基金画像
export function getFundProfile(fundCode) {
  return request.get(`/fund/${fundCode}/profile`)
}

// 获取模型信息
export function getModelInfo(fundCode) {
  return request.get(`/fund/${fundCode}/model`)
}

// 获取回测数据
export function getBacktestData(fundCode) {
  return request.get(`/fund/${fundCode}/backtest`)
}
