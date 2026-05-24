<template>
  <div class="backtest-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">回测诊断</h1>
        <p class="page-subtitle">查看模型历史预测表现与实际对比</p>
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
            @keyup.enter="loadBacktestData"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="input-group">
          <label>时间范围</label>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            size="large"
            :shortcuts="dateShortcuts"
          />
        </div>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          @click="loadBacktestData"
        >
          <el-icon><Search /></el-icon>
          查询
        </el-button>
      </div>
    </div>

    <!-- 回测概览指标 -->
    <div v-if="hasData" class="metrics-grid">
      <div
        v-for="(metric, index) in backtestMetrics"
        :key="index"
        class="metric-card glass-card"
        :style="{ animationDelay: `${index * 0.1}s` }"
      >
        <div class="metric-header">
          <span class="metric-label">{{ metric.label }}</span>
          <el-tooltip :content="metric.tooltip" placement="top">
            <el-icon color="#64748b" :size="14"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="metric-value" :class="metric.status">
          {{ metric.value }}
        </div>
        <div class="metric-trend" :class="metric.trend > 0 ? 'up' : 'down'">
          <el-icon :size="12"><Top v-if="metric.trend > 0" /><Bottom v-else /></el-icon>
          {{ Math.abs(metric.trend) }}%
        </div>
      </div>
    </div>

    <!-- 主图表区域 -->
    <div v-if="hasData" class="chart-section glass-card">
      <div class="chart-header">
        <h3 class="section-title">实际值 vs 预测值</h3>
        <div class="chart-controls">
          <el-radio-group v-model="chartType" size="small">
            <el-radio-button label="line">折线图</el-radio-button>
            <el-radio-button label="scatter">散点图</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <BaseChart
        :option="mainChartOption"
        height="400px"
        :loading="loading"
      />
    </div>

    <!-- 区间覆盖率分析 -->
    <div v-if="hasData" class="analysis-grid">
      <div class="analysis-card glass-card">
        <h3 class="section-title">区间覆盖率</h3>
        <BaseChart
          :option="coverageChartOption"
          height="300px"
        />
      </div>

      <div class="analysis-card glass-card">
        <h3 class="section-title">方向准确率分布</h3>
        <BaseChart
          :option="directionChartOption"
          height="300px"
        />
      </div>
    </div>

    <!-- 详细数据表格 -->
    <div v-if="hasData" class="table-section glass-card">
      <div class="table-header">
        <h3 class="section-title">详细数据</h3>
        <el-button text type="primary" @click="exportData">
          <el-icon><Download /></el-icon>
          导出数据
        </el-button>
      </div>

      <el-table
        :data="backtestTableData"
        stripe
        style="width: 100%"
        max-height="400"
        empty-text="暂无数据"
      >
        <el-table-column prop="date" label="日期" width="120" fixed />
        <el-table-column prop="actual" label="实际涨跌幅" width="120">
          <template #default="{ row }">
            <span :class="row.actual >= 0 ? 'text-positive' : 'text-negative'">
              {{ row.actual >= 0 ? '+' : '' }}{{ row.actual }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="predicted" label="预测点值" width="120">
          <template #default="{ row }">
            {{ row.predicted >= 0 ? '+' : '' }}{{ row.predicted }}%
          </template>
        </el-table-column>
        <el-table-column prop="interval80Lower" label="80%区间下界" width="120" />
        <el-table-column prop="interval80Upper" label="80%区间上界" width="120" />
        <el-table-column prop="interval90Lower" label="90%区间下界" width="120" />
        <el-table-column prop="interval90Upper" label="90%区间上界" width="120" />
        <el-table-column prop="direction" label="预测方向" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.direction === 'up' ? 'danger' : row.direction === 'down' ? 'success' : 'info'"
              size="small"
            >
              {{ directionText(row.direction) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inInterval" label="在区间内" width="100">
          <template #default="{ row }">
            <el-icon v-if="row.inInterval" color="#22c55e"><CircleCheckFilled /></el-icon>
            <el-icon v-else color="#ef4444"><CircleCloseFilled /></el-icon>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 空状态 -->
    <div v-if="!hasData && !loading" class="empty-state glass-card">
      <el-empty description="请选择基金代码并查询回测数据" :image-size="120" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Search, Top, Bottom, InfoFilled,
  Download, CircleCheckFilled, CircleCloseFilled
} from '@element-plus/icons-vue'
import { getBacktestData } from '@/api/fund'
import BaseChart from '@/components/common/BaseChart.vue'

// 状态
const fundCode = ref('018956')
const dateRange = ref([])
const loading = ref(false)
const hasData = ref(false)
const chartType = ref('line')

// 日期快捷选项
const dateShortcuts = [
  {
    text: '最近一周',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
      return [start, end]
    }
  },
  {
    text: '最近一月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
      return [start, end]
    }
  },
  {
    text: '最近三月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 90)
      return [start, end]
    }
  }
]

// 回测指标（从API加载）
const backtestMetrics = ref([
  { label: '区间覆盖率(80%)', value: '-', tooltip: '实际值落在80%预测区间的比例', status: '', trend: 0 },
  { label: '区间覆盖率(90%)', value: '-', tooltip: '实际值落在90%预测区间的比例', status: '', trend: 0 },
  { label: '方向准确率', value: '-', tooltip: '预测方向正确的比例', status: '', trend: 0 },
  { label: '平均绝对误差(MAE)', value: '-', tooltip: '预测值与实际值的平均偏差', status: '', trend: 0 },
  { label: '均方根误差(RMSE)', value: '-', tooltip: '预测误差的标准差', status: '', trend: 0 },
  { label: '皮尔逊相关系数', value: '-', tooltip: '预测值与实际值的相关性', status: '', trend: 0 }
])

// 表格数据（从API加载）
const backtestTableData = ref([])

// 主图表配置
const mainChartOption = computed(() => {
  if (chartType.value === 'line') {
    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(59, 130, 246, 0.3)',
        textStyle: { color: '#f8fafc' },
        axisPointer: { type: 'cross' }
      },
      legend: {
        data: ['实际值', '预测值', '80%区间', '90%区间'],
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
        data: backtestTableData.value.map(d => d.date),
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisLabel: { color: '#64748b', fontSize: 11, rotate: 45 }
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
          data: backtestTableData.value.map(d => d.actual),
          lineStyle: { width: 2, color: '#94a3b8' },
          itemStyle: { color: '#94a3b8' },
          symbol: 'none'
        },
        {
          name: '预测值',
          type: 'line',
          data: backtestTableData.value.map(d => d.predicted),
          lineStyle: { width: 3, color: '#3b82f6' },
          itemStyle: { color: '#3b82f6' },
          symbol: 'none'
        },
        {
          name: '80%区间上界',
          type: 'line',
          data: backtestTableData.value.map(d => d.interval80Upper),
          lineStyle: { width: 1, color: 'rgba(239, 68, 68, 0.4)', type: 'dashed' },
          areaStyle: { color: 'rgba(239, 68, 68, 0.03)' },
          symbol: 'none'
        },
        {
          name: '80%区间下界',
          type: 'line',
          data: backtestTableData.value.map(d => d.interval80Lower),
          lineStyle: { width: 1, color: 'rgba(34, 197, 94, 0.4)', type: 'dashed' },
          areaStyle: { color: 'rgba(34, 197, 94, 0.03)' },
          symbol: 'none'
        }
      ]
    }
  }

  // 散点图模式
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(59, 130, 246, 0.3)',
      textStyle: { color: '#f8fafc' },
      formatter: (params) => {
        return `${params.data[2]}<br/>预测: ${params.data[0]}%<br/>实际: ${params.data[1]}%`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '预测值(%)',
      axisLabel: {
        formatter: '{value}%',
        color: '#64748b'
      },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
    },
    yAxis: {
      type: 'value',
      name: '实际值(%)',
      axisLabel: {
        formatter: '{value}%',
        color: '#64748b'
      },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
    },
    series: [{
      type: 'scatter',
      data: backtestTableData.value.map(d => [d.predicted, d.actual, d.date]),
      symbolSize: 8,
      itemStyle: {
        color: 'rgba(59, 130, 246, 0.7)',
        borderColor: '#3b82f6',
        borderWidth: 1
      }
    }, {
      type: 'line',
      data: [[-5, -5], [5, 5]],
      lineStyle: { width: 2, color: '#ef4444', type: 'dashed' },
      symbol: 'none',
      tooltip: { show: false }
    }]
  }
})

// 区间覆盖率图表
const coverageChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' }
  },
  legend: {
    data: ['80%置信区间', '90%置信区间'],
    top: 10,
    textStyle: { color: '#94a3b8' }
  },
  radar: {
    indicator: [
      { name: '上涨日', max: 100 },
      { name: '下跌日', max: 100 },
      { name: '震荡日', max: 100 },
      { name: '高波动日', max: 100 },
      { name: '低波动日', max: 100 }
    ],
    shape: 'circle',
    axisName: { color: '#94a3b8' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    splitArea: { areaStyle: { color: ['rgba(59, 130, 246, 0.02)', 'rgba(59, 130, 246, 0.04)'] } }
  },
  series: [{
    type: 'radar',
    data: [
      {
        value: [85, 78, 88, 72, 91],
        name: '80%置信区间',
        areaStyle: { color: 'rgba(59, 130, 246, 0.3)' },
        lineStyle: { color: '#3b82f6' },
        itemStyle: { color: '#3b82f6' }
      },
      {
        value: [92, 89, 95, 84, 97],
        name: '90%置信区间',
        areaStyle: { color: 'rgba(34, 197, 94, 0.2)' },
        lineStyle: { color: '#22c55e' },
        itemStyle: { color: '#22c55e' }
      }
    ]
  }]
}))

// 方向准确率图表
const directionChartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' },
    formatter: '{a}<br/>{b}: {c}% ({d}%)'
  },
  legend: {
    orient: 'vertical',
    right: '5%',
    top: 'center',
    textStyle: { color: '#94a3b8' }
  },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    center: ['40%', '50%'],
    avoidLabelOverlap: false,
    itemStyle: {
      borderRadius: 8,
      borderColor: '#0b1220',
      borderWidth: 2
    },
    label: { show: false },
    emphasis: {
      label: { show: true, fontSize: 14, fontWeight: 'bold' }
    },
    data: [
      { value: 78, name: '正确', itemStyle: { color: '#22c55e' } },
      { value: 18, name: '错误', itemStyle: { color: '#ef4444' } },
      { value: 4, name: '中性', itemStyle: { color: '#94a3b8' } }
    ]
  }]
}))

// 方法
const loadBacktestData = async () => {
  if (!fundCode.value.trim()) {
    return
  }

  loading.value = true

  try {
    const res = await getBacktestData(fundCode.value)
    const data = res.data || res
    console.log('回测数据:', data)
    
    // 更新回测指标
    if (data.metrics) {
      const m = data.metrics
      backtestMetrics.value[0].value = m.interval_coverage_80 ? `${m.interval_coverage_80 * 100:.1f}%` : '-'
      backtestMetrics.value[1].value = m.interval_coverage_90 ? `${m.interval_coverage_90 * 100:.1f}%` : '-'
      backtestMetrics.value[2].value = m.direction_accuracy ? `${m.direction_accuracy * 100:.1f}%` : '-'
      backtestMetrics.value[3].value = m.mae ? `${(m.mae * 100).toFixed(2)}%` : '-'
      backtestMetrics.value[4].value = m.rmse ? `${(m.rmse * 100).toFixed(2)}%` : '-'
      backtestMetrics.value[5].value = m.correlation ? m.correlation.toFixed(3) : '-'
      
      // 设置状态
      backtestMetrics.value.forEach((metric, i) => {
        const val = parseFloat(metric.value)
        if (!isNaN(val)) {
          if (i < 3) { // 覆盖率和准确率，越高越好
            metric.status = val >= 70 ? 'good' : (val >= 50 ? 'neutral' : 'bad')
          } else if (i === 5) { // 相关系数，越高越好
            metric.status = val >= 0.7 ? 'good' : (val >= 0.4 ? 'neutral' : 'bad')
          } else { // MAE/RMSE，越低越好
            metric.status = val <= 1 ? 'good' : (val <= 2 ? 'neutral' : 'bad')
          }
        }
      })
    }
    
    // 更新表格数据
    if (data.backtest && Array.isArray(data.backtest)) {
      backtestTableData.value = data.backtest.map(row => ({
        date: row.date || row.trade_date || '',
        actual: row.target_next || row.actual || 0,
        predicted: row.pred_return || row.predicted || 0,
        interval80Lower: row.nav_interval_80_lower || row.lower_80 || null,
        interval80Upper: row.nav_interval_80_upper || row.upper_80 || null,
        interval90Lower: row.nav_interval_90_lower || row.lower_90 || null,
        interval90Upper: row.nav_interval_90_upper || row.upper_90 || null,
        direction: row.direction_signal || row.direction || 'neutral',
        inInterval: row.in_interval !== undefined ? row.in_interval : true
      }))
    } else if (data.table_data) {
      backtestTableData.value = data.table_data
    }
    
    hasData.value = !!backtestTableData.value.length

  } catch (error) {
    console.error('加载回测数据失败:', error)
    hasData.value = false
  } finally {
    loading.value = false
  }
}

const exportData = () => {
  if (!backtestTableData.value.length) {
    alert('暂无数据可导出')
    return
  }
  
  // 导出CSV
  const headers = ['日期', '实际值', '预测值', '80%区间下限', '80%区间上限', '90%区间下限', '90%区间上限', '方向', '在区间内']
  const rows = backtestTableData.value.map(d => [
    d.date, 
    typeof d.actual === 'number' ? d.actual.toFixed(2) : d.actual,
    typeof d.predicted === 'number' ? d.predicted.toFixed(2) : d.predicted,
    d.interval80Lower, d.interval80Upper,
    d.interval90Lower, d.interval90Upper,
    directionText(d.direction), d.inInterval
  ])
  
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `backtest_${fundCode.value}_${new Date().toISOString().slice(0,10)}.csv`
  link.click()
}

const directionText = (dir) => {
  const map = { up: '看涨', down: '看跌', neutral: '中性' }
  return map[dir] || dir
}

onMounted(() => {
  // 自动加载默认基金代码的回测数据
  if (fundCode.value) {
    loadBacktestData()
  }
})
</script>

<style lang="scss" scoped>
.backtest-page {
  max-width: 1400px;
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
  }

  @media (max-width: $breakpoint-sm) {
    flex-direction: column;
    align-items: stretch;

    .input-group {
      width: 100%;
    }
  }
}

/* 指标卡片 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  padding: 20px;
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;

  &:hover {
    transform: translateY(-2px);
  }
}

.metric-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.metric-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  margin-bottom: 8px;

  &.good {
    color: $positive;
  }

  &.neutral {
    color: $warning;
  }

  &.bad {
    color: $negative;
  }
}

.metric-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  padding: 2px 8px;
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

/* 图表区域 */
.chart-section,
.analysis-grid,
.table-section {
  margin-bottom: 24px;
}

.chart-header,
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
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

.chart-controls {
  display: flex;
  gap: 8px;
}

.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.analysis-card {
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;
  animation-delay: 0.2s;
}

/* 表格样式 */
.text-positive {
  color: $positive;
  font-weight: 600;
}

.text-negative {
  color: $negative;
  font-weight: 600;
}

/* 空状态 */
.empty-state {
  padding: 60px 20px;
  text-align: center;
}
</style>
