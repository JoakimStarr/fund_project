<template>
  <PageContainer narrow>
    <div class="page-header mb-16">
      <h2 class="page-title">基金画像</h2>
    </div>

    <SectionCard compact class="mb-16">
      <el-autocomplete
        v-model="fundCode"
        :fetch-suggestions="handleSearch"
        placeholder="输入基金代码或名称搜索"
        clearable
        class="profile-search"
        @keyup.enter="loadProfile"
        @select="handleSelect"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-autocomplete>
    </SectionCard>

    <template v-if="profile">
      <SectionCard class="mb-16">
        <template #header>
          <div class="profile-header">
            <div class="flex gap-8">
              <h3 class="profile-name">{{ profile.fund_name || '--' }}</h3>
              <el-tag type="primary" size="small" effect="dark">{{ profile.fund_type || '--' }}</el-tag>
              <el-tag v-if="profile.rating" size="small">{{ profile.rating }}</el-tag>
            </div>
          </div>
        </template>
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="基金代码">{{ profile.fund_code }}</el-descriptions-item>
          <el-descriptions-item label="基金全称">{{ profile.full_name || '--' }}</el-descriptions-item>
          <el-descriptions-item label="风格描述">{{ profile.type_desc || profile.fund_type_raw || '--' }}</el-descriptions-item>
          <el-descriptions-item label="成立日期">{{ profile.established || '--' }}</el-descriptions-item>
          <el-descriptions-item label="基金规模">{{ profile.size_text || '--' }}</el-descriptions-item>
          <el-descriptions-item label="基金经理">{{ profile.manager || '--' }}</el-descriptions-item>
          <el-descriptions-item label="基金公司">{{ profile.company || '--' }}</el-descriptions-item>
          <el-descriptions-item label="托管银行">{{ profile.custodian_bank || '--' }}</el-descriptions-item>
          <el-descriptions-item label="最新净值">{{ profile.latest_nav?.toFixed(4) || '--' }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <template v-if="profile.risk_level != null">
              <el-rate v-model.number="riskLevelVal" disabled show-score score-template="{value}级" />
            </template>
            <span v-else>--</span>
          </el-descriptions-item>
          <el-descriptions-item label="投资风格">{{ profile.style_tips || '--' }}</el-descriptions-item>
          <el-descriptions-item label="评级">{{ profile.rating || '--' }}</el-descriptions-item>
        </el-descriptions>
      </SectionCard>

      <el-row :gutter="12" class="mb-16">
        <el-col :xs="12" :sm="8" :md="6" v-for="m in metricCards" :key="m.label" class="mb-8">
          <StatCard icon="TrendCharts" :value="m.value" :label="m.label" :accent="m.color" />
        </el-col>
      </el-row>

      <el-row :gutter="16" class="mb-16">
        <el-col :xs="24" :md="14" class="mb-8">
          <SectionCard title="资产配置与持仓明细" subtitle="股票/债券/现金合并展示">
            <el-table :data="allAssets" size="small" stripe empty-text="暂无资产配置数据" max-height="380">
              <el-table-column prop="name" label="标的名称" min-width="130" />
              <el-table-column prop="code" label="代码" width="85" align="center" />
              <el-table-column label="权重" width="90" align="center">
                <template #default="{row}">{{ (row.weight * 100).toFixed(2) }}%</template>
              </el-table-column>
              <el-table-column prop="type_label" label="类型" width="80" align="center">
                <template #default="{row}">
                  <el-tag :type="row.type_tag" size="small">{{ row.type_label }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="assetSummary" class="asset-summary">
              <span>股票合计: <b>{{ (assetSummary.stock * 100).toFixed(1) }}%</b></span>
              <span>债券合计: <b>{{ (assetSummary.bond * 100).toFixed(1) }}%</b></span>
              <span>现金合计: <b>{{ (assetSummary.cash * 100).toFixed(1) }}%</b></span>
            </div>
          </SectionCard>
        </el-col>
        <el-col :xs="24" :md="10" class="mb-8">
          <SectionCard title="资产分布">
            <div ref="pieChartRef" style="height:320px" />
          </SectionCard>
        </el-col>
      </el-row>

      <SectionCard v-if="hasPredictionCapability" title="预测能力评估" class="mb-16">
        <el-descriptions :column="4" size="small" border>
          <el-descriptions-item label="方向准确率">
            {{ predictionCapability.direction_accuracy != null ? (predictionCapability.direction_accuracy * 100).toFixed(1) + '%' : '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="MAE">{{ predictionCapability.mae?.toFixed(4) || '--' }}</el-descriptions-item>
          <el-descriptions-item label="模型版本">{{ predictionCapability.model_version || '--' }}</el-descriptions-item>
          <el-descriptions-item label="训练天数">{{ predictionCapability.train_rows || '--' }}</el-descriptions-item>
        </el-descriptions>
      </SectionCard>

      <SectionCard v-if="profile.invest_strategy" title="投资策略">
        <div class="strategy-content">{{ profile.invest_strategy }}</div>
      </SectionCard>
    </template>
  </PageContainer>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useFundStore } from '@/stores/fund'
import { Search } from '@element-plus/icons-vue'

const route = useRoute()
const fundStore = useFundStore()
const fundCode = ref('')
const profile = ref(null)
const pieChartRef = ref(null)
let pieChartInstance = null

const riskLevelVal = computed(() => profile.value?.risk_level || 0)

const predictionCapability = computed(() => profile.value?.prediction_capability || {})

const metricCards = computed(() => {
  const p = profile.value
  if (!p) return []
  const cards = []
  if (p.nav_grtd != null) cards.push({ label: '日涨跌', value: formatPct(p.nav_grtd), color: p.nav_grtd >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (p.nav_grl1m != null) cards.push({ label: '近1月', value: formatPct(p.nav_grl1m), color: (p.nav_grl1m || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (p.nav_grl3m != null) cards.push({ label: '近3月', value: formatPct(p.nav_grl3m), color: (p.nav_grl3m || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (p.nav_grl6m != null) cards.push({ label: '近6月', value: formatPct(p.nav_grl6m), color: (p.nav_grl6m || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (!cards.some(c => c.label === '今年') && p.nav_grlty != null) cards.push({ label: '今年', value: formatPct(p.nav_grlty), color: (p.nav_grlty || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (!cards.some(c => c.label === '1年') && p.nav_grl1y != null) cards.push({ label: '1年', value: formatPct(p.nav_grl1y), color: (p.nav_grl1y || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (!cards.some(c => c.label === '3年') && p.nav_grl3y != null) cards.push({ label: '3年', value: formatPct(p.nav_grl3y), color: (p.nav_grl3y || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (!cards.some(c => c.label === '5年') && p.nav_grl5y != null) cards.push({ label: '5年', value: formatPct(p.nav_grl5y), color: (p.nav_grl5y || 0) >= 0 ? 'var(--danger)' : 'var(--success)' })
  if (cards.length < 4 && p.latest_nav) cards.push({ label: '最新净值', value: p.latest_nav.toFixed(4), color: 'var(--primary)' })
  if (cards.length < 4) cards.push({ label: '数据天数', value: (p.data_days || 0) + '天', color: '#909399' })
  return cards.slice(0, 6)
})

const allAssets = computed(() => {
  const aa = profile.value?.asset_allocation
  if (!aa) return []
  const result = []
  for (const s of (aa.stocks || [])) {
    result.push({ ...s, type_label: '股票', type_tag: '' })
  }
  for (const b of (aa.bonds || [])) {
    result.push({ ...b, type_label: '债券', type_tag: 'warning' })
  }
  for (const c of (aa.cash || [])) {
    result.push({ ...c, type_label: '现金', type_tag: 'info' })
  }
  for (const o of (aa.other || [])) {
    result.push({ ...o, type_label: '其他', type_tag: 'info' })
  }
  return result.sort((a, b) => b.weight - a.weight)
})

const assetSummary = computed(() => {
  const aa = profile.value?.asset_allocation
  if (!aa) return null
  return {
    stock: aa.stock_total_weight || 0,
    bond: aa.bond_total_weight || 0,
    cash: aa.cash_total_weight || 0,
  }
})

const hasPredictionCapability = computed(() => {
  const pc = profile.value?.prediction_capability
  return pc && pc.direction_accuracy != null
})

function formatPct(val) {
  if (val == null) return '--'
  const num = parseFloat(val)
  if (isNaN(num)) return val
  return (num >= 0 ? '+' : '') + num.toFixed(2) + '%'
}

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
    if (data?.asset_allocation) {
      initPieChart(data.asset_allocation)
    }
  } catch {}
}

function initPieChart(aa) {
  nextTick(() => {
    if (!pieChartRef.value) return
    import('echarts').then(echarts => {
      if (pieChartInstance) pieChartInstance.dispose()
      pieChartInstance = echarts.init(pieChartRef.value)
      const stockW = (aa.stock_total_weight || 0) * 100
      const bondW = (aa.bond_total_weight || 0) * 100
      const cashW = (aa.cash_total_weight || 0) * 100
      const otherW = Math.max(0, 100 - stockW - bondW - cashW)
      const pieData = [
        { name: `股票 ${stockW.toFixed(1)}%`, value: stockW, itemStyle: { color: '#409eff' } },
        { name: `债券 ${bondW.toFixed(1)}%`, value: bondW, itemStyle: { color: '#67c23a' } },
        { name: `现金 ${cashW.toFixed(1)}%`, value: cashW, itemStyle: { color: '#e6a23c' } },
      ]
      if (otherW > 0.5) pieData.push({ name: `其他 ${otherW.toFixed(1)}%`, value: otherW, itemStyle: { color: '#909399' } })
      pieChartInstance.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
        legend: { bottom: 0 },
        series: [{
          type: 'pie',
          radius: ['35%', '62%'],
          center: ['50%', '45%'],
          data: pieData,
          label: { formatter: '{b}\n{d}%', fontSize: 11 },
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.3)' } }
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

<style scoped lang="scss">
.page-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.profile-search {
  width: 100%;
  :deep(.el-autocomplete) { width: 100%; }
}

.profile-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.profile-name {
  font-size: var(--font-size-xl);
  font-weight: 600;
  margin: 0;
}

.asset-summary {
  margin-top: 12px;
  display: flex;
  gap: 20px;
  font-size: var(--font-size-base);
  flex-wrap: wrap;
}

.strategy-content {
  white-space: pre-wrap;
  font-size: var(--font-size-base);
  line-height: 1.8;
  color: var(--text-secondary);
}
</style>