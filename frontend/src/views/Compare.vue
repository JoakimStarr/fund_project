<template>
  <div style="max-width:1000px;margin:0 auto">
    <h2>多基金对比</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
        <el-autocomplete
          v-model="newCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码或名称添加"
          clearable
          style="flex:1"
          @keyup.enter="addFund"
          @select="handleSelect"
        />
        <el-button type="primary" :disabled="fundCodes.length < 2 || predicting" @click="doBatchPredict">
          {{ predicting ? '预测中...' : '批量预测' }}
        </el-button>
        <el-button :disabled="!fundCodes.length" @click="clearAll">清空</el-button>
      </div>
      <div>
        <el-tag
          v-for="(c, i) in fundCodes"
          :key="c"
          closable
          :type="i < 2 ? 'primary' : ''"
          style="margin:4px"
          @close="removeFund(i)"
        >
          {{ c }}
        </el-tag>
        <span v-if="!fundCodes.length" style="font-size:13px;color:#909399">请添加基金代码进行比较（最多10只）</span>
      </div>
    </el-card>

    <el-card v-if="predicting" shadow="never">
      <el-skeleton :rows="5" animated />
    </el-card>

    <template v-if="results.length">
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">预测对比</span></template>
        <el-table :data="results" size="small" stripe>
          <el-table-column prop="fund_code" label="基金代码" width="110" align="center" />
          <el-table-column prop="fund_name" label="基金名称" min-width="140" />
          <el-table-column prop="fund_type" label="类型" width="80" align="center" />
          <el-table-column label="预测涨跌" width="120" align="center">
            <template #default="{row}">
              <span :class="(row.predicted_return || 0) >= 0 ? 'color-up' : 'color-down'" class="font-bold" style="font-size:16px">
                {{ formatPercent(row.predicted_return) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="置信区间" width="160" align="center">
            <template #default="{row}">
              <span style="font-size:12px;color:#909399">
                [{{ formatPercent(row.confidence_interval?.lower) }}, {{ formatPercent(row.confidence_interval?.upper) }}]
              </span>
            </template>
          </el-table-column>
          <el-table-column label="上涨概率" width="110" align="center">
            <template #default="{row}">
              <span :style="{color:(row.direction_probability||0)>0.5?'var(--danger-color)':'var(--success-color)'}">
                {{ ((row.direction_probability || 0) * 100).toFixed(0) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><span style="font-weight:600">涨跌对比图</span></template>
        <div ref="chartRef" style="height:300px"></div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { batchPredict } from '@/api/fund'
import { searchFunds } from '@/api/fund'
import { formatPercent } from '@/utils/format'

const newCode = ref('')
const fundCodes = ref([])
const predicting = ref(false)
const results = ref([])
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
  const code = item.fund_code || item.value.split(' - ')[0]
  addCode(code)
}

function addFund() {
  if (!newCode.value) return
  const code = newCode.value.trim().split(' - ')[0]
  addCode(code)
  newCode.value = ''
}

function addCode(code) {
  if (!code) return
  if (fundCodes.value.includes(code)) return
  if (fundCodes.value.length >= 10) return
  fundCodes.value.push(code)
}

function removeFund(index) {
  fundCodes.value.splice(index, 1)
}

function clearAll() {
  fundCodes.value = []
  results.value = []
}

async function doBatchPredict() {
  if (fundCodes.value.length < 2) return
  predicting.value = true
  results.value = []
  try {
    const data = await batchPredict({ fund_codes: fundCodes.value })
    results.value = data?.results || data || []
    initChart(results.value)
  } catch {} finally {
    predicting.value = false
  }
}

function initChart(data) {
  nextTick(() => {
    if (!chartRef.value) return
    import('echarts').then(echarts => {
      if (chartInstance) chartInstance.dispose()
      chartInstance = echarts.init(chartRef.value)
      const names = data.map(r => r.fund_name || r.fund_code)
      const values = data.map(r => ((r.predicted_return || 0) * 100).toFixed(2))
      const colors = values.map(v => v >= 0 ? '#F56C6C' : '#67C23A')
      chartInstance.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: names, axisLabel: { rotate: 30, fontSize: 11 } },
        yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
        series: [{
          type: 'bar',
          data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
          barWidth: '40%',
          label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 }
        }]
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