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
  Search, Aim, Setting, TrendCharts
} from '@element-plus/icons-vue'
import { predictFund, getFundProfile } from '@/api/fund'
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

// 快捷代码
const quickCodes = ['018956', '000001', '110011', '161725', '519778']

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
  } catch (error) {
    errorMessage.value = error.message || '预测失败，请稍后重试'
    console.error('预测失败:', error)
  } finally {
    predicting.value = false
  }
}

const handleTrain = async () => {
  // 跳转到训练页面或直接调用训练API
  // 这里简化处理，实际应该跳转到训练页面
  const { startTraining } = await import('@/api/train')

  training.value = true

  try {
    const res = await startTraining({
      fund_code: fundCode.value,
      force: forceRetrain.value
    })

    if (res.task_id) {
      // 训练任务已创建，可以轮询状态
      console.log('训练任务ID:', res.task_id)
      errorMessage.value = ''
      // 可以显示训练进度...
    }
  } catch (error) {
    errorMessage.value = error.message || '训练启动失败'
  } finally {
    training.value = false
  }
}

const selectQuickCode = (code) => {
  fundCode.value = code
  handlePredict()
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
</style>
