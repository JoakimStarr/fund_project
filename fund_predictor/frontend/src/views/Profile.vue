<template>
  <div class="profile-container">
    <el-card v-if="loading" v-loading="loading" element-loading-text="加载基金画像中..." style="min-height: 400px;" />

    <template v-else-if="profileData.fund_code">
      <div class="profile-header">
        <h2 class="fund-name">{{ profileData.fund_name || fundCode }}</h2>
        <div class="header-tags">
          <el-tag :type="typeTagType" size="large" effect="dark">{{ typeLabel }}</el-tag>
          <el-tag v-if="profileData.cache_info?.stale" type="warning" size="small">数据可能过期</el-tag>
          <el-tag :type="predictionSuitable ? 'success' : 'danger'" size="small">
            {{ predictionSuitable ? '适合预测' : '不适合预测' }}
          </el-tag>
        </div>
      </div>

      <el-row :gutter="20" class="info-section">
        <el-col :span="6" v-for="(metric, index) in displayMetrics" :key="index">
          <div class="metric-item">
            <span class="metric-label">{{ metric.label }}</span>
            <span class="metric-value">{{ metric.value }}</span>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-section">
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header><span>资产配置</span></template>
            <div ref="allocationChartRef" style="height: 300px;"></div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="hover">
            <template #header><span>行业分布</span></template>
            <div ref="industryChartRef" style="height: 300px;"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="analysis-section">
        <el-col :span="24">
          <el-card shadow="hover">
            <template #header><span>策略与风险分析</span></template>
            <div class="strategy-content">
              <div class="benchmark-info">
                <span class="label">业绩比较基准：</span>
                <span class="value">{{ profileData.benchmark || '-' }}</span>
              </div>
              <div class="risk-score-display">
                <span class="label">风险等级：</span>
                <el-tag :type="riskTagType">{{ profileData.risk_level || '未知' }}</el-tag>
              </div>
              <div class="keywords-section" v-if="profileData.strategy_keywords && profileData.strategy_keywords.length > 0">
                <span class="label">投资关键词：</span>
                <el-tag v-for="(keyword, idx) in profileData.strategy_keywords" :key="idx" class="keyword-tag" effect="plain" type="primary" size="small">
                  {{ keyword }}
                </el-tag>
              </div>
              <div class="strategy-description" v-if="profileData.strategy_text">
                <p>{{ profileData.strategy_text }}</p>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-empty v-else description="请输入有效的基金代码查看画像信息" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  fundCode: string
}>()

const loading = ref(false)
const allocationChartRef = ref<HTMLElement | null>(null)
const industryChartRef = ref<HTMLElement | null>(null)

interface CacheInfo {
  cached: boolean
  fetched_at: string
  expires_at: string
  ttl_days: number
  data_source: string
  stale: boolean
}

interface ProfileData {
  fund_code: string
  fund_name: string
  fund_type: string
  fund_type_raw: string
  establish_date: string
  fund_size: number | null
  manager: string
  fee_rate: number | null
  benchmark: string
  strategy_text: string
  strategy_keywords: string[]
  skip_prediction: boolean
  risk_level: string
  cache_info: CacheInfo | null
}

const profileData = ref<ProfileData>({
  fund_code: '',
  fund_name: '',
  fund_type: '',
  fund_type_raw: '',
  establish_date: '',
  fund_size: null,
  manager: '',
  fee_rate: null,
  benchmark: '',
  strategy_text: '',
  strategy_keywords: [],
  skip_prediction: false,
  risk_level: '',
  cache_info: null,
})

let allocationInstance: echarts.ECharts | null = null
let industryInstance: echarts.ECharts | null = null

const typeTagType = computed(() => {
  const map: Record<string, string> = {
    hybrid_equity: 'danger',
    equity_active: 'danger',
    index_equity: 'warning',
    hybrid_flexible: '',
    hybrid_balanced: '',
    bond_mixed: 'success',
    bond_pure: 'success',
    money_market: 'info',
    fof: '',
    unknown: 'info',
  }
  return map[profileData.value.fund_type] || 'info'
})

const typeLabel = computed(() => {
  const map: Record<string, string> = {
    hybrid_equity: '混合-偏股',
    equity_active: '股票型',
    index_equity: '指数型',
    hybrid_flexible: '混合-灵活',
    hybrid_balanced: '混合-平衡',
    bond_mixed: '债券型',
    bond_pure: '纯债基金',
    money_market: '货币基金',
    fof: 'FOF基金',
    unknown: '未知类型',
  }
  return map[profileData.value.fund_type] || profileData.value.fund_type_raw || '未知'
})

const predictionSuitable = computed(() => !profileData.value.skip_prediction)

const riskTagType = computed(() => {
  const level = profileData.value.risk_level || ''
  if (level.includes('低')) return 'success'
  if (level.includes('中低')) return ''
  if (level.includes('中')) return 'warning'
  if (level.includes('高')) return 'danger'
  return 'info'
})

const displayMetrics = computed(() => {
  const data = profileData.value
  return [
    { label: '基金代码', value: data.fund_code || '-' },
    { label: '成立日期', value: data.establish_date || '-' },
    { label: '规模(亿)', value: data.fund_size != null ? `${data.fund_size.toFixed(2)}亿` : '-' },
    { label: '基金经理', value: data.manager || '-' },
    { label: '管理费率', value: data.fee_rate != null ? `${data.fee_rate}%` : '-' },
    { label: '原始类型', value: data.fund_type_raw || '-' },
  ]
})

const defaultAllocation = [
  { name: '股票', value: 60, color: '#5470c6' },
  { name: '债券', value: 25, color: '#91cc75' },
  { name: '现金', value: 10, color: '#fac858' },
  { name: '其他', value: 5, color: '#ee6666' },
]

const defaultIndustry = [
  { name: '待获取持仓数据', value: 1, color: '#ccc' },
]

function loadProfile() {
  if (!props.fundCode) return

  loading.value = true

  fetch(`/api/v1/fund/${props.fundCode}/profile`)
    .then(res => res.json())
    .then(res => {
      if (res.ok) {
        profileData.value = { ...profileData.value, ...res.data }
      } else {
        console.error('Failed to load profile:', res.error)
      }

      nextTick(() => {
        renderCharts()
      })
    })
    .catch(err => console.error('Error fetching profile:', err))
    .finally(() => {
      loading.value = false
    })
}

function renderCharts() {
  if (allocationChartRef.value) {
    if (!allocationInstance) {
      allocationInstance = echarts.init(allocationChartRef.value)
    }
    allocationInstance.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, type: 'scroll' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{d}%' },
        data: defaultAllocation,
      }],
    }, true)
  }

  if (industryChartRef.value) {
    if (!industryInstance) {
      industryInstance = echarts.init(industryChartRef.value)
    }
    industryInstance.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: defaultIndustry.map(i => i.name), axisLabel: { rotate: 30, fontSize: 11 } },
      yAxis: { type: 'value', name: '占比(%)' },
      series: [{
        type: 'bar',
        data: defaultIndustry.map(i => ({ value: i.value * 100, itemStyle: { color: i.color } })),
        barMaxWidth: 40,
        label: { show: true, position: 'top', fontSize: 11 },
      }],
    }, true)
  }
}

watch(() => props.fundCode, () => {
  loadProfile()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

function handleResize() {
  allocationInstance?.resize()
  industryInstance?.resize()
}
</script>

<style scoped>
.profile-container {
  padding: 16px;
}

.profile-header {
  margin-bottom: 24px;
  text-align: center;
}

.fund-name {
  font-size: 22px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 12px;
}

.header-tags {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.info-section {
  margin-bottom: 20px;
}

.metric-item {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 18px 14px;
  text-align: center;
  transition: transform 0.3s ease;
}

.metric-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.metric-label {
  display: block;
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}

.metric-value {
  display: block;
  color: #303133;
  font-weight: bold;
  font-size: 17px;
}

.charts-section,
.analysis-section {
  margin-top: 20px;
}

.strategy-content > div {
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.strategy-content > div:last-child {
  border-bottom: none;
}

.label {
  font-weight: bold;
  color: #606266;
  margin-right: 8px;
}

.value {
  color: #303133;
}

.keyword-tag {
  margin-right: 8px;
  margin-top: 4px;
}

.strategy-description p {
  line-height: 1.7;
  color: #606266;
  margin: 8px 0 0 0;
}
</style>
