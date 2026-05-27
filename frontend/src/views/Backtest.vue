<template>
  <PageContainer narrow>
    <div class="page-header mb-16">
      <h2 class="page-title">回测诊断</h2>
    </div>

    <SectionCard compact class="mb-16">
      <div class="backtest-search">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码"
          clearable
          class="search-input"
          @keyup.enter="loadData"
          @select="handleSelect"
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          class="date-picker"
          value-format="YYYY-MM-DD"
        />
        <el-button-group class="quick-range">
          <el-button size="small" @click="setQuickRange(7)">近一周</el-button>
          <el-button size="small" @click="setQuickRange(30)">近一月</el-button>
          <el-button size="small" @click="setQuickRange(90)">近三月</el-button>
          <el-button size="small" @click="setQuickRange(180)">近半年</el-button>
        </el-button-group>
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </SectionCard>

    <template v-if="metrics.length">
      <el-row :gutter="12" class="mb-16">
        <el-col :xs="12" :sm="8" :md="4" v-for="m in metrics" :key="m.label" class="mb-8">
          <StatCard icon="DataBoard" :value="m.value" :label="m.label" accent="var(--primary)" />
        </el-col>
      </el-row>

      <SectionCard title="实际 vs 预测走势" class="mb-16">
        <div ref="chartRef" style="height:350px" />
      </SectionCard>

      <SectionCard title="详细回测记录">
        <el-table :data="records" size="small" stripe empty-text="暂无回测记录" max-height="400">
          <el-table-column prop="date" label="日期" width="110" align="center" />
          <el-table-column label="实际涨跌" width="110" align="center">
            <template #default="{row}">
              <span :class="row.actual_return >= 0 ? 'color-up' : 'color-down'" class="font-bold">
                {{ formatPercent(row.actual_return) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="预测涨跌" width="110" align="center">
            <template #default="{row}">
              <span :class="row.predicted_return >= 0 ? 'color-up' : 'color-down'" class="font-bold">
                {{ formatPercent(row.predicted_return) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="偏差" width="100" align="center">
            <template #default="{row}">
              <span>{{ (Math.abs(row.predicted_return - row.actual_return) * 100).toFixed(2) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="方向判断" width="100" align="center">
            <template #default="{row}">
              <el-tag :type="row.direction_correct ? 'success' : 'danger'" size="small" effect="plain">
                {{ row.direction_correct ? '正确' : '错误' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="置信下限" width="110" align="center">
            <template #default="{row}">{{ formatPercent(row.confidence_lower) }}</template>
          </el-table-column>
          <el-table-column label="置信上限" width="110" align="center">
            <template #default="{row}">{{ formatPercent(row.confidence_upper) }}</template>
          </el-table-column>
        </el-table>
      </SectionCard>
    </template>
  </PageContainer>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { getBacktest } from '@/api/backtest'
import { searchFunds } from '@/api/fund'
import { formatPercent } from '@/utils/format'

const fundCode = ref('')
const dateRange = ref(null)
const loading = ref(false)
const metrics = ref([])
const records = ref([])
const chartRef = ref(null)
let chartInstance = null

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

function setQuickRange(days) {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - days)
  dateRange.value = [
    start.toISOString().split('T')[0],
    end.toISOString().split('T')[0]
  ]
}

async function loadData() {
  if (!fundCode.value) return
  loading.value = true
  metrics.value = []
  records.value = []
  try {
    const params = {}
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const data = await getBacktest(fundCode.value, params)
    if (data) {
      if (data.summary) {
        metrics.value = [
          { label: '方向准确率', value: data.summary.direction_accuracy != null ? (data.summary.direction_accuracy * 100).toFixed(1) + '%' : '--' },
          { label: 'MAE', value: data.summary.mae?.toFixed(4) || '--' },
          { label: 'RMSE', value: data.summary.rmse?.toFixed(4) || '--' },
          { label: '区间覆盖(80%)', value: data.summary.interval_coverage_80 != null ? (data.summary.interval_coverage_80 * 100).toFixed(1) + '%' : '--' },
          { label: '区间覆盖(90%)', value: data.summary.interval_coverage_90 != null ? (data.summary.interval_coverage_90 * 100).toFixed(1) + '%' : '--' },
          { label: 'Spearman', value: data.summary.spearman?.toFixed(3) || '--' },
        ]
      }
      records.value = data.records || []
      initChart(data.records || [])
    }
  } catch {} finally {
    loading.value = false
  }
}

function initChart(data) {
  nextTick(() => {
    if (!chartRef.value) return
    import('echarts').then(echarts => {
      if (chartInstance) chartInstance.dispose()
      chartInstance = echarts.init(chartRef.value)
      const dates = data.map(r => r.date)
      const actuals = data.map(r => (r.actual_return * 100).toFixed(2))
      const predicts = data.map(r => (r.predicted_return * 100).toFixed(2))
      chartInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['实际涨跌', '预测涨跌'], bottom: 0 },
        grid: { left: '3%', right: '4%', bottom: '18%', containLabel: true },
        xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
        series: [
          {
            name: '实际涨跌',
            type: 'line',
            data: actuals,
            smooth: true,
            lineStyle: { color: '#67C23A', width: 2 },
            itemStyle: { color: '#67C23A' }
          },
          {
            name: '预测涨跌',
            type: 'line',
            data: predicts,
            smooth: true,
            lineStyle: { color: '#409EFF', width: 2, type: 'dashed' },
            itemStyle: { color: '#409EFF' }
          }
        ]
      })
    })
  })
}

function handleResize() {
  if (chartInstance) chartInstance.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) chartInstance.dispose()
})
</script>

<style scoped lang="scss">
.page-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.backtest-search {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 160px;
  :deep(.el-autocomplete) { width: 100%; }
}

.date-picker {
  width: 240px;
  @media (max-width: 767px) {
    width: 100%;
  }
}

.quick-range {
  @media (max-width: 767px) {
    width: 100%;
    display: flex;
    :deep(.el-button) {
      flex: 1;
    }
  }
}
</style>