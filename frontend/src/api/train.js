import request from './index'

export function createTask(data) {
  return request.post('/train', data)
}

export function getTaskStatus(taskId) {
  return request.get('/tasks/' + taskId)
}

export function listTasks(params) {
  return request.get('/tasks', { params })
}