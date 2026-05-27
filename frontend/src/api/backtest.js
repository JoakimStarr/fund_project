import request from './index'

export function getBacktest(code, params) {
  return request.get('/backtest/' + code, { params })
}