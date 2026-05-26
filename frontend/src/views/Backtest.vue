<template>
  <div style="max-width:1000px;margin:0 auto">
    <h2>回测诊断</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:center">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码"
          clearable
          style="flex:1"
          @keyup.enter="loadData"
          @select="handleSelect"
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width:260px"
          value-format="YYYY-MM-DD"
        />
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </el-card>

    <template v-if="metrics.length">
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="4" v-for="m in metrics" :key="m.label">
          <el-card shadow="hover" :body-style="{padding:'16px 8px',textAlign:'center'}">
            <div style="font-size:22px;font-weight:700;color:var(--primary-color)">{{ m.value }}</div>
            <div style="font-size:12px;color:#909399;margin-top:4px">{{ m.label }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">实际 vs 预测走势</span></template>
        <div ref="chartRef" style="height:350px"></div>
      </el-card>

      <el-card shadow="never">
        <template #header><span style="font-weight:600">详细回测记录</span></template>
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
              <el-tag
                :type="row.direction_correct ? 'success' : 'danger'"
                size="small"
                effect="plain"
              >
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
      </el-card>
    </template>
  </div>
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