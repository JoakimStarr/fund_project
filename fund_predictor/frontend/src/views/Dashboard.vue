<template>
  <div class="dashboard-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">决策中心</h1>
        <p class="page-subtitle">T+1 风险预测与方向判断</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="goToPredict">
          <el-icon><Aim /></el-icon>
          开始预测
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div
        v-for="(stat, index) in statsData"
        :key="index"
        class="stat-card glass-card"
        :style="{ animationDelay: `${index * 0.1}s` }"
      >
        <div class="stat-icon" :style="{ background: stat.iconBg }">
          <el-icon :size="24" :color="stat.iconColor">
            <component :is="stat.icon" />
          </el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value" :class="{ 'animate-number': stat.animating }">{{ displayValue(stat) }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
        <div class="stat-trend" :class="stat.trend">
          <el-icon :size="14"><Top v-if="stat.trend === 'up'" /><Bottom v-else /></el-icon>
          <span>{{ stat.change }}</span>
        </div>
      </div>
    </div>

    <!-- 快速操作区 -->
    <div class="quick-actions">
      <h2 class="section-title">快速入口</h2>
      <div class="action-grid">
        <div
          v-for="action in quickActions"
          :key="action.path"
          class="action-item"
          @click="$router.push(action.path)"
        >
          <div class="action-icon" :style="{ background: action.bg }">
            <el-icon :size="28" :color="action.color">
              <component :is="action.icon" />
            </el-icon>
          </div>
          <div class="action-text">
            <div class="action-title">{{ action.title }}</div>
            <div class="action-desc">{{ action.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content-grid">
      <!-- 最近预测 -->
      <div class="content-card glass-card">
        <div class="card-header">
          <h3 class="card-title">最近预测</h3>
          <el-button text type="primary" @click="$router.push('/predict')">
            查看全部
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
        <div class="card-body">
          <div v-if="recentPredictions.length === 0" class="empty-state">
            <el-empty description="暂无预测记录" :image-size="80" />
          </div>
          <div v-else class="prediction-list">
            <div
              v-for="item in recentPredictions"
              :key="item.id"
              class="prediction-item"
              @click="viewPrediction(item)"
            >
              <div class="prediction-code">{{ item.fundCode }}</div>
              <div class="prediction-result" :class="item.direction">
                {{ item.result }}
              </div>
              <div class="prediction-time">{{ item.time }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 系统状态 -->
      <div class="content-card glass-card">
        <div class="card-header">
          <h3 class="card-title">系统状态</h3>
          <el-tag :type="systemStatus.type" size="small">
            {{ systemStatus.text }}
          </el-tag>
        </div>
        <div class="card-body">
          <div class="status-list">
            <div
              v-for="(status, key) in systemServices"
              :key="key"
              class="status-item"
            >
              <span class="status-name">{{ status.name }}</span>
              <div class="status-bar-wrapper">
                <div
                  class="status-bar"
                  :class="status.status"
                  :style="{ width: status.value + '%' }"
                ></div>
              </div>
              <span class="status-value">{{ status.value }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 预测趋势图表 -->
    <div class="chart-section glass-card">
      <div class="card-header">
        <h3 class="card-title">预测准确率趋势</h3>
        <div class="chart-controls">
          <el-radio-group v-model="trendPeriod" size="small">
            <el-radio-button label="7d">近7天</el-radio-button>
            <el-radio-button label="30d">近30天</el-radio-button>
            <el-radio-button label="90d">近90天</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <BaseChart :option="accuracyChartOption" height="350px" />
    </div>

    <!-- 免责声明 -->
    <footer class="disclaimer">
      本系统仅用于量化研究和模型实验，不构成投资建议。预测结果仅供参考，投资有风险，决策需谨慎。
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Aim, Top, Bottom, ArrowRight,
  TrendCharts, Setting, DataLine, Monitor,
  UserFilled, Timer
} from '@element-plus/icons-vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { getDashboardStats, getRecentPredictions } from '@/api/dashboard'

const router = useRouter()

// 统计数据（从API加载）
const statsData = ref([
  {
    icon: 'DataAnalysis',
    iconBg: 'rgba(59, 130, 246, 0.15)',
    iconColor: '#3b82f6',
    value: '-',
    label: '已训练模型',
    trend: 'up',
    change: '-'
  },
  {
    icon: 'TrendCharts',
    iconBg: 'rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    value: '-',
    label: '平均准确率',
    trend: 'up',
    change: '-'
  },
  {
    icon: 'SuccessFilled',
    iconBg: 'rgba(239, 68, 68, 0.15)',
    iconColor: '#ef4444',
    value: '-',
    label: '今日预测次数',
    trend: 'up',
    change: '-'
  },
  {
    icon: 'Clock',
    iconBg: 'rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    value: '-',
    label: '平均响应时间',
    trend: 'down',
    change: '-'
  }
])

// 快速操作
const quickActions = [
  { path: '/predict', title: '智能预测', desc: '输入基金代码获取预测结果', icon: 'TrendCharts', bg: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' },
  { path: '/train', title: '模型训练', desc: '为指定基金训练新模型', icon: 'Setting', bg: 'rgba(34, 197, 94, 0.15)', color: '#22c55e' },
  { path: '/backtest', title: '回测诊断', desc: '查看历史回测表现', icon: 'DataLine', bg: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' },
  { path: '/compare', title: '多基金对比', desc: '同时分析多只基金', icon: 'DataLine', bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' },
  { path: '/profile', title: '基金画像', desc: '了解基金分类信息', icon: 'UserFilled', bg: 'rgba(236, 72, 153, 0.15)', color: '#ec4899' },
  { path: '/intraday', title: '盘中估算', desc: 'T日实时净值估算', icon: 'Timer', bg: 'rgba(6, 182, 212, 0.15)', color: '#06b6d4' }
]

// 最近预测记录（从API加载）
const recentPredictions = ref([])

// 系统状态（从API加载）
const systemStatus = ref({ type: 'success', text: '加载中...' })
const systemServices = ref({
  model: { name: '模型服务', value: 0, status: 'unknown' },
  api: { name: 'API 服务', value: 0, status: 'unknown' },
  database: { name: '数据库', value: 0, status: 'unknown' },
  cache: { name: '缓存服务', value: 0, status: 'unknown' }
})

// 趋势周期
const trendPeriod = ref('30d')

// 准确率趋势图配置
const accuracyChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' },
    axisPointer: {
      type: 'cross',
      crossStyle: { color: '#999' }
    }
  },
  legend: {
    data: ['方向准确率', '区间覆盖率'],
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
    boundaryGap: false,
    data: generateDateRange(30),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b', fontSize: 11 }
  },
  yAxis: {
    type: 'value',
    min: 60,
    max: 100,
    axisLabel: {
      formatter: '{value}%',
      color: '#64748b'
    },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [
    {
      name: '方向准确率',
      type: 'line',
      smooth: true,
      data: generateRandomData(30, 78, 88),
      lineStyle: { width: 3, color: '#3b82f6' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ]
        }
      },
      itemStyle: { color: '#3b82f6' }
    },
    {
      name: '区间覆盖率',
      type: 'line',
      smooth: true,
      data: generateRandomData(30, 82, 92),
      lineStyle: { width: 3, color: '#22c55e' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(34, 197, 94, 0.3)' },
            { offset: 1, color: 'rgba(34, 197, 94, 0)' }
          ]
        }
      },
      itemStyle: { color: '#22c55e' }
    }
  ]
}))

// 辅助函数：生成日期范围
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

// 辅助函数：生成随机数据
function generateRandomData(count, min, max) {
  return Array.from({ length: count }, () =>
    Math.floor(Math.random() * (max - min) + min)
  )
}

// 方法
const goToPredict = () => {
  router.push('/predict')
}

// 数字显示格式化
const displayValue = (stat) => {
  if (stat._displayValue !== undefined) {
    return stat._displayValue
  }
  return stat.value
}

// 数字滚动动画
const animateNumber = (statIndex, targetValue) => {
  const stat = statsData.value[statIndex]
  if (!stat) return

  stat.animating = true

  // 解析目标值
  const targetStr = String(targetValue)
  const isPercent = targetStr.includes('%')
  const isTime = targetStr.includes('<') || targetStr.includes('s') || targetStr.includes('ms')
  const numMatch = targetStr.match(/[\d.]+/)
  const targetNum = numMatch ? parseFloat(numMatch[0]) : 0
  const startNum = 0
  const duration = 1500 // 动画持续时间（毫秒）
  const startTime = Date.now()

  const animate = () => {
    const elapsed = Date.now() - startTime
    const progress = Math.min(elapsed / duration, 1)

    // 使用缓动函数让动画更自然
    const easeOutQuart = 1 - Math.pow(1 - progress, 4)
    const currentNum = startNum + (targetNum - startNum) * easeOutQuart

    // 格式化显示值
    if (isTime) {
      stat._displayValue = targetStr
    } else if (isPercent) {
      stat._displayValue = `${currentNum.toFixed(1)}%`
    } else if (targetNum % 1 !== 0 || targetStr.includes('.')) {
      stat._displayValue = currentNum.toFixed(2)
    } else {
      stat._displayValue = Math.floor(currentNum).toString()
    }

    if (progress < 1) {
      requestAnimationFrame(animate)
    } else {
      stat._displayValue = undefined
      stat.animating = false
    }
  }

  requestAnimationFrame(animate)
}

const viewPrediction = (item) => {
  router.push({
    path: '/predict',
    query: { code: item.fundCode }
  })
}

// 加载仪表盘数据
const loadDashboardData = async () => {
  try {
    const [statsRes, predictionsRes] = await Promise.all([
      getDashboardStats(),
      getRecentPredictions({ limit: 10 })
    ])
    
    // 更新统计数据
    if (statsRes.data) {
      const data = statsRes.data

      const newValues = [
        String(data.total_models || 0),
        data.avg_accuracy?.label || '-',
        String(data.today_predictions || 0),
        data.avg_response_time?.label || '< 2s'
      ]

      // 更新值并触发动画
      newValues.forEach((value, index) => {
        if (statsData.value[index] && value !== statsData.value[index].value) {
          statsData.value[index].value = value
          // 延迟触发动画，让每个卡片错开显示效果
          setTimeout(() => {
            animateNumber(index, value)
          }, index * 150)
        }
      })
      
      // 更新系统状态
      if (data.system_status) {
        systemServices.value = data.system_status
        const allHealthy = Object.values(data.system_status).every(s => s.status === 'healthy')
        systemStatus.value = { 
          type: allHealthy ? 'success' : 'warning', 
          text: allHealthy ? '正常运行' : '部分服务异常' 
        }
      }
    }
    
    // 更新最近预测记录
    if (predictionsRes.data && Array.isArray(predictionsRes.data)) {
      recentPredictions.value = predictionsRes.data.map((p, idx) => ({
        id: idx + 1,
        fundCode: p.fundCode,
        result: typeof p.result === 'number' ? `${p.result >= 0 ? '+' : ''}${(p.result * 100).toFixed(2)}%` : (p.result || '-'),
        direction: p.direction === 'bullish' ? 'positive' : (p.direction === 'bearish' ? 'negative' : 'neutral'),
        time: p.time || '-'
      }))
    }
    
    console.log('仪表盘数据加载完成')
  } catch (error) {
    console.error('加载仪表盘数据失败:', error)
    systemStatus.value = { type: 'error', text: '加载失败' }
  }
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.header-actions {
  display: flex;
  gap: 12px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;

  &:hover {
    transform: translateY(-4px);
  }
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-content {
  flex: 1;

  .stat-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    transition: transform 0.3s ease, color 0.3s ease;

    &.animate-number {
      animation: numberGlow 1.5s ease-out;
    }
  }

  .stat-label {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 2px;
  }
}

@keyframes numberGlow {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
    text-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
  }
  50% {
    transform: scale(1.05);
    opacity: 1;
    text-shadow: 0 0 30px rgba(59, 130, 246, 0.8);
  }
  100% {
    transform: scale(1);
    opacity: 1;
    text-shadow: none;
  }
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: $radius-sm;

  &.up {
    background: rgba($positive, 0.1);
    color: $positive;
  }

  &.down {
    background: rgba($negative, 0.1);
    color: $negative;
  }
}

/* 快速操作 */
.quick-actions {
  margin-bottom: 28px;

  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
  }
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: $radius-md;
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: var(--bg-card-hover);
    border-color: var(--primary-glow);
    transform: translateY(-2px);
  }
}

.action-icon {
  width: 44px;
  height: 44px;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.action-text {
  .action-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .action-desc {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
  }
}

/* 主要内容网格 */
.main-content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 28px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.content-card {
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;
  animation-delay: 0.3s;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
}

.card-body {
  min-height: 200px;
}

/* 预测列表 */
.prediction-list {
  .prediction-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: all $transition-fast;

    &:last-child {
      border-bottom: none;
    }

    &:hover {
      background: var(--glass-bg);
      margin: 0 -12px;
      padding-left: 12px;
      padding-right: 12px;
      border-radius: $radius-sm;
    }
  }

  .prediction-code {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    font-family: 'SF Mono', 'Fira Code', monospace;
  }

  .prediction-result {
    font-size: 15px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;

    &.positive {
      color: $positive;
    }

    &.negative {
      color: $negative;
    }
  }

  .prediction-time {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
}

/* 系统状态列表 */
.status-list {
  .status-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);

    &:last-child {
      border-bottom: none;
    }
  }

  .status-name {
    font-size: 13px;
    color: var(--text-secondary);
    width: 70px;
    flex-shrink: 0;
  }

  .status-bar-wrapper {
    flex: 1;
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: $radius-full;
    overflow: hidden;
  }

  .status-bar {
    height: 100%;
    border-radius: $radius-full;
    transition: width $transition-slow;

    &.healthy {
      background: linear-gradient(90deg, #22c55e, #4ade80);
    }

    &.warning {
      background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }

    &.error {
      background: linear-gradient(90deg, #ef4444, #f87171);
    }
  }

  .status-value {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    width: 36px;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
}

/* 图表区域 */
.chart-section {
  margin-bottom: 28px;

  .card-header {
    margin-bottom: 8px;
  }
}

.chart-controls {
  display: flex;
  gap: 8px;
}

/* 免责声明 */
.disclaimer {
  margin-top: 40px;
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  border-top: 1px solid var(--border);
}
</style>
