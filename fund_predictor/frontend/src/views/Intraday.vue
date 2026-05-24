<template>
  <div class="intraday-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">T日盘中估算</h1>
        <p class="page-subtitle">基于持仓和行情数据，实时估算当日基金净值</p>
      </div>
      <div class="header-actions">
        <div class="current-time" :class="{ 'is-live': isMarketOpen }">
          <span class="time-dot"></span>
          {{ currentTime }}
        </div>
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
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="input-group">
          <label>估算模式</label>
          <el-select v-model="estimateMode" size="large" style="width: 160px;">
            <el-option label="实时估算" value="realtime" />
            <el-option label="快照模式" value="snapshot" />
          </el-select>
        </div>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          @click="startEstimate"
        >
          <el-icon><VideoPlay /></el-icon>
          开始估算
        </el-button>

        <el-button
          :type="estimating ? 'danger' : 'info'"
          size="large"
          @click="toggleAutoRefresh"
        >
          <el-icon><Timer /></el-icon>
          {{ estimating ? '停止' : '自动刷新' }}
        </el-button>
      </div>
    </div>

    <!-- 估算结果 -->
    <div v-if="hasResult" class="result-section">
      <!-- 主要估值卡片 -->
      <div class="main-estimate-card glass-card">
        <div class="estimate-header">
          <div class="fund-info">
            <span class="code">{{ estimateData.fundCode }}</span>
            <span class="name">{{ estimateData.fundName }}</span>
          </div>
          <el-tag :type="marketStatusType" effect="dark">
            {{ marketStatusText }}
          </el-tag>
        </div>

        <div class="estimate-main">
          <div class="nav-value-section">
            <div class="nav-label">估算净值</div>
            <div class="nav-value" :class="estimateData.changeClass">
              {{ estimateData.estimatedNav }}
            </div>
          </div>

          <div class="change-section">
            <div class="change-item">
              <span class="change-label">估算涨跌</span>
              <span class="change-value" :class="estimateData.changeClass">
                {{ estimateData.estimatedChange }}
              </span>
            </div>
            <div class="change-item">
              <span class="change-label">涨跌幅</span>
              <span class="change-value" :class="estimateData.changeClass">
                {{ estimateData.changePercent }}
              </span>
            </div>
          </div>
        </div>

        <div class="confidence-bar">
          <span class="confidence-label">置信度</span>
          <el-progress
            :percentage="estimateData.confidence"
            :stroke-width="10"
            :color="confidenceColor(estimateData.confidence)"
            :format="(val) => val + '%'"
          />
        </div>
      </div>

      <!-- 详细数据网格 -->
      <div class="detail-grid">
        <!-- 持仓贡献 -->
        <div class="detail-card glass-card">
          <h3 class="section-title">重仓股贡献</h3>
          <el-table
            :data="estimateData.topHoldings"
            stripe
            style="width: 100%"
            size="small"
            max-height="300"
          >
            <el-table-column prop="name" label="股票名称" min-width="120" />
            <el-table-column prop="code" label="代码" width="90">
              <template #default="{ row }">
                <span class="font-mono">{{ row.code }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="weight" label="仓位%" width="80" align="right">
              <template #default="{ row }">
                {{ row.weight }}%
              </template>
            </el-table-column>
            <el-table-column prop="change" label="个股涨跌%" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.change >= 0 ? 'text-positive' : 'text-negative'">
                  {{ row.change >= 0 ? '+' : '' }}{{ row.change }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="contribution" label="贡献" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.contribution >= 0 ? 'text-positive' : 'text-negative'">
                  {{ row.contribution >= 0 ? '+' : '' }}{{ row.contribution }}bp
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 分项贡献 -->
        <div class="detail-card glass-card">
          <h3 class="section-title">分项贡献分析</h3>
          <BaseChart :option="contributionChartOption" height="280px" />
        </div>
      </div>

      <!-- 实时走势图 -->
      <div class="chart-section glass-card">
        <div class="chart-header">
          <h3 class="section-title">日内净值估算走势</h3>
          <div class="chart-info">
            <span class="update-time">更新于: {{ lastUpdateTime }}</span>
          </div>
        </div>
        <BaseChart :option="intradayChartOption" height="350px" />
      </div>

      <!-- 估算说明 -->
      <div class="notice-section glass-card">
        <h3 class="section-title">估算说明</h3>
        <div class="notice-content">
          <el-alert
            title="估算原理"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <p>
                基于最新披露的持仓数据（季报/中报）和实时行情，加权计算各成分证券的涨跌幅贡献，
                再加上现金、债券等固定收益类资产的预估收益，得出当日净值的估算值。
              </p>
            </template>
          </el-alert>

          <div class="warning-items">
            <div class="warning-item">
              <el-icon color="#f59e0b"><WarningFilled /></el-icon>
              <span>持仓数据存在滞后性，实际持仓可能与披露时点有差异</span>
            </div>
            <div class="warning-item">
              <el-icon color="#f59e0b"><WarningFilled /></el-icon>
              <span>未考虑交易费用、申赎影响等因素</span>
            </div>
            <div class="warning-item">
              <el-icon color="#f59e0b"><WarningFilled /></el-icon>
              <span>估算结果仅供参考，不作为投资依据</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state glass-card">
      <div class="empty-content">
        <el-icon :size="64" color="#3b82f6"><Timer /></el-icon>
        <h3>T日盘中估算</h3>
        <p>输入基金代码，系统将根据持仓和实时行情估算当日净值</p>
        <el-button type="primary" @click="startEstimate">开始估算</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import {
  Search, VideoPlay, Timer, WarningFilled
} from '@element-plus/icons-vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { getLatestIntraday } from '@/api/intraday'

// 状态
const fundCode = ref('018956')
const estimateMode = ref('realtime')
const loading = ref(false)
const hasResult = ref(false)
const estimating = ref(false)
const currentTime = ref('')
const lastUpdateTime = ref('')
const isMarketOpen = ref(true)

// 自动刷新定时器
let autoRefreshTimer = null
let timeUpdateTimer = null

// 估算数据（从API加载）
const estimateData = reactive({
  fundCode: '',
  fundName: '',
  estimatedNav: '-',
  estimatedChange: '-',
  changePercent: '-',
  changeClass: 'neutral',
  confidence: 0,
  topHoldings: [],
  contributions: {
    stocks: 0,
    bonds: 0,
    cash: 0,
    other: 0,
    fee: 0
  }
})

// 市场状态
const marketStatusType = computed(() => isMarketOpen.value ? 'success' : 'info')
const marketStatusText = computed(() => isMarketOpen.value ? '交易中' : '已收盘')

// 日内走势图配置
const intradayChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' },
    formatter: (params) => {
      const data = params[0]
      return `${data.axisValue}<br/>估算净值: ${data.data[1]}<br/>涨跌幅: ${data.data[2]}%`
    }
  },
  legend: {
    data: ['估算净值', '前日净值'],
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
    data: generateIntradayTime(),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
      rotate: 30
    }
  },
  yAxis: {
    type: 'value',
    name: '净值',
    min: (value) => value.min - 0.005,
    max: (value) => value.max + 0.005,
    axisLabel: {
      color: '#64748b',
      formatter: '{value}'
    },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [
    {
      name: '估算净值',
      type: 'line',
      smooth: false,
      data: generateIntradayNavData(),
      lineStyle: { width: 2, color: '#3b82f6' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59, 130, 246, 0.25)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ]
        }
      },
      itemStyle: { color: '#3b82f6' },
      symbol: 'none',
      markLine: {
        data: [{ yAxis: 1.2334, name: '前日净值' }],
        lineStyle: { color: '#94a3b8', type: 'dashed' },
        label: { formatter: '前日净值: {c}' }
      }
    }
  ]
}))

// 贡献图表配置
const contributionChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' },
    formatter: '{b}: +{c} bp'
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'value',
    axisLabel: {
      color: '#64748b',
      formatter: '{value}'
    },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  yAxis: {
    type: 'category',
    data: ['费用扣除', '其他资产', '现金类', '债券类', '股票投资'],
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b' }
  },
  series: [{
    type: 'bar',
    data: [
      { value: Math.abs(estimateData.contributions.fee), itemStyle: { color: '#ef4444' } },
      { value: Math.abs(estimateData.contributions.other), itemStyle: { color: '#a855f7' } },
      { value: estimateData.contributions.cash, itemStyle: { color: '#06b6d4' } },
      { value: estimateData.contributions.bonds, itemStyle: { color: '#22c55e' } },
      { value: estimateData.contributions.stocks, itemStyle: { color: '#3b82f6' } }
    ],
    barWidth: '60%',
    itemStyle: {
      borderRadius: [0, 4, 4, 0]
    },
    label: {
      show: true,
      position: 'right',
      color: '#94a3b8',
      formatter: (params) => `${params.data.value > 0 ? '+' : ''}${params.data.value} bp`
    }
  }]
}))

// 方法
const startEstimate = async () => {
  if (!fundCode.value.trim()) return

  loading.value = true

  try {
    const res = await getLatestIntraday(fundCode.value)
    const data = res.data || res
    console.log('盘中估算数据:', data)
    
    if (data) {
      estimateData.fundCode = fundCode.value
      estimateData.fundName = data.fund_name || `基金 ${fundCode.value}`
      estimateData.estimatedNav = data.estimated_nav ? data.estimated_nav.toFixed(4) : '-'
      
      const change = data.estimated_change || 0
      estimateData.estimatedChange = change >= 0 ? `+${change.toFixed(4)}` : change.toFixed(4)
      estimateData.changePercent = `${(data.change_percent || 0).toFixed(2)}%`
      estimateData.changeClass = (data.change_percent || 0) >= 0 ? 'positive' : 'negative'
      estimateData.confidence = Math.round((data.confidence || 0) * 100)
      
      // 持仓贡献（如果有）
      if (data.holdings && Array.isArray(data.holdings)) {
        estimateData.topHoldings = data.holdings.slice(0, 5).map(h => ({
          name: h.name,
          code: h.code,
          weight: h.weight || 0,
          change: h.change || 0,
          contribution: h.contribution || 0
        }))
      }
      
      // 贡献分解（如果有）
      if (data.contributions) {
        estimateData.contributions = data.contributions
      }
    }

    hasResult.value = true
    lastUpdateTime.value = formatTime(new Date())

    // 如果是实时模式，自动开启刷新
    if (estimateMode.value === 'realtime') {
      toggleAutoRefresh()
    }
  } catch (error) {
    console.error('估算失败:', error)
    hasResult.value = false
  } finally {
    loading.value = false
  }
}

const toggleAutoRefresh = () => {
  if (estimating.value) {
    // 停止刷新
    estimating.value = false
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer)
      autoRefreshTimer = null
    }
  } else {
    // 开始刷新 - 重新调用API获取最新数据
    estimating.value = true
    autoRefreshTimer = setInterval(async () => {
      try {
        const res = await getLatestIntraday(fundCode.value)
        const data = res.data || res
        
        if (data && data.estimated_nav !== undefined) {
          const change = data.estimated_change || 0
          estimateData.estimatedNav = data.estimated_nav.toFixed(4)
          estimateData.estimatedChange = change >= 0 ? `+${change.toFixed(4)}` : change.toFixed(4)
          estimateData.changePercent = `${(data.change_percent || 0).toFixed(2)}%`
          estimateData.changeClass = (data.change_percent || 0) >= 0 ? 'positive' : 'negative'
          estimateData.confidence = Math.round((data.confidence || 0) * 100)
        }
        
        lastUpdateTime.value = formatTime(new Date())
      } catch (error) {
        console.error('刷新估算失败:', error)
      }
    }, 5000) // 每5秒更新一次
  }
}

const confidenceColor = (value) => {
  if (value >= 85) return '#22c55e'
  if (value >= 70) return '#f59e0b'
  return '#ef4444'
}

// 辅助函数
function generateIntradayTime() {
  const times = []
  for (let h = 9; h <= 11; h++) {
    for (let m = 0; m < 60; m += 5) {
      if (h === 11 && m > 30) continue
      times.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
    }
  }
  for (let h = 13; h <= 15; h++) {
    for (let m = 0; m < 60; m += 5) {
      if (h === 15 && m > 0) break
      times.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
    }
  }
  return times
}

function generateIntradayNavData() {
  const times = generateIntradayTime()
  let nav = 1.2334
  return times.map((_, i) => {
    nav += (Math.random() - 0.48) * 0.002
    const changePercent = ((nav - 1.2334) / 1.2334 * 100).toFixed(2)
    return [i, parseFloat(nav.toFixed(4)), parseFloat(changePercent)]
  })
}

function formatTime(date) {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function updateTime() {
  const now = new Date()
  currentTime.value = formatTime(now)

  // 判断是否在交易时间
  const hour = now.getHours()
  const minute = now.getMinutes()
  const time = hour * 60 + minute
  isMarketOpen.value = (time >= 9 * 60 + 30 && time <= 11 * 60 + 30) ||
                       (time >= 13 * 60 && time <= 15 * 60)
}

// 生命周期
onMounted(() => {
  updateTime()
  timeUpdateTimer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
  if (timeUpdateTimer) clearInterval(timeUpdateTimer)
})
</script>

<style lang="scss" scoped>
.intraday-page {
  max-width: 1200px;
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
  align-items: center;
  gap: 16px;
}

.current-time {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-tertiary);
  border-radius: $radius-full;
  font-family: 'SF Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);

  &.is-live .time-dot {
    background: $success;
    animation: pulse 2s ease-in-out infinite;
  }

  .time-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: $neutral;
  }
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

  @media (max-width: $breakpoint-sm) {
    flex-direction: column;
    align-items: stretch;

    .input-group .el-input,
    .el-select {
      width: 100% !important;
    }
  }
}

/* 结果区域 */
.result-section {
  animation: fadeIn 0.5s ease;
}

/* 主估值卡片 */
.main-estimate-card {
  margin-bottom: 24px;
  padding: 32px;
}

.estimate-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;

  .fund-info {
    display: flex;
    align-items: baseline;
    gap: 12px;

    .code {
      font-size: 20px;
      font-weight: 700;
      font-family: 'SF Mono', monospace;
      color: var(--primary);
    }

    .name {
      font-size: 15px;
      color: var(--text-secondary);
    }
  }
}

.estimate-main {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 40px;
  align-items: center;
  margin-bottom: 28px;

  @media (max-width: $breakpoint-sm) {
    grid-template-columns: 1fr;
    text-align: center;
  }
}

.nav-value-section {
  .nav-label {
    font-size: 13px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
  }

  .nav-value {
    font-size: 56px;
    font-weight: 800;
    letter-spacing: -2px;
    font-variant-numeric: tabular-nums;
    transition: color $transition-normal;

    &.positive {
      color: $positive;
      text-shadow: 0 0 40px rgba($positive, 0.2);
    }

    &.negative {
      color: $negative;
      text-shadow: 0 0 40px rgba($negative, 0.2);
    }
  }
}

.change-section {
  display: flex;
  gap: 32px;

  @media (max-width: $breakpoint-sm) {
    justify-content: center;
  }

  .change-item {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .change-label {
      font-size: 12px;
      color: var(--text-muted);
    }

    .change-value {
      font-size: 26px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;

      &.positive {
        color: $positive;
      }

      &.negative {
        color: $negative;
      }
    }
  }
}

.confidence-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid var(--border);

  .confidence-label {
    font-size: 13px;
    color: var(--text-muted);
    min-width: 50px;
  }

  .el-progress {
    flex: 1;
  }
}

/* 详细数据 */
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.detail-card {
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
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

.font-mono {
  font-family: 'SF Mono', monospace;
}

.text-positive {
  color: $positive;
  font-weight: 600;
}

.text-negative {
  color: $negative;
  font-weight: 600;
}

.text-primary {
  color: var(--primary);
}

/* 图表区域 */
.chart-section,
.notice-section {
  margin-bottom: 24px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .update-time {
    font-size: 12px;
    color: var(--text-muted);
    font-family: 'SF Mono', monospace;
  }
}

/* 说明区域 */
.notice-content {
  .el-alert {
    margin-bottom: 16px;

    p {
      margin: 8px 0 0;
      font-size: 13px;
      color: var(--text-secondary);
      line-height: 1.6;
    }
  }
}

.warning-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.warning-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);

  .el-icon {
    margin-top: 2px;
    flex-shrink: 0;
  }
}

/* 空状态 */
.empty-state {
  padding: 80px 20px;
  text-align: center;
}

.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;

  h3 {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
  }

  p {
    font-size: 14px;
    color: var(--text-muted);
    max-width: 400px;
  }
}
</style>
