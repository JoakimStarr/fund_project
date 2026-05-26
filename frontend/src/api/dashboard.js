import request from './index'

export function getStats() {
  return request.get('/dashboard/stats')
}

export function getRecentPredictions(params) {
  return request.get('/dashboard/recent-predictions', { params })
}