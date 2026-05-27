import request from './index'

export function getIntradayEstimate(code, data) {
  return request.post('/intraday/' + code, data || {})
}

export function saveIntradayEstimate(code) {
  return request.post('/intraday/' + code + '/save')
}
