import request from './index'

export function predictFund(data) {
  return request.post('/fund/predict', data)
}

export function validateFundCode(rawInput) {
  return request.post('/fund/validate', { raw_input: rawInput })
}

export function searchFunds(query) {
  return request.get('/fund/search', { params: { q: query } })
}

export function getProfile(code) {
  return request.get('/fund/' + code + '/profile')
}

export function getNews(code, params) {
  return request.get('/fund/' + code + '/news', { params })
}

export function batchPredict(data) {
  return request.post('/fund/batch-predict', data)
}

export function getBacktest(code, params) {
  return request.get('/fund/' + code + '/backtest', { params })
}

export function rollbackModel(code, data) {
  return request.post('/fund/' + code + '/rollback', data)
}