<template>
  <PageContainer narrow>
    <div class="page-header mb-16">
      <h2 class="page-title">模型训练</h2>
    </div>

    <SectionCard compact class="mb-16">
      <div class="train-search">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码"
          clearable
          class="search-input"
          @keyup.enter="startTrain"
          @select="handleSelect"
        />
        <el-checkbox v-model="forceRetrain" label="强制重训" border size="small" />
        <el-button type="primary" :loading="training" @click="startTrain">开始训练</el-button>
      </div>
    </SectionCard>

    <template v-if="trainStore.taskStatus">
      <SectionCard title="训练进度" class="mb-16">
        <el-progress
          :percentage="trainStore.progress"
          :status="progressStatus"
          :stroke-width="20"
          class="mb-16"
        >
          <span class="text-sm">{{ stageText }}</span>
        </el-progress>
        <div ref="logRef" class="log-terminal">
          <div v-for="(line, i) in logLines" :key="i">{{ line }}</div>
        </div>
      </SectionCard>
    </template>

    <SectionCard v-if="trainResult" title="训练结果" class="mb-16">
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
    </SectionCard>

    <SectionCard title="训练历史">
      <el-table :data="trainStore.taskHistory" size="small" empty-text="暂无训练记录" stripe>
        <el-table-column prop="fund_code" label="基金代码" width="100" />
        <el-table-column prop="fund_name" label="基金名称" min-width="120" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{row}">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'info'" size="small">
              {{ row.status === 'success' ? '完成' : row.status === 'running' ? '训练中' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column width="110" align="center">
          <template #header>
            <span class="flex-center gap-4">
              方向准确率
              <el-tooltip content="预测涨跌方向正确的比例，越高越好" placement="top">
                <el-icon style="color:var(--text-tertiary);cursor:pointer"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
          </template>
          <template #default="{row}">
            <span v-if="row.metrics_summary?.direction_accuracy != null && row.status === 'success'" style="color:#67c23a;font-weight:500">
              {{ (row.metrics_summary.direction_accuracy * 100).toFixed(1) }}%
            </span>
            <span v-else style="color:#c0c4cc">--</span>
          </template>
        </el-table-column>
        <el-table-column width="100" align="center">
          <template #header>
            <span class="flex-center gap-4">
              MAE
              <el-tooltip content="平均绝对误差，预测值与真实值的平均差距，越小越好" placement="top">
                <el-icon style="color:var(--text-tertiary);cursor:pointer"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
          </template>
          <template #default="{row}">
            <span v-if="row.metrics_summary?.mae != null && row.status === 'success'" style="color:#409eff;font-weight:500">
              {{ row.metrics_summary.mae.toFixed(4) }}
            </span>
            <span v-else style="color:#c0c4cc">--</span>
          </template>
        </el-table-column>
        <el-table-column width="100" align="center">
          <template #header>
            <span class="flex-center gap-4">
              RMSE
              <el-tooltip content="均方根误差，对大误差更敏感的指标，越小越好" placement="top">
                <el-icon style="color:var(--text-tertiary);cursor:pointer"><QuestionFilled /></el-icon>
              </el-tooltip>
            </span>
          </template>
          <template #default="{row}">
            <span v-if="row.metrics_summary?.rmse != null && row.status === 'success'" style="color:#e6a23c;font-weight:500">
              {{ row.metrics_summary.rmse.toFixed(4) }}
            </span>
            <span v-else style="color:#c0c4cc">--</span>
          </template>
        </el-table-column>
        <el-table-column label="样本数" width="80" align="center">
          <template #default="{row}">
            <span v-if="row.metrics_summary?.train_rows != null && row.status === 'success'">
              {{ row.metrics_summary.train_rows }}
            </span>
            <span v-else style="color:#c0c4cc">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="训练时间" width="150" align="center">
          <template #default="{row}">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </PageContainer>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useTrainStore } from '@/stores/train'
import { searchFunds } from '@/api/fund'
import { formatDateTime } from '@/utils/format'
import { QuestionFilled } from '@element-plus/icons-vue'

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

<style scoped lang="scss">
.page-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.train-search {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 180px;
  :deep(.el-autocomplete) { width: 100%; }
}

.log-terminal {
  background: #1d1e1f;
  color: #c9d1d9;
  padding: var(--space-md);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-family: var(--font-mono);
  height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}
</style>