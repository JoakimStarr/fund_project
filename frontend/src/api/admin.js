import request from './index'

export function getDataStatus() {
  return request.get('/admin/data-status')
}

export function updateData(data) {
  return request.post('/admin/update-data', data || {})
}