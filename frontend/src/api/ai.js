import request from './index'

export function getAiAnalysis(data) {
  return request.post('/ai/analysis', data)
}

export function getProviderStatus() {
  return request.get('/ai/provider-status')
}