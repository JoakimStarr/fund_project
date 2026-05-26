<template>
  <div style="max-width:900px;margin:0 auto">
    <h2>模型训练</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:center">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码"
          clearable
          style="flex:1"
          @keyup.enter="startTrain"
          @select="handleSelect"
        />
        <el-checkbox v-model="forceRetrain" label="强制重训" border size="small" />
        <el-button type="primary" :loading="training" @click="startTrain">开始训练</el-button>
      </div>
    </el-card>

    <template v-if="trainStore.taskStatus">
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">训练进度</span></template>
        <el-progress
          :percentage="trainStore.progress"
          :status="progressStatus"
          :stroke-width="20"
          style="margin-bottom:12px"
        >
          <span style="font-size:13px">{{ stageText }}</span>
        </el-progress>
        <div
          ref="logRef"
          style="background:#1d1e1f;color:#c9d1d9;padding:12px;border-radius:4px;font-size:12px;font-family:monospace;height:200px;overflow-y:auto;white-space:pre-wrap"
        >
          <div v-for="(line, i) in logLines" :key="i">{{ line }}</div>
        </div>
      </el-card>
    </template>

    <el-card v-if="trainResult" shadow="never" style="margin-bottom:16px">
      <template #header><span style="font-weight:600">训练结果</span></template>
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="方向准确率">
          {{ trainResult.direction_accuracy != null ? (trainResult.direction_accuracy * 100).toFixed(1) + '%' : '--' }}
        </el-descriptions-item>
        <el-descriptions-item label="MAE">{{ trainResult.mae?.toFixed(4) || '--' }}</el-descriptions-item>
        <el-descriptions-item label="RMSE">{{ trainResult.rmse?.toFixed(4) || '--' }}</el-descriptions-item>
        <el-descriptions-item label="训练样本">{{ trainResult.sample_count ?? '--' }}</el-descriptions-item>
        <el-descriptions-item label="模型版本">{{ trainResult.model_version || '--' }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ trainResult.duration || '--' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never">
      <template #header><span style="font-weight:600">训练历史</span></template>
      <el-table :data="trainStore.taskHistory" size="small" empty-text="暂无训练记录" stripe>
        <el-table-column prop="fund_code" label="基金代码" width="110" />
        <el-table-column prop="fund_name" label="基金名称" min-width="130" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{row}">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'info'" size="small">
              {{ row.status === 'success' ? '完成' : row.status === 'running' ? '训练中' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="准确率" width="100" align="center">
          <template #default="{row}">
            {{ row.direction_accuracy != null ? (row.direction_accuracy * 100).toFixed(1) + '%' : '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="训练时间" width="170" align="center">
          <template #default="{row}">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useTrainStore } from '@/stores/train'
import { searchFunds } from '@/api/fund'
import { formatDateTime } from '@/utils/format'

const trainStore = useTrainStore()
const fundCode = ref('')
const forceRetrain = ref(false)
const training = ref(false)
const logLines = ref([])
const trainResult = ref(null)
const logRef = ref(null)

const progressStatus = computed(() => {
  const p = trainStore.progress
  if (p >= 100) return 'success'
  return ''
})

const stageText = computed(() => {
  const p = trainStore.progress
  if (p === 0) return '等待开始...'
  if (p < 30) return '数据加载中...'
  if (p < 60) return '特征工程处理中...'
  if (p < 90) return '模型训练中...'
  if (p < 100) return '模型评估中...'
  return '训练完成'
})

watch(() => trainStore.taskStatus, (val) => {
  if (val && val.logs) {
    logLines.value = val.logs
    nextTick(() => {
      if (logRef.value) {
        logRef.value.scrollTop = logRef.value.scrollHeight
      }
    })
  }
  if (val && val.status === 'success' && val.result) {
    trainResult.value = val.result
  }
})

async function handleSearch(query, cb) {
  if (!query) return cb([])
  try {
    const data = await searchFunds(query)
    cb((data || []).map(f => ({ value: f.fund_code + ' - ' + f.fund_name, ...f })))
  } catch {
    cb([])
  }
}

function handleSelect(item) {
  fundCode.value = item.fund_code || item.value.split(' - ')[0]
}

async function startTrain() {
  if (!fundCode.value) return
  training.value = true
  trainResult.value = null
  logLines.value = []
  try {
    const task = await trainStore.createTask({
      fund_code: fundCode.value,
      force_retrain: forceRetrain.value
    })
    if (task && task.task_id) {
      await pollTask(task.task_id)
    }
  } catch {} finally {
    training.value = false
  }
}

async function pollTask(taskId) {
  const maxAttempts = 600
  let attempts = 0
  while (attempts < maxAttempts) {
    await new Promise(r => setTimeout(r, 2000))
    try {
      const status = await trainStore.pollTaskStatus(taskId)
      if (status.status === 'success' || status.status === 'failed') {
        if (status.result) trainResult.value = status.result
        break
      }
    } catch {
      break
    }
    attempts++
  }
}

trainStore.fetchHistory()
</script>