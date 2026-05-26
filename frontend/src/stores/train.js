import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createTask, getTaskStatus, listTasks } from '@/api/train'

export const useTrainStore = defineStore('train', () => {
  const taskStatus = ref(null)
  const taskHistory = ref([])
  const progress = ref(0)

  async function createTaskAction(data) {
    const result = await createTask(data)
    if (result && result.task_id) {
      taskStatus.value = result
      progress.value = 0
    }
    return result
  }

  async function pollTaskStatus(taskId) {
    const data = await getTaskStatus(taskId)
    taskStatus.value = data
    if (data && data.progress != null) {
      progress.value = data.progress
    }
    return data
  }

  async function fetchHistory(params) {
    const data = await listTasks(params)
    taskHistory.value = data?.tasks || data || []
    return taskHistory.value
  }

  return {
    taskStatus,
    taskHistory,
    progress,
    createTask: createTaskAction,
    pollTaskStatus,
    fetchHistory
  }
})