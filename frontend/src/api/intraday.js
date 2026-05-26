import request from './index'

export function getIntradayEstimate(code, data) {
  return request.post('/intraday/' + code, data || {})
}