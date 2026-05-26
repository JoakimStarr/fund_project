<template>
  <div class="profile-container">
    <!-- 输入区域 -->
    <div v-if="!effectiveFundCode" class="input-section glass-card">
      <div class="input-wrapper">
        <el-input
          v-model="inputFundCode"
          placeholder="请输入6位基金代码"
          maxlength="6"
          size="large"
          clearable
          @keyup.enter="handleLoadProfile"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="large" @click="handleLoadProfile">
          查看画像
        </el-button>
      </div>
      <div class="quick-codes">
        <span class="quick-label">快捷选择：</span>
        <el-tag
          v-for="code in ['018956', '022771', '000001']"
          :key="code"
          class="code-tag"
          effect="plain"
          @click="selectQuickCode(code)"
        >
          {{ code }}
        </el-tag>
      </div>
    </div>

    <el-card v-if="loading" v-loading="loading" element-loading-text="加载基金画像中..." style="min-height: 400px;" />

    <template v-else-if="profileData.fund_code">
      <div class="profile-header">
        <h2 class="fund-name">{{ profileData.fund_name || effectiveFundCode }}</h2>
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
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'

const props = defineProps<{
  fundCode?: string
}>()

const route = useRoute()
const router = useRouter()
const inputFundCode = ref('')

const effectiveFundCode = computed(() => {
  return props.fundCode || inputFundCode.value || route.params.code || ''
})

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
  asset_allocation: Record<string, number>
  industry_distribution: Array<{name: string, value: number}>
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
  asset_allocation: {},
  industry_distribution: [],
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

// 默认颜色配置
const allocationColors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4']
const industryColors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc']

function loadProfile() {
  const code = effectiveFundCode.value
  if (!code) return

  loading.value = true

  fetch(`/api/v1/fund/${code}/profile`)
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
  // 资产配置图表
  if (allocationChartRef.value) {
    if (!allocationInstance) {
      allocationInstance = echarts.init(allocationChartRef.value)
    }
    
    // 使用真实数据或默认数据
    const allocationData = profileData.value.asset_allocation
    let chartData: Array<{name: string, value: number}> = []
    
    if (allocationData && Object.keys(allocationData).length > 0) {
      // 使用真实资产配置数据
      chartData = Object.entries(allocationData).map(([name, value], index) => ({
        name,
        value: typeof value === 'number' ? value : parseFloat(value as string) || 0,
        itemStyle: { color: allocationColors[index % allocationColors.length] }
      })).filter(item => item.value > 0)
    } else {
      // 根据基金类型推断默认配置
      const fundType = profileData.value.fund_type
      if (fundType === 'money_market') {
        chartData = [
          { name: '现金及等价物', value: 95, itemStyle: { color: '#91cc75' } },
          { name: '其他', value: 5, itemStyle: { color: '#ee6666' } }
        ]
      } else if (fundType === 'bond_pure' || fundType === 'bond_mixed') {
        chartData = [
          { name: '债券', value: 85, itemStyle: { color: '#91cc75' } },
          { name: '现金', value: 10, itemStyle: { color: '#fac858' } },
          { name: '其他', value: 5, itemStyle: { color: '#ee6666' } }
        ]
      } else {
        // 股票型/混合型默认
        chartData = [
          { name: '股票', value: 70, itemStyle: { color: '#5470c6' } },
          { name: '债券', value: 20, itemStyle: { color: '#91cc75' } },
          { name: '现金', value: 8, itemStyle: { color: '#fac858' } },
          { name: '其他', value: 2, itemStyle: { color: '#ee6666' } }
        ]
      }
    }
    
    allocationInstance.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c}% ({d}%)' },
      legend: { bottom: 0, type: 'scroll' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{d}%' },
        data: chartData,
      }],
    }, true)
  }

  // 行业分布图表
  if (industryChartRef.value) {
    if (!industryInstance) {
      industryInstance = echarts.init(industryChartRef.value)
    }
    
    const industryData = profileData.value.industry_distribution
    let chartData: Array<{name: string, value: number, itemStyle: {color: string}}> = []
    let xAxisData: string[] = []
    
    if (industryData && industryData.length > 0) {
      // 使用真实行业分布数据
      chartData = industryData.map((item, index) => ({
        name: item.name,
        value: item.value,
        itemStyle: { color: industryColors[index % industryColors.length] }
      }))
      xAxisData = industryData.map(item => item.name)
    } else {
      // 显示提示信息
      chartData = [{ name: '暂无数据', value: 0, itemStyle: { color: '#ccc' } }]
      xAxisData = ['暂无行业分布数据']
    }
    
    industryInstance.setOption({
      tooltip: { 
        trigger: 'axis', 
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0]
          return p.value > 0 ? `${p.name}: ${p.value}%` : p.name
        }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: { 
        type: 'category', 
        data: xAxisData, 
        axisLabel: { rotate: 30, fontSize: 11 } 
      },
      yAxis: { 
        type: 'value', 
        name: '占比(%)',
        max: industryData && industryData.length > 0 ? undefined : 10
      },
      series: [{
        type: 'bar',
        data: chartData,
        barMaxWidth: 40,
        label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => p.value > 0 ? p.value + '%' : '' },
      }],
    }, true)
  }
}

watch(effectiveFundCode, () => {
  loadProfile()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

function handleResize() {
  allocationInstance?.resize()
  industryInstance?.resize()
}

function handleLoadProfile() {
  if (inputFundCode.value && inputFundCode.value.length === 6) {
    router.push(`/profile/${inputFundCode.value}`)
  }
}

function selectQuickCode(code) {
  inputFundCode.value = code
  router.push(`/profile/${code}`)
}
</script>

<style scoped>
.profile-container {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.input-section {
  padding: 40px;
  text-align: center;
}

.input-wrapper {
  display: flex;
  gap: 16px;
  max-width: 500px;
  margin: 0 auto 24px;
}

.quick-codes {
  margin-top: 16px;
}

.quick-label {
  margin-right: 12px;
  color: var(--text-secondary);
}

.code-tag {
  cursor: pointer;
  margin: 4px;
  transition: all 0.2s;
}

.code-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
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
