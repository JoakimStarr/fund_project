<template>
  <div class="profile-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">基金画像</h1>
        <p class="page-subtitle">了解基金的分类信息、投资策略和风险特征</p>
      </div>
    </div>

    <!-- 搜索区 -->
    <div class="search-section glass-card">
      <div class="search-row">
        <el-input
          v-model="fundCode"
          placeholder="请输入6位基金代码"
          maxlength="6"
          size="large"
          clearable
          @keyup.enter="loadProfile"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="large" :loading="loading" @click="loadProfile">
          查询画像
        </el-button>
      </div>

      <!-- 快捷选择 -->
      <div class="quick-codes">
        <span class="quick-label">热门基金：</span>
        <el-tag
          v-for="code in hotFunds"
          :key="code"
          effect="plain"
          @click="selectFund(code)"
        >
          {{ code }}
        </el-tag>
      </div>
    </div>

    <!-- 基金画像结果 -->
    <div v-if="hasProfile" class="profile-content">
      <!-- 基本信息 -->
      <div class="info-grid">
        <div class="info-card glass-card main-info">
          <div class="fund-header">
            <div class="fund-code-large">{{ profileData.fundCode }}</div>
            <el-tag :type="profileData.typeTagType" size="large" effect="dark">
              {{ profileData.fundType }}
            </el-tag>
          </div>
          <h2 class="fund-name">{{ profileData.fundName }}</h2>
          <p class="fund-desc">{{ profileData.description }}</p>

          <div class="key-metrics">
            <div class="metric-item">
              <span class="metric-label">基金规模</span>
              <span class="metric-value">{{ profileData.fundSize }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">成立日期</span>
              <span class="metric-value">{{ profileData.establishDate }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">基金经理</span>
              <span class="metric-value">{{ profileData.manager }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">管理费率</span>
              <span class="metric-value">{{ profileData.feeRate }}</span>
            </div>
          </div>
        </div>

        <!-- 风险评级 -->
        <div class="info-card glass-card risk-card">
          <h3 class="card-title-custom">风险评估</h3>
          <div class="risk-gauge">
            <el-progress
              type="dashboard"
              :percentage="profileData.riskScore"
              :width="140"
              :stroke-width="12"
              :color="riskColor(profileData.riskScore)"
              :format="(val) => val + '分'"
            />
          </div>
          <div class="risk-level">
            <span class="level-text">{{ profileData.riskLevel }}</span>
            <span class="level-desc">{{ profileData.riskDescription }}</span>
          </div>
          <div class="risk-factors">
            <div v-for="factor in profileData.riskFactors" :key="factor.name" class="factor-item">
              <span class="factor-name">{{ factor.name }}</span>
              <div class="factor-bar-wrapper">
                <div
                  class="factor-bar"
                  :style="{ width: factor.value + '%', background: factor.color }"
                ></div>
              </div>
              <span class="factor-value">{{ factor.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 投资策略 -->
      <div class="strategy-section glass-card">
        <h3 class="section-title">投资策略分析</h3>
        <div class="strategy-content">
          <div class="strategy-tags">
            <span class="tag-label">策略关键词：</span>
            <el-tag
              v-for="keyword in profileData.strategyKeywords"
              :key="keyword"
              effect="plain"
              type="primary"
              class="strategy-tag"
            >
              {{ keyword }}
            </el-tag>
          </div>

          <div class="benchmark-info">
            <span class="label">业绩比较基准</span>
            <span class="value">{{ profileData.benchmark }}</span>
          </div>

          <div class="strategy-description">
            {{ profileData.strategyDesc }}
          </div>
        </div>
      </div>

      <!-- 资产配置 -->
      <div class="allocation-section glass-card">
        <h3 class="section-title">资产配置（估算）</h3>
        <div class="allocation-content">
          <BaseChart :option="allocationChartOption" height="320px" />
          <div class="allocation-legend">
            <div
              v-for="item in profileData.allocation"
              :key="item.name"
              class="legend-item"
            >
              <span class="legend-color" :style="{ background: item.color }"></span>
              <span class="legend-name">{{ item.name }}</span>
              <span class="legend-value">{{ item.percentage }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 行业分布 -->
      <div class="industry-section glass-card">
        <h3 class="section-title">行业分布</h3>
        <BaseChart :option="industryChartOption" height="300px" />
      </div>

      <!-- 预测适用性 -->
      <div class="prediction-suitability glass-card">
        <h3 class="section-title">预测模型适用性</h3>
        <div class="suitability-grid">
          <div class="suitability-card" :class="profileData.predictionSuitable ? 'suitable' : 'not-suitable'">
            <el-icon :size="32" :color="profileData.predictionSuitable ? '#22c55e' : '#ef4444'">
              <component :is="profileData.predictionSuitable ? 'CircleCheckFilled' : 'WarningFilled'" />
            </el-icon>
            <div class="suitability-text">
              <strong>{{ profileData.predictionSuitable ? '适用' : '不适用' }}</strong>
              <p>{{ profileData.predictionReason }}</p>
            </div>
          </div>

          <div class="metrics-mini-grid">
            <div class="mini-metric">
              <span class="mini-label">历史波动率</span>
              <span class="mini-value">{{ profileData.volatility }}</span>
            </div>
            <div class="mini-metric">
              <span class="mini-label">数据充足度</span>
              <span class="mini-value text-positive">{{ profileData.dataSufficiency }}</span>
            </div>
            <div class="mini-metric">
              <span class="mini-label">特征丰富度</span>
              <span class="mini-value text-primary">{{ profileData.featureRichness }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state glass-card">
      <el-empty description="请输入基金代码查询画像信息" :image-size="120" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import { getFundProfile } from '@/api/fund'
import BaseChart from '@/components/common/BaseChart.vue'

// 状态
const fundCode = ref('018956')
const loading = ref(false)
const hasProfile = ref(false)

// 热门基金
const hotFunds = ['018956', '000001', '110011', '161725', '519778', '000300']

// 基金画像数据（模拟）
const profileData = ref({
  fundCode: '018956',
  fundName: '财通资管新能源汽车混合A',
  fundType: '混合型-偏股',
  typeTagType: '',
  description: '主要投资于新能源汽车产业链相关的优质上市公司，追求长期资本增值。',
  fundSize: '52.36亿',
  establishDate: '2021-09-28',
  manager: '张三',
  feeRate: '1.50%',
  riskScore: 72,
  riskLevel: '中高风险',
  riskDescription: '适合风险承受能力较强的投资者',
  riskFactors: [
    { name: '市场风险', value: 75, color: '#ef4444' },
    { name: '行业集中', value: 68, color: '#f59e0b' },
    { name: '流动性', value: 45, color: '#22c55e' }
  ],
  strategyKeywords: ['新能源汽车', '新能源', '智能制造', '绿色低碳'],
  benchmark: '沪深300指数收益率*70%+中债综合财富(总值)指数收益率*30%',
  strategyDesc: '本基金采用自上而下与自下而上相结合的投资策略，重点关注新能源汽车产业链中的优质企业，通过深入研究行业发展趋势和公司基本面，精选具有核心竞争力和成长潜力的个股进行投资。',
  allocation: [
    { name: '股票', percentage: 85, color: '#3b82f6' },
    { name: '债券', percentage: 8, color: '#22c55e' },
    { name: '现金', percentage: 5, color: '#94a3b8' },
    { name: '其他', percentage: 2, color: '#a855f7' }
  ],
  industryDistribution: [
    { name: '电力设备', value: 35 },
    { name: '汽车', value: 25 },
    { name: '有色金属', value: 15 },
    { name: '化工', value: 10 },
    { name: '电子', value: 8 },
    { name: '其他', value: 7 }
  ],
  predictionSuitable: true,
  predictionReason: '该基金为偏股混合型，净值变动具有较好的可预测性，且历史数据充足。',
  volatility: '24.5%',
  dataSufficiency: '优秀',
  featureRichness: '良好'
})

// 图表配置
const allocationChartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' },
    formatter: '{b}: {c}% ({d}%)'
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
    data: profileData.value.allocation.map(item => ({
      value: item.percentage,
      name: item.name,
      itemStyle: { color: item.color }
    }))
  }]
}))

const industryChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    textStyle: { color: '#f8fafc' }
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
      formatter: '{value}%',
      color: '#64748b'
    },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  yAxis: {
    type: 'category',
    data: profileData.value.industryDistribution.map(d => d.name),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b' }
  },
  series: [{
    type: 'bar',
    data: profileData.value.industryDistribution.map((d, i) => ({
      value: d.value,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#3b82f6' },
          { offset: 1, color: `hsl(${220 + i * 20}, 80%, 60%)` }
        ])
      }
    })),
    barWidth: '60%'
  }]
}))

// 方法
const loadProfile = async () => {
  if (!fundCode.value.trim()) return

  loading.value = true

  try {
    const res = await getFundProfile(fundCode.value)
    console.log('基金画像:', res.data)

    // 更新数据...
    hasProfile.value = true

    // 根据类型设置标签颜色
    const typeMap = {
      '股票型': 'danger',
      '混合型': 'warning',
      '债券型': 'success',
      '货币型': 'info',
      '指数型': ''
    }

    // 简单匹配类型
    for (const [type, tagType] of Object.entries(typeMap)) {
      if (res.data?.fund_type?.includes(type)) {
        profileData.value.typeTagType = tagType
        break
      }
    }
  } catch (error) {
    console.error('加载画像失败:', error)
    hasProfile.value = false
  } finally {
    loading.value = false
  }
}

const selectFund = (code) => {
  fundCode.value = code
  loadProfile()
}

// 辅助函数
const riskColor = (score) => {
  if (score >= 80) return '#ef4444'
  if (score >= 60) return '#f59e0b'
  return '#22c55e'
}

onMounted(() => {
  // 自动加载默认基金
  loadProfile()
})
</script>

<style lang="scss" scoped>
.profile-page {
  max-width: 1200px;
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

/* 搜索区域 */
.search-section {
  padding: 24px;
  margin-bottom: 24px;
}

.search-row {
  display: flex;
  gap: 12px;

  .el-input {
    width: 280px;
  }
}

.quick-codes {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.quick-label {
  font-size: 13px;
  color: var(--text-muted);

  .el-tag {
    cursor: pointer;
    transition: all $transition-fast;

    &:hover {
      border-color: var(--primary);
      color: var(--primary);
    }
  }
}

/* 内容区域 */
.profile-content {
  animation: fadeIn 0.5s ease;
}

/* 信息网格 */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 20px;
  margin-bottom: 24px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.info-card {
  animation: fadeIn 0.5s ease forwards;
  opacity: 0;
}

/* 主信息卡片 */
.main-info {
  padding: 28px;
  animation-delay: 0s;
}

.fund-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.fund-code-large {
  font-size: 24px;
  font-weight: 800;
  font-family: 'SF Mono', monospace;
  color: var(--primary);
}

.fund-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.fund-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
}

.key-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.metric-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 风险卡片 */
.risk-card {
  padding: 28px;
  animation-delay: 0.1s;
}

.card-title-custom {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.risk-gauge {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.risk-level {
  text-align: center;
  margin-bottom: 24px;

  .level-text {
    display: block;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
  }

  .level-desc {
    font-size: 13px;
    color: var(--text-muted);
  }
}

.risk-factors {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.factor-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.factor-name {
  font-size: 13px;
  color: var(--text-secondary);
  width: 70px;
  flex-shrink: 0;
}

.factor-bar-wrapper {
  flex: 1;
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: $radius-full;
  overflow: hidden;
}

.factor-bar {
  height: 100%;
  border-radius: $radius-full;
  transition: width $transition-slow;
}

.factor-value {
  font-size: 12px;
  color: var(--text-muted);
  width: 30px;
  text-align: right;
}

/* 策略区域 */
.strategy-section,
.allocation-section,
.industry-section,
.prediction-suitability {
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

.strategy-content {
  .strategy-tags {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }

  .tag-label {
    font-size: 13px;
    color: var(--text-muted);
  }

  .strategy-tag {
    cursor: default;
  }

  .benchmark-info {
    display: flex;
    gap: 12px;
    padding: 14px 18px;
    background: var(--bg-tertiary);
    border-radius: $radius-md;
    margin-bottom: 16px;

    .label {
      font-size: 13px;
      color: var(--text-muted);
    }

    .value {
      font-size: 13px;
      color: var(--text-secondary);
    }
  }

  .strategy-description {
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.8;
  }
}

/* 资产配置 */
.allocation-content {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 32px;
  align-items: center;

  @media (max-width: $breakpoint-sm) {
    grid-template-columns: 1fr;
  }
}

.allocation-legend {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.legend-name {
  font-size: 13px;
  color: var(--text-secondary);
  width: 60px;
}

.legend-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

/* 适用性 */
.suitability-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;

  @media (max-width: $breakpoint-sm) {
    grid-template-columns: 1fr;
  }
}

.suitability-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-tertiary);
  border-radius: $radius-md;
  border-left: 4px solid transparent;

  &.suitable {
    border-left-color: #22c55e;
  }

  &.not-suitable {
    border-left-color: #ef4444;
  }
}

.suitability-text {
  strong {
    display: block;
    font-size: 16px;
    color: var(--text-primary);
    margin-bottom: 4px;
  }

  p {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0;
  }
}

.metrics-mini-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: $radius-md;
}

.mini-metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mini-label {
  font-size: 13px;
  color: var(--text-muted);
}

.mini-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

/* 空状态 */
.empty-state {
  padding: 60px 20px;
  text-align: center;
}
</style>
