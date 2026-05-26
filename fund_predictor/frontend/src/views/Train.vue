<template>
  <div class="train-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">模型训练</h1>
        <p class="page-subtitle">为指定基金代码训练预测模型</p>
      </div>
    </div>

    <!-- 训练配置 -->
    <div class="config-section glass-card">
      <h3 class="section-title">训练配置</h3>
      <el-form
        ref="formRef"
        :model="trainForm"
        :rules="formRules"
        label-width="120px"
        size="large"
        @submit.prevent="handleTrain"
      >
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="基金代码" prop="fundCode">
              <el-input
                v-model="trainForm.fundCode"
                placeholder="请输入6位基金代码"
                maxlength="6"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="强制重训" prop="forceRetrain">
              <el-switch v-model="trainForm.forceRetrain" />
              <span class="form-tip">覆盖已有模型</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" :loading="training" @click="handleTrain">
            <el-icon><VideoPlay /></el-icon>
            开始训练
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 训练进度 -->
    <div v-if="currentTask" class="progress-section glass-card">
      <h3 class="section-title">训练进度</h3>

      <div class="task-info">
        <div class="info-row">
          <span class="info-label">任务ID:</span>
          <span class="info-value font-mono">{{ currentTask.taskId }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">基金代码:</span>
          <span class="info-value">{{ currentTask.fundCode }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">状态:</span>
          <el-tag :type="statusType(currentTask.status)" effect="dark">
            {{ statusText(currentTask.status) }}
          </el-tag>
        </div>
        <div class="info-row" v-if="currentTask.startTime">
          <span class="info-label">开始时间:</span>
          <span class="info-value">{{ formatTime(currentTask.startTime) }}</span>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="progress-wrapper">
        <el-progress
          :percentage="currentTask.progress || 0"
          :stroke-width="20"
          :text-inside="true"
          :status="progressStatus(currentTask.status)"
          :color="progressColor"
        />

        <!-- 阶段信息 -->
        <div v-if="currentTask.stage" class="stage-info">
          <span class="stage-text">当前阶段: {{ currentTask.stage }}</span>
          <span v-if="currentTask.elapsedTime" class="elapsed-time">
            已耗时: {{ currentTask.elapsedTime }}
          </span>
        </div>
      </div>

      <!-- 日志输出 -->
      <div v-if="logs.length > 0" class="log-container">
        <div class="log-header">
          <span>训练日志</span>
          <el-button text size="small" @click="clearLogs">清空</el-button>
        </div>

        <!-- 训练进度可视化指示器 -->
        <div class="training-progress-visual">
          <div class="progress-stages">
            <div
              v-for="(stage, index) in trainingStages"
              :key="stage.name"
              class="stage-item"
              :class="{
                'active': stage.status === 'active',
                'completed': stage.status === 'completed',
                'pending': stage.status === 'pending'
              }"
            >
              <div class="stage-dot">
                <span v-if="stage.status === 'completed'" class="check-icon">✓</span>
                <span v-else-if="stage.status === 'active'" class="pulse-ring"></span>
              </div>
              <span class="stage-name">{{ stage.name }}</span>
            </div>
          </div>
        </div>

        <div class="log-content" ref="logContentRef">
          <div
            v-for="(log, index) in logs"
            :key="index"
            class="log-line"
            :class="log.type"
          >
            <span class="log-time">{{ log.time }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>

      <!-- 错误信息 -->
      <el-alert
        v-if="currentTask.error"
        :title="currentTask.error.message"
        type="error"
        show-icon
        closable
        class="mt-4"
      >
        <template #default>
          <pre class="error-details">{{ JSON.stringify(currentTask.error.details, null, 2) }}</pre>
        </template>
      </el-alert>
    </div>

    <!-- 历史任务列表 -->
    <div class="history-section glass-card">
      <div class="section-header">
        <h3 class="section-title">历史训练记录</h3>
        <el-button text type="primary" @click="refreshHistory">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <el-table
        :data="historyTasks"
        stripe
        style="width: 100%"
        empty-text="暂无训练记录"
        @row-click="viewTaskDetail"
      >
        <el-table-column prop="taskId" label="任务ID" width="180">
          <template #default="{ row }">
            <span class="font-mono">{{ row.taskId }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="fundCode" label="基金代码" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="startTime" label="开始时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.startTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="100" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              size="small"
              @click.stop="viewTaskDetail(row)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { VideoPlay, Refresh } from '@element-plus/icons-vue'
import { startTraining } from '@/api/train'
import { getTaskStatus, getTasksHistory } from '@/api/task'

// 表单相关
const formRef = ref(null)
const trainForm = reactive({
  fundCode: '',
  forceRetrain: false
})

const formRules = {
  fundCode: [
    { required: true, message: '请输入基金代码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '请输入6位数字的基金代码', trigger: 'blur' }
  ]
}

// 状态
const training = ref(false)
const currentTask = ref(null)
const logs = ref([])
const logContentRef = ref(null)

// 轮询定时器
let pollTimer = null

// 历史任务列表（从API加载）
const historyTasks = ref([])
const historyLoading = ref(false)

// 训练阶段定义
const stageDefinitions = [
  { name: '初始化', keywords: ['初始化', '准备'] },
  { name: '数据加载', keywords: ['数据', '加载', 'fetch'] },
  { name: '特征工程', keywords: ['特征', 'feature', '预处理'] },
  { name: '模型训练', keywords: ['训练', 'train', 'epoch', 'batch', 'loss'] },
  { name: '模型评估', keywords: ['评估', 'evaluate', '验证', 'val'] },
  { name: '保存模型', keywords: ['保存', 'save', '完成'] }
]

// 基于日志分析训练阶段进度
const trainingStages = computed(() => {
  const stages = stageDefinitions.map(s => ({ ...s, status: 'pending' }))

  if (!currentTask.value || logs.value.length === 0) {
    return stages
  }

  // 合并所有日志消息用于分析
  const allLogsText = logs.value.map(l => l.message).join(' ')
  const currentStage = currentTask.value.stage || ''

  let foundActive = false

  for (let i = 0; i < stages.length; i++) {
    const stage = stages[i]

    // 检查是否已完成（后续阶段已开始或任务完成）
    if (foundActive) {
      stage.status = 'pending'
      continue
    }

    // 检查是否匹配当前阶段
    const isCurrentStage = stage.keywords.some(kw =>
      currentStage.toLowerCase().includes(kw.toLowerCase())
    )

    // 检查日志中是否有该阶段的记录
    const hasLogEvidence = stage.keywords.some(kw =>
      allLogsText.toLowerCase().includes(kw.toLowerCase())
    )

    if (currentTask.value.status === 'completed') {
      stage.status = 'completed'
    } else if (isCurrentStage || (hasLogEvidence && !foundActive)) {
      stage.status = 'active'
      foundActive = true
    } else if (hasLogEvidence || i === 0) {
      stage.status = 'completed'
    }
  }

  // 如果没有找到活跃状态且任务还在运行，设置第一个未完成为活跃
  if (!foundActive && currentTask.value.status === 'running') {
    const firstPending = stages.find(s => s.status === 'pending')
    if (firstPending) {
      firstPending.status = 'active'
    }
  }

  return stages
})

// 方法
const handleTrain = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (error) {
    return
  }

  training.value = true

  // 重置状态
  currentTask.value = null
  logs.value = []

  try {
    const res = await startTraining({
      fund_code: trainForm.fundCode,
      force: trainForm.forceRetrain
    })

    if (res.task_id) {
      // 初始化当前任务
      currentTask.value = {
        taskId: res.task_id,
        fundCode: trainForm.fundCode,
        status: 'running',
        progress: 0,
        stage: '初始化中...',
        startTime: new Date(),
        elapsedTime: '0s'
      }

      addLog('info', `训练任务已创建: ${res.task_id}`)
      addLog('info', `基金代码: ${trainForm.fundCode}`)
      addLog('info', '开始轮询任务状态...')

      // 开始轮询
      startPolling(res.task_id)
    }
  } catch (error) {
    addLog('error', `启动失败: ${error.message}`)
  } finally {
    training.value = false
  }
}

const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  stopPolling()
  currentTask.value = null
  logs.value = []
}

// 轮询任务状态
const startPolling = (taskId) => {
  stopPolling()

  pollTimer = setInterval(async () => {
    try {
      const res = await getTaskStatus(taskId)
      const data = res.data

      // 更新任务状态
      if (currentTask.value) {
        currentTask.value.status = data.status
        currentTask.value.stage = data.stage || ''
        currentTask.value.progress = calculateProgress(data.status, data.stage)

        if (data.error) {
          currentTask.value.error = data.error
        }

        // 计算已耗时间
        if (currentTask.value.startTime) {
          const elapsed = Math.floor((Date.now() - currentTask.value.startTime.getTime()) / 1000)
          currentTask.value.elapsedTime = formatDuration(elapsed)
        }

        // 添加日志
        if (data.stage && data.stage !== currentTask.value._lastStage) {
          addLog('info', `进入阶段: ${data.stage}`)
          currentTask.value._lastStage = data.stage
        }
      }

      // 检查是否完成
      if (['completed', 'failed'].includes(data.status)) {
        stopPolling()

        if (data.status === 'completed') {
          addLog('success', '训练完成！模型已保存')
        } else {
          addLog('error', `训练失败: ${data.error?.message || '未知错误'}`)

          if (data.error?.details) {
            console.error('错误详情:', data.error.details)
          }
        }

        // 刷新历史记录
        refreshHistory()
      }
    } catch (error) {
      console.error('轮询失败:', error)
      // 继续轮询，不中断
    }
  }, 2000) // 每2秒轮询一次
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 添加日志
const addLog = (type, message) => {
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`

  logs.value.push({ type, message, time })

  // 自动滚动到底部
  nextTick(() => {
    if (logContentRef.value) {
      logContentRef.value.scrollTop = logContentRef.value.scrollHeight
    }
  })
}

const clearLogs = () => {
  logs.value = []
}

// 辅助函数
const statusType = (status) => {
  const map = {
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    pending: 'info'
  }
  return map[status] || 'info'
}

const statusText = (status) => {
  const map = {
    running: '训练中',
    completed: '已完成',
    failed: '失败',
    pending: '等待中'
  }
  return map[status] || status
}

const progressStatus = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return undefined
}

const progressColor = [
  { color: '#3b82f6', percentage: 30 },
  { color: '#8b5cf6', percentage: 60 },
  { color: '#22c55e', percentage: 90 },
  { color: '#22c55e', percentage: 100 }
]

const calculateProgress = (status, stage) => {
  const stages = ['初始化', '数据加载', '特征工程', '模型训练', '模型评估', '保存模型']
  let base = 0

  if (status === 'completed') return 100
  if (status === 'failed') return 50

  const index = stages.findIndex(s => stage?.includes(s))
  if (index >= 0) {
    base = ((index + 1) / stages.length) * 80
  }

  return Math.min(base + Math.random() * 15, 95)
}

const formatTime = (date) => {
  if (!date) return '-'
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const formatDuration = (seconds) => {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes < 60) return `${minutes}m ${secs}s`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours}h ${mins}m`
}

const refreshHistory = async () => {
  // 刷新历史记录逻辑
  console.log('刷新历史记录')
  historyLoading.value = true
  try {
    const response = await getTasksHistory({ limit: 50 })
    if (response.ok && response.data) {
      historyTasks.value = response.data
      console.log('历史记录加载成功:', response.data.length, '条')
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
  } finally {
    historyLoading.value = false
  }
}

const viewTaskDetail = (row) => {
  console.log('查看任务详情:', row)
  // 可以显示详情对话框或跳转到详情页
}

// 生命周期
onMounted(() => {
  // 页面加载时的初始化逻辑
  refreshHistory()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style lang="scss" scoped>
.train-page {
  max-width: 1200px;
}

.page-header {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}

.page-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
  margin: 0;
}

.page-subtitle {
  color: var(--text-muted);
  font-size: 13px;
  margin-top: 4px;
}

/* 配置区域 */
.config-section,
.progress-section,
.history-section {
  margin-bottom: 24px;
  animation: fadeIn 0.5s ease;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;

  &::before {
    content: '';
    width: 3px;
    height: 16px;
    background: var(--primary);
    border-radius: 2px;
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .section-title {
    margin-bottom: 0;
  }
}

.form-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 8px;
}

.font-mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
}

/* 进度区域 */
.progress-wrapper {
  margin-top: 24px;
}

.task-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: $radius-md;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 13px;
  color: var(--text-muted);
  min-width: 70px;
}

.info-value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.stage-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--glass-bg);
  border-radius: $radius-sm;
  font-size: 13px;
}

.stage-text {
  color: var(--text-secondary);
}

.elapsed-time {
  color: var(--text-muted);
  font-family: 'SF Mono', monospace;
}

/* 日志容器 */
.log-container {
  margin-top: 24px;
  border: 1px solid var(--border);
  border-radius: $radius-md;
  overflow: hidden;
}

/* 训练进度可视化 */
.training-progress-visual {
  padding: 16px;
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border);
}

.progress-stages {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.stage-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;

  .stage-dot {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--bg-secondary);
    border: 2px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    transition: all 0.3s ease;

    .check-icon {
      color: #22c55e;
      font-size: 14px;
      font-weight: bold;
    }

    .pulse-ring {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #3b82f6;
      animation: pulse 1.5s ease-in-out infinite;
    }
  }

  .stage-name {
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
    white-space: nowrap;
    transition: color 0.3s ease;
  }

  &.completed {
    .stage-dot {
      background: rgba(34, 197, 94, 0.15);
      border-color: #22c55e;
    }
    .stage-name {
      color: #22c55e;
    }
  }

  &.active {
    .stage-dot {
      background: rgba(59, 130, 246, 0.15);
      border-color: #3b82f6;
      box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
    }
    .stage-name {
      color: #3b82f6;
      font-weight: 600;
    }
  }

  &.pending {
    .stage-dot {
      opacity: 0.5;
    }
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.log-content {
  max-height: 300px;
  overflow-y: auto;
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-line {
  display: flex;
  gap: 12px;
  padding: 2px 0;

  &.info .log-time { color: #94a3b8; }
  &.info .log-message { color: #e2e8f0; }

  &.success .log-time { color: #22c55e; }
  &.success .log-message { color: #86efac; }

  &.error .log-time { color: #ef4444; }
  &.error .log-message { color: #fca5a5; }

  &.warning .log-time { color: #f59e0b; }
  &.warning .log-message { color: #fcd34d; }
}

.log-time {
  color: var(--text-muted);
  white-space: nowrap;
}

.log-message {
  color: var(--text-secondary);
  word-break: break-all;
}

.error-details {
  margin-top: 8px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: $radius-sm;
  font-family: 'SF Mono', monospace;
  font-size: 11px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 历史表格 */
:deep(.el-table) {
  --el-table-border-color: var(--border);

  tr {
    cursor: pointer;
  }
}
</style>
