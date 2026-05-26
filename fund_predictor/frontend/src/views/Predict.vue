<template>
  <div class="predict-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">智能预测</h1>
        <p class="page-subtitle">输入基金代码，获取 T+1 净值预测结果</p>
      </div>
    </div>

    <!-- 控制区 -->
    <div class="control-section glass-card">
      <div class="control-row">
        <div class="input-group">
          <label>基金代码</label>
          <el-input
            v-model="fundCode"
            placeholder="请输入6位基金代码"
            maxlength="6"
            size="large"
            clearable
            @keyup.enter="handlePredict"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="button-group">
          <el-button
            type="primary"
            size="large"
            :loading="predicting"
            @click="handlePredict"
          >
            <el-icon><Aim /></el-icon>
            预测
          </el-button>

          <el-button
            size="large"
            :loading="training"
            @click="handleTrain"
          >
            <el-icon><Setting /></el-icon>
            训练并预测
          </el-button>
        </div>

        <div class="options-group hide-mobile">
          <el-switch
            v-model="forceRetrain"
            active-text="强制重训"
            inactive-text=""
          />
        </div>
      </div>

      <!-- 错误提示 -->
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      closable
      class="mt-4"
      @close="errorMessage = ''"
    />
    </div>

    <!-- 训练进度区域（新增） -->
    <div v-if="showTrainingProgress" class="training-progress glass-card">
      <div class="progress-header">
        <span class="progress-title">🔄 模型训练中...</span>
        <el-button 
          type="danger" 
          size="small" 
          text
          @click="cancelTraining"
          :disabled="!currentTaskId"
        >
          取消训练
        </el-button>
      </div>
      
      <!-- 进度条 -->
      <div class="progress-bar-wrapper">
        <el-progress 
          :percentage="trainingProgress.percentage" 
          :status="trainingStatus"
          :stroke-width="20"
          text-inside
          :color="progressColor"
        />
      </div>
      
      <!-- 训练信息 -->
      <div class="training-info-grid">
        <div class="info-item">
          <span class="info-label">任务ID</span>
          <span class="info-value">{{ currentTaskId || '---' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">当前阶段</span>
          <span class="info-value stage-text">{{ trainingProgress.stage }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">已用时</span>
          <span class="info-value">{{ formatDuration(trainingProgress.elapsed) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">预计剩余</span>
          <span class="info-value">{{ formatDuration(trainingProgress.remaining) }}</span>
        </div>
      </div>
      
      <!-- 训练日志（可折叠） -->
      <el-collapse v-if="trainingLogs.length > 0" class="log-collapse">
        <el-collapse-item title="📋 查看训练日志">
          <div class="log-container">
            <pre>{{ trainingLogs.join('\n') }}</pre>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 空状态 -->
    <div v-if="!hasResult" class="empty-state glass-card">
      <div class="empty-icon">
        <el-icon :size="64" color="#3b82f6"><TrendCharts /></el-icon>
      </div>
      <h3 class="empty-title">输入基金代码开始预测</h3>
      <p class="empty-desc">
        系统将分析模型可信度、方向信号和风险区间，辅助您的投资决策
      </p>
      <div class="quick-codes">
        <span class="quick-label">快捷选择：</span>
        <el-tag
          v-for="code in quickCodes"
          :key="code"
          class="code-tag"
          effect="plain"
          @click="selectQuickCode(code)"
        >
          {{ code }}
        </el-tag>
      </div>
    </div>

    <!-- 预测结果 -->
    <div v-else class="result-section">
      <!-- 主结论卡 -->
      <div class="conclusion-card glass-card">
        <div class="conclusion-main">
          <div class="conclusion-label">当前结论</div>
          <div
            class="conclusion-value"
            :class="predictionData.directionClass"
          >
            {{ predictionData.conclusion }}
          </div>
          <div class="conclusion-subtitle">{{ predictionData.subtitle }}</div>
          <div class="reliability-badge" :class="predictionData.reliabilityLevel">
            {{ predictionData.reliabilityText }}
          </div>
        </div>
      </div>

      <!-- 方向信号网格 -->
      <div class="direction-grid">
        <div class="direction-item glass-card" :class="{ active: predictionData.upProbability > 50 }">
          <div class="direction-label">上涨概率</div>
          <div class="direction-value positive">{{ predictionData.upProbability }}%</div>
        </div>
        <div class="direction-item glass-card" :class="{ active: predictionData.downProbability > 50 }">
          <div class="direction-label">下跌概率</div>
          <div class="direction-value negative">{{ predictionData.downProbability }}%</div>
        </div>
        <div class="direction-item glass-card">
          <div class="direction-label">中性区间</div>
          <div class="direction-value neutral">{{ predictionData.neutralRange }}</div>
        </div>
      </div>

      <!-- 区间可视化 -->
      <div class="interval-section">
        <div class="interval-card glass-card">
          <div class="interval-header">
            <span class="interval-title">80% 收益区间</span>
            <el-tag size="small" type="info">置信度 80%</el-tag>
          </div>
          <div class="interval-bar-wrapper">
            <div class="interval-bar">
              <div
                class="interval-range"
                :style="{
                  left: predictionData.interval80.left + '%',
                  width: predictionData.interval80.width + '%'
                }"
              ></div>
              <div
                class="interval-center"
                :style="{ left: predictionData.interval80.center + '%' }"
              ></div>
            </div>
          </div>
          <div class="interval-labels">
            <span class="negative">{{ predictionData.interval80.lower }}</span>
            <span class="positive">{{ predictionData.interval80.upper }}</span>
          </div>
        </div>

        <div class="interval-card glass-card">
          <div class="interval-header">
            <span class="interval-title">90% 收益区间</span>
            <el-tag size="small" type="info">置信度 90%</el-tag>
          </div>
          <div class="interval-bar-wrapper">
            <div class="interval-bar">
              <div
                class="interval-range"
                :style="{
                  left: predictionData.interval90.left + '%',
                  width: predictionData.interval90.width + '%'
                }"
              ></div>
              <div
                class="interval-center"
                :style="{ left: predictionData.interval90.center + '%' }"
              ></div>
            </div>
          </div>
          <div class="interval-labels">
            <span class="negative">{{ predictionData.interval90.lower }}</span>
            <span class="positive">{{ predictionData.interval90.upper }}</span>
          </div>
        </div>
      </div>

      <!-- 辅助点预测 -->
      <div class="auxiliary-prediction glass-card">
        <span class="auxiliary-label">辅助点预测</span>
        <span class="auxiliary-value">{{ predictionData.pointPrediction }}</span>
      </div>

      <!-- 关键可信度指标 -->
      <div class="metrics-section glass-card">
        <h3 class="section-title">关键可信度指标</h3>
        <div class="metrics-grid">
          <div
            v-for="(metric, key) in predictionData.metrics"
            :key="key"
            class="metric-item"
          >
            <div class="metric-name">{{ metric.name }}</div>
            <div class="metric-number" :class="metric.status">
              {{ metric.value }}
            </div>
          </div>
        </div>
      </div>

      <!-- AI 一句话摘要入口 -->
      <div v-if="hasResult" class="ai-summary-entry glass-card">
        <div class="ai-summary-content">
          <el-icon class="ai-icon"><MagicStick /></el-icon>
          <span v-if="aiSummaryLoading" class="summary-text loading-text">
            <el-icon class="is-loading"><Loading /></el-icon>
            AI 正在分析...
          </span>
          <template v-else-if="aiSummaryText">
            <span class="summary-text">{{ aiSummaryText }}</span>
            <router-link
              :to="{ path: '/intraday', query: { code: fundCode } }"
              class="view-full-link"
            >
              查看完整 AI 解读 →
            </router-link>
          </template>
          <span v-else class="summary-text summary-unavailable">
            AI 分析暂时不可用
          </span>
        </div>
      </div>

      <!-- 预测历史图表 -->
      <div class="chart-section glass-card">
        <h3 class="section-title">预测趋势图</h3>
        <BaseChart
          :option="predictionChartOption"
          height="350px"
          :loading="chartLoading"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Search, Aim, Setting, TrendCharts,
  MagicStick, Loading
} from '@element-plus/icons-vue'
import { predictFund, getFundProfile } from '@/api/fund'
import { getAIAnalysis } from '@/api/ai_analysis'
import BaseChart from '@/components/common/BaseChart.vue'

const route = useRoute()

// 状态
const fundCode = ref('018956')
const predicting = ref(false)
const training = ref(false)
const forceRetrain = ref(false)
const errorMessage = ref('')
const hasResult = ref(false)
const chartLoading = ref(false)

// 训练进度相关状态（新增）
const showTrainingProgress = ref(false)
const currentTaskId = ref(null)
const trainingProgress = reactive({
  percentage: 0,
  stage: '初始化',
  elapsed: 0,
  remaining: 0
})
const trainingLogs = ref([])
let pollingTimer = null

// 快捷代码
const quickCodes = ['018956', '000001', '110011', '161725', '519778']

// AI 摘要相关状态
const aiSummaryLoading = ref(false)
const aiSummaryText = ref('')

// 预测数据（从API加载）
const predictionData = reactive({
  conclusion: '',
  directionClass: 'neutral',
  subtitle: '',
  reliabilityLevel: 'low',
  reliabilityText: '加载中...',
  upProbability: 50,
  downProbability: 50,
  neutralRange: '-',
  interval80: {
    lower: '-',
    upper: '-',
    left: 50,
    width: 0,
    center: 50
  },
  interval90: {
    lower: '-',
    upper: '-',
    left: 50,
    width: 0,
    center: 50
  },
  pointPrediction: '-',
  metrics: {
    improvement: { name: '模型改进度', value: '-', status: '' },
    correlation: { name: '预测-真实相关', value: '-', status: '' },
    auc: { name: '方向 AUC', value: '-', status: '' },
    proxyR2: { name: 'Proxy R²', value: '-', status: '' }
  },
  // 原始API数据，用于调试
  rawData: null
})

// 图表配置
const predictionChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' }
  },
  legend: {
    data: ['实际值', '预测值', '区间上界', '区间下界'],
    top: 10,
    textStyle: { color: '#94a3b8' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: generateDateRange(30),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b', fontSize: 11 }
  },
  yAxis: {
    type: 'value',
    name: '涨跌幅(%)',
    axisLabel: {
      formatter: '{value}%',
      color: '#64748b'
    },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [
    {
      name: '实际值',
      type: 'line',
      smooth: true,
      data: generateRandomFloatData(30, -2, 3),
      lineStyle: { width: 2, color: '#94a3b8' },
      itemStyle: { color: '#94a3b8' }
    },
    {
      name: '预测值',
      type: 'line',
      smooth: true,
      data: generateRandomFloatData(30, -2, 3),
      lineStyle: { width: 3, color: '#3b82f6' },
      itemStyle: { color: '#3b82f6' }
    },
    {
      name: '区间上界',
      type: 'line',
      smooth: true,
      data: generateRandomFloatData(30, 1, 5),
      lineStyle: { width: 1, color: 'rgba(239, 68, 68, 0.5)', type: 'dashed' },
      areaStyle: { color: 'rgba(239, 68, 68, 0.05)' }
    },
    {
      name: '区间下界',
      type: 'line',
      smooth: true,
      data: generateRandomFloatData(30, -5, -1),
      lineStyle: { width: 1, color: 'rgba(34, 197, 94, 0.5)', type: 'dashed' },
      areaStyle: { color: 'rgba(34, 197, 94, 0.05)' }
    }
  ]
}))

// 方法
const handlePredict = async () => {
  if (!fundCode.value.trim()) {
    errorMessage.value = '请输入基金代码'
    return
  }

  predicting.value = true
  errorMessage.value = ''

  try {
    const res = await predictFund({ fund_code: fundCode.value })
    const data = res.data || res
    console.log('预测结果:', data)
    
    // 将API数据映射到predictionData
    predictionData.rawData = data
    
    // 点预测
    const predReturn = data.pred_return || data.pred || 0
    const predPercent = (predReturn * 100).toFixed(3)
    predictionData.conclusion = predReturn >= 0 ? `+${predPercent}%` : `${predPercent}%`
    predictionData.pointPrediction = predictionData.conclusion
    
    // 方向信号
    const directionSignal = data.direction_signal || 'neutral'
    predictionData.directionClass = directionSignal
    const directionStrength = data.direction_strength || 'none'
    
    // 概率
    const pUp = data.p_up !== null && data.p_up !== undefined ? data.p_up : 0.5
    const pDown = data.p_down !== null && data.p_down !== undefined ? data.p_down : (1 - pUp)
    predictionData.upProbability = Math.round(pUp * 100)
    predictionData.downProbability = Math.round(pDown * 100)
    
    // 中性区间 (p_up 在 0.4-0.6 之间)
    if (pUp >= 0.4 && pUp <= 0.6) {
      const neutralLow = ((0.4 - pUp) * 100).toFixed(2)
      const neutralHigh = ((0.6 - pUp) * 100).toFixed(2)
      predictionData.neutralRange = `${neutralLow}% ~ +${neutralHigh}%`
    } else {
      predictionData.neutralRange = '-'
    }
    
    // 副标题
    if (directionSignal === 'bullish') {
      predictionData.subtitle = directionStrength === 'strong' 
        ? '模型强烈看好该基金明日表现' 
        : '模型倾向认为该基金明日将上涨'
    } else if (directionSignal === 'bearish') {
      predictionData.subtitle = directionStrength === 'strong'
        ? '模型强烈看空该基金明日表现'
        : '模型倾向认为该基金明日将下跌'
    } else {
      predictionData.subtitle = '模型方向信号不明显，建议观望'
    }
    
    // 可靠度/置信度
    const proxyConfidence = data.proxy_based_confidence || 'low'
    predictionData.reliabilityLevel = proxyConfidence
    const confidenceMap = { high: '高可信度', medium: '中可信度', low: '低可信度' }
    predictionData.reliabilityText = confidenceMap[proxyConfidence] || '未知'
    
    // 区间数据 (基于净值区间转换为百分比)
    const nav80 = data.nav_interval_80 || {}
    const nav90 = data.nav_interval_90 || {}
    const todayNav = data.today_nav || 1
    
    if (nav80.lower && nav80.upper) {
      const lower80Pct = ((nav80.lower / todayNav - 1) * 100).toFixed(2)
      const upper80Pct = ((nav80.upper / todayNav - 1) * 100).toFixed(2)
      predictionData.interval80.lower = `${lower80Pct}%`
      predictionData.interval80.upper = `+${upper80Pct}%`
      
      // 计算区间位置（简化处理）
      const center80 = 50 // 预测值在区间中的相对位置
      const width80 = Math.min(Math.abs(parseFloat(upper80Pct)) + Math.abs(parseFloat(lower80Pct)), 10) * 5
      predictionData.interval80.left = Math.max(0, 50 - width80 / 2)
      predictionData.interval80.width = width80
      predictionData.interval80.center = center80
    }
    
    if (nav90.lower && nav90.upper) {
      const lower90Pct = ((nav90.lower / todayNav - 1) * 100).toFixed(2)
      const upper90Pct = ((nav90.upper / todayNav - 1) * 100).toFixed(2)
      predictionData.interval90.lower = `${lower90Pct}%`
      predictionData.interval90.upper = `+${upper90Pct}%`
      
      const center90 = 50
      const width90 = Math.min(Math.abs(parseFloat(upper90Pct)) + Math.abs(parseFloat(lower90Pct)), 15) * 3.5
      predictionData.interval90.left = Math.max(0, 50 - width90 / 2)
      predictionData.interval90.width = width90
      predictionData.interval90.center = center90
    }
    
    // 指标数据
    const pointMetrics = data.point_prediction_health || {}
    const dirMetrics = data.direction_health || {}
    const baseline = data.baseline || {}
    
    predictionData.metrics.improvement.value = baseline.model_vs_mean_improvement 
      ? `${(baseline.model_vs_mean_improvement * 100).toFixed(2)}%` 
      : '-'
    predictionData.metrics.improvement.status = parseFloat(baseline.model_vs_mean_improvement) > 0 ? 'good' : 'bad'
    
    predictionData.metrics.correlation.value = pointMetrics.pred_real_corr 
      ? pointMetrics.pred_real_corr.toFixed(3) 
      : '-'
    predictionData.metrics.correlation.status = parseFloat(pointMetrics.pred_real_corr) > 0.1 ? 'good' : 'bad'
    
    predictionData.metrics.auc.value = dirMetrics.auc ? dirMetrics.auc.toFixed(3) : '-'
    predictionData.metrics.auc.status = parseFloat(dirMetrics.auc) > 0.55 ? 'good' : 'bad'
    
    predictionData.metrics.proxyR2.value = data.proxy_r2_60 ? data.proxy_r2_60.toFixed(3) : '-'
    predictionData.metrics.proxyR2.status = parseFloat(data.proxy_r2_60) > 0.35 ? 'good' : 'bad'
    
    hasResult.value = true

    // 异步加载 AI 摘要（不阻塞主流程）
    loadAISummary()
  } catch (error) {
    errorMessage.value = error.message || '预测失败，请稍后重试'
    console.error('预测失败:', error)
  } finally {
    predicting.value = false
  }
}

const handleTrain = async () => {
  if (!fundCode.value.trim()) {
    errorMessage.value = '请输入基金代码'
    return
  }
  
  if (!/^\d{6}$/.test(fundCode.value)) {
    errorMessage.value = '请输入正确的6位数字基金代码'
    return
  }

  // 动态导入避免循环依赖
  const { startTraining, getTaskStatus } = await import('@/api/train')

  training.value = true
  showTrainingProgress.value = true
  
  // 重置进度
  Object.assign(trainingProgress, {
    percentage: 0,
    stage: '提交训练任务',
    elapsed: 0,
    remaining: 0
  })
  trainingLogs.value = []
  
  try {
    ElMessage.info('正在提交训练任务...')
    
    const res = await startTraining({
      fund_code: fundCode.value,
      force: forceRetrain.value
    })

    if (res.task_id) {
      currentTaskId.value = res.task_id
      ElMessage.success(`训练任务已启动 (ID: ${res.task_id})`)
      
      // 开始轮询进度
      startPolling()
    } else {
      throw new Error('训练任务创建失败：未返回task_id')
    }
  } catch (error) {
    console.error('训练启动失败:', error)
    errorMessage.value = `训练启动失败: ${error.message || '未知错误'}`
    resetTrainingState()
  }
}

// 训练进度轮询（新增）
function startPolling() {
  stopPolling() // 清除旧的定时器
  
  pollingTimer = setInterval(async () => {
    try {
      if (!currentTaskId.value) return
      
      const { getTaskStatus } = await import('@/api/train')
      const statusRes = await getTaskStatus(currentTaskId.value)
      const status = statusRes.data || statusRes
      
      // 更新进度
      updateProgress(status)
      
      // 追加日志
      if (status.log) {
        const newLog = typeof status.log === 'string' ? status.log : JSON.stringify(status.log)
        if (!trainingLogs.value.includes(newLog)) {
          trainingLogs.value.push(newLog)
          // 保持日志不超过50条
          if (trainingLogs.value.length > 50) {
            trainingLogs.value.shift()
          }
        }
      }
      
      // 检查是否完成
      if (status.status === 'completed' || status.status === 'success') {
        completeTraining()
      } else if (status.status === 'failed' || status.status === 'error') {
        failTraining(status.error || '训练失败')
      }
      
    } catch (error) {
      console.error('轮询失败:', error)
      // 轮询失败不中断，继续尝试
    }
  }, 2000) // 每2秒轮询一次
}

function updateProgress(status) {
  let percentage = 0
  let stage = ''
  
  switch (status.status) {
    case 'pending':
    case 'queued':
      percentage = 5
      stage = '等待执行'
      break
    case 'running':
    case 'processing':
      if (status.progress && status.progress.current_step) {
        const steps = ['data_fetch', 'feature_engineering', 'model_training', 'evaluation']
        const currentIndex = steps.indexOf(status.progress.current_step)
        percentage = Math.min(95, 20 + (currentIndex * 25) + (status.progress.step_progress || 0))
        stage = getStageName(status.progress.current_step)
      } else if (status.progress_percent !== undefined) {
        percentage = Math.min(95, status.progress_percent)
        stage = status.stage || '训练中...'
      } else {
        percentage = 50
        stage = '训练中...'
      }
      break
    case 'completed':
    case 'success':
      percentage = 100
      stage = '已完成'
      break
    default:
      percentage = 10
      stage = status.status || '处理中...'
  }
  
  Object.assign(trainingProgress, {
    percentage,
    stage,
    elapsed: status.elapsed || trainingProgress.elapsed + 2,
    remaining: status.remaining || Math.max(0, (100 - percentage) * 2)
  })
}

function getStageName(step) {
  const names = {
    'data_fetch': '📥 正在获取数据...',
    'feature_engineering': '⚙️ 正在构建特征...',
    'model_training': '🎯 正在训练模型...',
    'evaluation': '✅ 正在评估模型...',
    'saving': '💾 正在保存模型...'
  }
  return names[step] || step
}

function completeTraining() {
  stopPolling()
  
  ElMessage.success('🎉 训练完成！正在自动预测...')
  
  // 延迟一下让用户看到完成状态
  setTimeout(async () => {
    try {
      resetTrainingState()
      // 自动开始预测
      await handlePredict()
    } catch (error) {
      errorMessage.value = `自动预测失败: ${error.message}`
    }
  }, 1500)
}

function failTraining(errorMsg) {
  stopPolling()
  ElMessage.error(`❌ 训练失败: ${errorMsg}`)
  errorMessage.value = `训练失败: ${errorMsg}`
  resetTrainingState()
}

function cancelTraining() {
  ElMessageBox.confirm(
    '确定要取消当前训练吗？',
    '取消确认',
    {
      confirmButtonText: '确定取消',
      cancelButtonText: '继续训练',
      type: 'warning'
    }
  ).then(() => {
    stopPolling()
    ElMessage.warning('已取消训练')
    resetTrainingState()
  }).catch(() => {
    // 用户选择继续训练
  })
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function resetTrainingState() {
  training.value = false
  showTrainingProgress.value = false
  currentTaskId.value = null
  Object.assign(trainingProgress, {
    percentage: 0,
    stage: '',
    elapsed: 0,
    remaining: 0
  })
  trainingLogs.value = []
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '--'
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  if (mins > 0) {
    return `${mins}分${secs}秒`
  }
  return `${secs}秒`
}

// 计算属性：训练状态
const trainingStatus = computed(() => {
  const progress = trainingProgress.percentage
  if (progress >= 100) return 'success'
  if (progress > 80) return '' // 接近完成时不显示特殊状态
  return undefined
})

// 计算属性：进度条颜色
const progressColor = computed(() => {
  const progress = trainingProgress.percentage
  if (progress < 30) return '#409EFF' // 蓝色
  if (progress < 70) return '#E6A23C' // 橙色
  if (progress < 90) return '#67C23A' // 绿色
  return '#409EFF' // 完成
})

const selectQuickCode = (code) => {
  fundCode.value = code
  handlePredict()
}

// 加载 AI 一句话摘要（轻量级）
async function loadAISummary() {
  if (!fundCode.value) return

  aiSummaryLoading.value = true
  aiSummaryText.value = ''

  try {
    const res = await getAIAnalysis(fundCode.value, { source: 'predict', summary_only: true })
    const data = res.data || res

    if (data && data.summary) {
      // 截取摘要前 100 字作为一句话展示
      aiSummaryText.value = data.summary.length > 100
        ? data.summary.substring(0, 100) + '...'
        : data.summary
    }
  } catch (error) {
    console.error('AI 摘要加载失败:', error)
    // 静默失败，不显示错误信息
  } finally {
    aiSummaryLoading.value = false
  }
}

// 辅助函数
function generateDateRange(days) {
  const dates = []
  const now = new Date()
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    dates.push(`${date.getMonth() + 1}/${date.getDate()}`)
  }
  return dates
}

function generateRandomFloatData(count, min, max) {
  return Array.from({ length: count }, () =>
    parseFloat((Math.random() * (max - min) + min).toFixed(2))
  )
}

// 初始化：从URL参数读取基金代码
onMounted(() => {
  const code = route.query.code
  if (code) {
    fundCode.value = code
    handlePredict()
  }
})
</script>

<style lang="scss" scoped>
.predict-page {
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

/* 控制区 */
.control-section {
  padding: 24px;
  margin-bottom: 24px;
}

.control-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;

  .input-group {
    display: flex;
    flex-direction: column;
    gap: 8px;

    label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .el-input {
      width: 200px;
    }
  }

  .button-group {
    display: flex;
    gap: 12px;
  }

  .options-group {
    margin-left: auto;
  }

  @media (max-width: $breakpoint-sm) {
    flex-direction: column;
    align-items: stretch;

    .input-group .el-input,
    .button-group {
      width: 100%;
    }

    .button-group {
      flex-direction: column;
    }

    .options-group {
      margin-left: 0;
      justify-content: flex-start;
    }
  }
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  animation: fadeIn 0.5s ease;
}

.empty-icon {
  margin-bottom: 24px;
  opacity: 0.7;
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: var(--text-muted);
  max-width: 400px;
  margin-bottom: 24px;
}

.quick-codes {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.quick-label {
  font-size: 13px;
  color: var(--text-muted);
}

.code-tag {
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

/* 主结论卡 */
.conclusion-card {
  background: linear-gradient(
    135deg,
    var(--glass-bg) 0%,
    rgba(59, 130, 246, 0.08) 100%
  );
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: $radius-xl;
  padding: 40px;
  text-align: center;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), #60a5fa);
  }
}

.conclusion-main {
  position: relative;
  z-index: 1;
}

.conclusion-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 12px;
}

.conclusion-value {
  font-size: 56px;
  font-weight: 800;
  margin-bottom: 12px;
  letter-spacing: -2px;
  transition: color $transition-normal;

  &.bullish {
    color: $positive;
    text-shadow: 0 0 40px rgba($positive, 0.3);
  }

  &.bearish {
    color: $negative;
    text-shadow: 0 0 40px rgba($negative, 0.3);
  }

  &.neutral {
    color: $neutral;
  }

  &.risk-only {
    color: $warning;
  }
}

.conclusion-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  max-width: 500px;
  margin: 0 auto 16px;
  line-height: 1.6;
}

.reliability-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: $radius-full;
  font-size: 13px;
  font-weight: 600;

  &.high {
    background: rgba($positive, 0.15);
    color: $positive;
    border: 1px solid rgba($positive, 0.3);
  }

  &.medium {
    background: rgba($warning, 0.15);
    color: $warning;
    border: 1px solid rgba($warning, 0.3);
  }

  &.low {
    background: rgba($neutral, 0.15);
    color: $neutral;
    border: 1px solid var(--border);
  }
}

/* 方向信号 */
.direction-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;

  @media (max-width: $breakpoint-sm) {
    grid-template-columns: 1fr;
  }
}

.direction-item {
  padding: 28px;
  text-align: center;
  transition: all $transition-normal;

  &:hover {
    transform: translateY(-2px);
  }

  &.active {
    border-color: var(--primary-glow);
    background: var(--primary-soft);
  }
}

.direction-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 14px;
}

.direction-value {
  font-size: 42px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;

  &.positive {
    color: $positive;
  }

  &.negative {
    color: $negative;
  }

  &.neutral {
    color: $neutral;
  }
}

/* 区间可视化 */
.interval-section {
  margin-bottom: 24px;
}

.interval-card {
  padding: 24px;
  margin-bottom: 16px;
}

.interval-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.interval-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.interval-bar-wrapper {
  margin-bottom: 12px;
}

.interval-bar {
  position: relative;
  height: 52px;
  background: var(--bg-tertiary);
  border-radius: $radius-sm;
  overflow: hidden;
}

.interval-range {
  position: absolute;
  top: 0;
  height: 100%;
  background: linear-gradient(
    90deg,
    $negative 0%,
    $neutral 50%,
    $positive 100%
  );
  border-radius: $radius-sm;
  transition: all $transition-slow;
}

.interval-center {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: white;
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
  transition: left $transition-slow;
}

.interval-labels {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;

  .negative {
    color: $negative;
  }

  .positive {
    color: $positive;
  }
}

/* 辅助点预测 */
.auxiliary-prediction {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 24px;
  background: var(--bg-tertiary);
  border-radius: $radius-md;
  border-left: 3px solid var(--text-muted);
  margin-bottom: 24px;
}

.auxiliary-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.auxiliary-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* 指标卡片 */
.metrics-section {
  margin-bottom: 24px;

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 20px;
  }
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.metric-item {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: $radius-md;
  padding: 20px;
  text-align: center;
  transition: all $transition-fast;

  &:hover {
    border-color: var(--border-strong);
  }
}

.metric-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.metric-number {
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);

  &.good {
    color: $positive;
  }

  &.bad {
    color: $negative;
  }
}

/* 图表区域 */
.chart-section {
  margin-bottom: 24px;

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 20px;
  }
}

/* AI 一句话摘要入口 */
.ai-summary-entry {
  margin-bottom: 24px;
  padding: 16px 20px;
  background: linear-gradient(
    135deg,
    var(--glass-bg) 0%,
    rgba(59, 130, 246, 0.05) 100%
  );
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: $radius-lg;
  transition: all $transition-normal;

  &:hover {
    border-color: var(--primary-glow);
    background: linear-gradient(
      135deg,
      var(--glass-bg) 0%,
      rgba(59, 130, 246, 0.1) 100%
    );
  }

  .ai-summary-content {
    display: flex;
    align-items: center;
    gap: 12px;

    .ai-icon {
      color: var(--primary);
      flex-shrink: 0;
      animation: sparkle 2s ease-in-out infinite;
    }

    .summary-text {
      font-size: 14px;
      color: var(--text-secondary);
      line-height: 1.6;
      flex: 1;

      &.loading-text {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--primary);
      }

      &.summary-unavailable {
        color: var(--text-muted);
        font-style: italic;
      }
    }

    .view-full-link {
      color: var(--primary);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      white-space: nowrap;
      transition: color $transition-fast;

      &:hover {
        color: #60a5fa;
        text-decoration: underline;
      }
    }
  }
}

/* 训练进度区域（新增） */
.training-progress {
  margin-top: 24px;
  padding: 24px;
  
  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    .progress-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
      
      &::before {
        content: '';
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #409EFF;
        border-radius: 50%;
        animation: pulse 1.5s ease-in-out infinite;
      }
    }
  }
  
  .progress-bar-wrapper {
    margin-bottom: 24px;
    
    :deep(.el-progress-bar__outer) {
      border-radius: 10px;
    }
    
    :deep(.el-progress-bar__inner) {
      border-radius: 10px;
      transition: width 0.3s ease;
    }
  }
  
  .training-info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
    
    .info-item {
      padding: 12px 16px;
      background: rgba(255, 255, 255, 0.5);
      border-radius: 8px;
      border: 1px solid var(--border);
      
      .info-label {
        font-size: 12px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
        display: block;
      }
      
      .info-value {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
        
        &.stage-text {
          color: #409EFF;
          font-size: 14px;
        }
      }
    }
  }
  
  .log-collapse {
    margin-top: 16px;
    
    :deep(.el-collapse-item__header) {
      font-size: 14px;
      color: var(--text-secondary);
    }
    
    .log-container {
      max-height: 200px;
      overflow-y: auto;
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
      font-size: 12px;
      line-height: 1.6;
      color: var(--text-secondary);
      background: rgba(0, 0, 0, 0.03);
      padding: 16px;
      border-radius: 6px;
      white-space: pre-wrap;
      word-break: break-all;
      
      &::-webkit-scrollbar {
        width: 6px;
      }
      
      &::-webkit-scrollbar-track {
        background: transparent;
      }
      
      &::-webkit-scrollbar-thumb {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 3px;
        
        &:hover {
          background: rgba(0, 0, 0, 0.3);
        }
      }
    }
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

@keyframes sparkle {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.1);
  }
}
</style>
