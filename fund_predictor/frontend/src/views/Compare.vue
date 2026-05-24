<template>
  <div class="compare-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">多基金对比</h1>
        <p class="page-subtitle">同时查看多只基金的预测结果，辅助投资决策</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="addFund">
          <el-icon><Plus /></el-icon>
          添加基金
        </el-button>
        <el-button @click="clearAll">
          <el-icon><Delete /></el-icon>
          清空
        </el-button>
      </div>
    </div>

    <!-- 基金选择区 -->
    <div class="selection-section glass-card">
      <div class="selection-row">
        <div class="fund-tags">
          <el-tag
            v-for="(code, index) in selectedFunds"
            :key="index"
            closable
            size="large"
            effect="dark"
            class="fund-tag"
            @close="removeFund(index)"
          >
            {{ code }}
          </el-tag>

          <el-input
            v-if="showAddInput"
            ref="addInputRef"
            v-model="newFundCode"
            placeholder="输入6位代码"
            maxlength="6"
            size="large"
            class="add-input"
            @keyup.enter="confirmAdd"
            @blur="cancelAdd"
          />
        </div>
      </div>

      <!-- 快捷添加 -->
      <div class="quick-add" v-if="selectedFunds.length === 0">
        <span class="quick-label">推荐对比：</span>
        <el-tag
          v-for="code in recommendedFunds"
          :key="code"
          effect="plain"
          class="quick-tag"
          @click="quickAdd(code)"
        >
          {{ code }}
        </el-tag>
      </div>
    </div>

    <!-- 对比结果 -->
    <div v-if="selectedFunds.length > 0" class="compare-results">
      <!-- 对比表格 -->
      <div class="table-section glass-card">
        <h3 class="section-title">预测结果对比</h3>
        <el-table
          :data="comparisonData"
          stripe
          style="width: 100%"
          :header-cell-style="{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }"
        >
          <el-table-column prop="fundCode" label="基金代码" width="120" fixed>
            <template #default="{ row }">
              <span class="font-mono font-bold">{{ row.fundCode }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="conclusion" label="预测结论" width="140">
            <template #default="{ row }">
              <span :class="row.directionClass">{{ row.conclusion }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="upProbability" label="上涨概率" width="110" align="center">
            <template #default="{ row }">
              <span :class="row.upProbability > 50 ? 'text-positive' : ''">
                {{ row.upProbability }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="downProbability" label="下跌概率" width="110" align="center">
            <template #default="{ row }">
              <span :class="row.downProbability > 50 ? 'text-negative' : ''">
                {{ row.downProbability }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="interval80" label="80%区间" min-width="180" />
          <el-table-column prop="interval90" label="90%区间" min-width="180" />
          <el-table-column prop="reliability" label="可信度" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.reliabilityType" size="small">
                {{ row.reliability }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="accuracy" label="模型准确率" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.accuracy >= 80 ? 'text-positive' : row.accuracy >= 70 ? '' : 'text-negative'">
                {{ row.accuracy }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 对比图表 -->
      <div class="charts-grid">
        <div class="chart-card glass-card">
          <h3 class="section-title">方向概率对比</h3>
          <BaseChart :option="directionCompareOption" height="350px" />
        </div>

        <div class="chart-card glass-card">
          <h3 class="section-title">风险区间对比</h3>
          <BaseChart :option="intervalCompareOption" height="350px" />
        </div>
      </div>

      <!-- 详细卡片视图 -->
      <div class="cards-grid">
        <div
          v-for="(item, index) in comparisonData"
          :key="index"
          class="fund-detail-card glass-card"
          :style="{ animationDelay: `${index * 0.1}s` }"
        >
          <div class="card-header-custom">
            <div class="fund-code-large">{{ item.fundCode }}</div>
            <el-tag :type="item.reliabilityType" size="small">{{ item.reliability }}</el-tag>
          </div>

          <div class="prediction-main" :class="item.directionClass">
            {{ item.conclusion }}
          </div>

          <div class="probability-bars">
            <div class="prob-bar">
              <span class="prob-label">看涨</span>
              <div class="bar-wrapper">
                <div class="bar-fill up" :style="{ width: item.upProbability + '%' }"></div>
              </div>
              <span class="prob-value text-positive">{{ item.upProbability }}%</span>
            </div>
            <div class="prob-bar">
              <span class="prob-label">看跌</span>
              <div class="bar-wrapper">
                <div class="bar-fill down" :style="{ width: item.downProbability + '%' }"></div>
              </div>
              <span class="prob-value text-negative">{{ item.downProbability }}%</span>
            </div>
          </div>

          <div class="interval-info">
            <div class="interval-item">
              <span class="interval-label">80%区间</span>
              <span class="interval-value">{{ item.interval80 }}</span>
            </div>
            <div class="interval-item">
              <span class="interval-label">90%区间</span>
              <span class="interval-value">{{ item.interval90 }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state glass-card">
      <el-empty description="请添加要对比的基金代码" :image-size="120">
        <el-button type="primary" @click="addFund">添加基金</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import BaseChart from '@/components/common/BaseChart.vue'

// 状态
const selectedFunds = ref(['018956', '000001'])
const showAddInput = ref(false)
const newFundCode = ref('')
const addInputRef = ref(null)

// 推荐基金
const recommendedFunds = ['110011', '161725', '519778', '000300', '002011']

// 对比数据（模拟）
const comparisonData = computed(() => {
  return selectedFunds.value.map(code => {
    const baseData = generateRandomPrediction(code)
    return baseData
  })
})

// 方向概率对比图配置
const directionCompareOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' }
  },
  legend: {
    data: ['上涨概率', '下跌概率'],
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
    data: selectedFunds.value,
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b' }
  },
  yAxis: {
    type: 'value',
    max: 100,
    axisLabel: {
      formatter: '{value}%',
      color: '#64748b'
    },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [
    {
      name: '上涨概率',
      type: 'bar',
      stack: 'total',
      data: comparisonData.value.map(d => d.upProbability),
      barWidth: '40%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#ef4444' },
          { offset: 1, color: '#dc2626' }
        ])
      }
    },
    {
      name: '下跌概率',
      type: 'bar',
      stack: 'total',
      data: comparisonData.value.map(d => d.downProbability),
      itemStyle: {
        borderRadius: [0, 0, 4, 4],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#22c55e' },
          { offset: 1, color: '#16a34a' }
        ])
      }
    }
  ]
}))

// 区间对比图配置
const intervalCompareOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' }
  },
  legend: {
    data: ['80%下界', '80%上界', '90%下界', '90%上界'],
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
    data: selectedFunds.value,
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b' }
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
      name: '80%下界',
      type: 'bar',
      data: comparisonData.value.map(d => parseFloat(d.interval80.split('~')[0])),
      itemStyle: { color: '#ef4444', opacity: 0.7 }
    },
    {
      name: '80%上界',
      type: 'bar',
      data: comparisonData.value.map(d => parseFloat(d.interval80.split('~')[1])),
      itemStyle: { color: '#22c55e', opacity: 0.7 }
    },
    {
      name: '90%下界',
      type: 'line',
      data: comparisonData.value.map(d => parseFloat(d.interval90.split('~')[0])),
      lineStyle: { type: 'dashed', color: '#f59e0b' },
      symbol: 'circle',
      symbolSize: 6
    },
    {
      name: '90%上界',
      type: 'line',
      data: comparisonData.value.map(d => parseFloat(d.interval90.split('~')[1])),
      lineStyle: { type: 'dashed', color: '#06b6d4' },
      symbol: 'circle',
      symbolSize: 6
    }
  ]
}))

// 方法
const addFund = () => {
  showAddInput.value = true
  nextTick(() => {
    addInputRef.value?.focus()
  })
}

const confirmAdd = () => {
  const code = newFundCode.value.trim()
  if (code && /^\d{6}$/.test(code) && !selectedFunds.value.includes(code)) {
    selectedFunds.value.push(code)
  }
  cancelAdd()
}

const cancelAdd = () => {
  showAddInput.value = false
  newFundCode.value = ''
}

const removeFund = (index) => {
  selectedFunds.value.splice(index, 1)
}

const quickAdd = (code) => {
  if (!selectedFunds.value.includes(code)) {
    selectedFunds.value.push(code)
  }
}

const clearAll = () => {
  selectedFunds.value = []
}

// 辅助函数：生成随机预测数据
function generateRandomPrediction(code) {
  const upProb = Math.floor(Math.random() * 50 + 25)
  const downProb = Math.floor(Math.random() * 30 + 10)
  const conclusion = (Math.random() * 2 - 1).toFixed(2)

  return {
    fundCode: code,
    conclusion: `${conclusion >= 0 ? '+' : ''}${conclusion}%`,
    directionClass: conclusion > 0.2 ? 'bullish' : conclusion < -0.2 ? 'bearish' : 'neutral',
    upProbability: upProb,
    downProbability: downProb,
    interval80: `${(Math.random() * -2 - 0.5).toFixed(2)}% ~ ${(Math.random() * 2 + 0.5).toFixed(2)}%`,
    interval90: `${(Math.random() * -3 - 1).toFixed(2)}% ~ ${(Math.random() * 3 + 1).toFixed(2)}%`,
    reliability: ['高', '中', '低'][Math.floor(Math.random() * 3)],
    reliabilityType: ['success', 'warning', 'info'][Math.floor(Math.random() * 3)],
    accuracy: Math.floor(Math.random() * 20 + 70)
  }
}
</script>

<style lang="scss" scoped>
.compare-page {
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

/* 选择区域 */
.selection-section {
  padding: 20px 24px;
  margin-bottom: 24px;
}

.selection-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.fund-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  flex: 1;
  align-items: center;
}

.fund-tag {
  font-family: 'SF Mono', monospace;
  font-size: 14px;
  padding: 8px 14px;
}

.add-input {
  width: 160px;

  :deep(.el-input__wrapper) {
    background: var(--bg-tertiary);
  }
}

.quick-add {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.quick-label {
  font-size: 13px;
  color: var(--text-muted);
}

.quick-tag {
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

/* 对比结果 */
.compare-results {
  animation: fadeIn 0.5s ease;
}

.table-section,
.charts-grid,
.cards-grid {
  margin-bottom: 24px;
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

.font-mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.font-bold {
  font-weight: 700;
}

.text-positive {
  color: $positive !important;
  font-weight: 600;
}

.text-negative {
  color: $negative !important;
  font-weight: 600;
}

/* 图表网格 */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  animation: fadeIn 0.5s ease;
}

/* 卡片网格 */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.fund-detail-card {
  padding: 24px;
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;

  &:hover {
    transform: translateY(-4px);
  }
}

.card-header-custom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.fund-code-large {
  font-size: 18px;
  font-weight: 700;
  font-family: 'SF Mono', monospace;
  color: var(--primary);
}

.prediction-main {
  font-size: 36px;
  font-weight: 800;
  text-align: center;
  margin-bottom: 20px;
  letter-spacing: -1px;

  &.bullish {
    color: $positive;
  }

  &.bearish {
    color: $negative;
  }

  &.neutral {
    color: $neutral;
  }
}

.probability-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.prob-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.prob-label {
  font-size: 12px;
  color: var(--text-muted);
  width: 36px;
}

.bar-wrapper {
  flex: 1;
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: $radius-full;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: $radius-full;
  transition: width $transition-slow;

  &.up {
    background: linear-gradient(90deg, #dc2626, #ef4444);
  }

  &.down {
    background: linear-gradient(90deg, #16a34a, #22c55e);
  }
}

.prob-value {
  font-size: 13px;
  font-weight: 600;
  width: 45px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.interval-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.interval-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.interval-label {
  color: var(--text-muted);
}

.interval-value {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* 空状态 */
.empty-state {
  padding: 60px 20px;
  text-align: center;
}
</style>
