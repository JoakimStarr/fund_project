<template>
  <div style="max-width:1000px;margin:0 auto">
    <h2>基金画像</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <el-autocomplete
        v-model="fundCode"
        :fetch-suggestions="handleSearch"
        placeholder="输入基金代码或名称搜索"
        clearable
        style="width:100%"
        @keyup.enter="loadProfile"
        @select="handleSelect"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-autocomplete>
    </el-card>

    <template v-if="profile">
      <el-card shadow="never" style="margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
          <h3>{{ profile.fund_name }}</h3>
          <el-tag type="primary" size="small" effect="dark">{{ profile.fund_type || '--' }}</el-tag>
        </div>
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="基金代码">{{ profile.fund_code || '--' }}</el-descriptions-item>
          <el-descriptions-item label="成立日期">{{ profile.established_date || profile.established || '--' }}</el-descriptions-item>
          <el-descriptions-item label="基金规模">{{ formatNumber(profile.fund_size || profile.size) }}</el-descriptions-item>
          <el-descriptions-item label="基金经理">{{ profile.manager || '--' }}</el-descriptions-item>
          <el-descriptions-item label="基金公司">{{ profile.company || '--' }}</el-descriptions-item>
          <el-descriptions-item label="最新净值">{{ profile.latest_nav?.toFixed(4) || '--' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="4" v-for="m in metricCards" :key="m.label">
          <el-card shadow="hover" :body-style="{padding:'16px 8px',textAlign:'center'}">
            <div style="font-size:20px;font-weight:700;color:var(--primary-color)">{{ m.value }}</div>
            <div style="font-size:12px;color:#909399;margin-top:4px">{{ m.label }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-card shadow="never" style="margin-bottom:16px">
            <template #header><span style="font-weight:600">持仓明细</span></template>
            <el-table :data="holdings" size="small" stripe empty-text="暂无持仓数据" max-height="300">
              <el-table-column prop="name" label="持仓标的" min-width="140" />
              <el-table-column prop="weight" label="权重" width="90" align="center">
                <template #default="{row}">{{ (row.weight * 100).toFixed(1) }}%</template>
              </el-table-column>
              <el-table-column prop="change" label="涨跌幅" width="90" align="center">
                <template #default="{row}">{{ row.change != null ? (row.change * 100).toFixed(1) + '%' : '--' }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" style="margin-bottom:16px">
            <template #header><span style="font-weight:600">资产配置</span></template>
            <div ref="pieChartRef" style="height:260px"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">分类置信度</span></template>
        <div v-if="classificationConfidence" style="padding:8px 0">
          <div
            v-for="(val, key) in classificationConfidence"
            :key="key"
            style="display:flex;align-items:center;gap:12px;margin-bottom:10px"
          >
            <span style="width:80px;font-size:13px;color:#606266">{{ key }}</span>
            <el-progress
              :percentage="val * 100"
              :stroke-width="12"
              style="flex:1"
              :format="() => (val * 100).toFixed(0) + '%'"
            />
          </div>
        </div>
        <div v-else style="text-align:center;padding:20px;color:#909399;font-size:13px">
          暂无分类置信度数据
        </div>
      </el-card>

      <el-card v-if="hasPredictionCapability" shadow="never">
        <template #header><span style="font-weight:600">预测能力评估</span></template>
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="方向准确率">
            {{ predictionCapability.direction_accuracy != null ? (predictionCapability.direction_accuracy * 100).toFixed(1) + '%' : '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="MAE">{{ predictionCapability.mae?.toFixed(4) || '--' }}</el-descriptions-item>
          <el-descriptions-item label="模型版本">{{ predictionCapability.model_version || '--' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useFundStore } from '@/stores/fund'
import { formatNumber, formatPercent } from '@/utils/format'

const route = useRoute()
const fundStore = useFundStore()
const fundCode = ref('')
const profile = ref(null)
const holdings = ref([])
const metricCards = ref([])
const classificationConfidence = ref(null)
const predictionCapability = ref(null)
const pieChartRef = ref(null)
let pieChartInstance = null

const hasPredictionCapability = computed(() => {
  return predictionCapability.value && predictionCapability.value.direction_accuracy != null
})

watch(() => route.params.code, (code) => {
  if (code) {
    fundCode.value = code
    loadProfile()
  }
})

async function handleSearch(query, cb) {
  if (!query) return cb([])
  try {
    const data = await fundStore.searchFunds(query)
    cb((data || []).map(f => ({ value: f.fund_code + ' - ' + f.fund_name, ...f })))
  } catch {
    cb([])
  }
}

function handleSelect(item) {
  fundCode.value = item.fund_code || item.value.split(' - ')[0]
}

async function loadProfile() {
  if (!fundCode.value) return
  try {
    const data = await fundStore.fetchProfile(fundCode.value)
    profile.value = data
    if (data) {
      holdings.value = data.holdings || []
      classificationConfidence.value = data.classification_confidence || null
      predictionCapability.value = data.prediction_capability || null
      if (data.metrics) {
        metricCards.value = Object.entries(data.metrics).slice(0, 6).map(([k, v]) => ({
          label: k,
          value: typeof v === 'number' ? (v * 100).toFixed(1) + '%' : String(v)
        }))
      }
      if (data.asset_allocation) {
        initPieChart(data.asset_allocation)
      }
    }
  } catch {}
}

function initPieChart(data) {
  nextTick(() => {
    if (!pieChartRef.value) return
    import('echarts').then(echarts => {
      if (pieChartInstance) pieChartInstance.dispose()
      pieChartInstance = echarts.init(pieChartRef.value)
      const pieData = Object.entries(data).map(([name, value]) => ({ name, value: (value * 100).toFixed(1) }))
      pieChartInstance.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
        series: [{
          type: 'pie',
          radius: ['40%', '65%'],
          center: ['50%', '50%'],
          data: pieData,
          label: { formatter: '{b}\n{d}%', fontSize: 11 },
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
        }]
      })
    })
  })
}

function handleResize() {
  if (pieChartInstance) pieChartInstance.resize()
}

onMounted(() => {
  if (route.params.code) {
    fundCode.value = route.params.code
    loadProfile()
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (pieChartInstance) pieChartInstance.dispose()
})
</script>