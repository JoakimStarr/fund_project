import request from './index'

export function predictFund(data) {
  return request.post('/predict', data)
}

export function batchPredict(data) {
  return request.post('/predict/batch', data)
}

export function getPredictionHistory(params) {
  return request.get('/predict/history', { params })
}