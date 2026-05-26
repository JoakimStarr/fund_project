import request from './index'

export function getBacktest(code, params) {
  return request.get('/fund/' + code + '/backtest', { params })
}