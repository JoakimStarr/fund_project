import request from './index'

export function predictFund(data) {
  return request.post('/fund/predict', data)
}

export function batchPredict(data) {
  return request.post('/fund/batch-predict', data)
}

export function getPredictionHistory(params) {
  return request.get('/dashboard/recent-predictions', { params })
}