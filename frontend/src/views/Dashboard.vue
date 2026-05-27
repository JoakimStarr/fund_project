<template>
  <PageContainer>
    <div class="dashboard-header flex-between mb-16">
      <h2 class="dashboard-title">决策中心</h2>
      <el-tag type="info" effect="plain" class="animate-fade-in">{{ today }}</el-tag>
    </div>

    <el-row :gutter="16" class="mb-16">
      <el-col :xs="12" :sm="12" :md="6" v-for="(s, i) in statCards" :key="s.label" class="mb-8">
        <StatCard
          :icon="s.icon"
          :value="s.value"
          :label="s.label"
          :accent="s.color"
          :style="{ animationDelay: `${i * 0.1}s` }"
          class="animate-fade-in-up"
        />
      </el-col>
    </el-row>

    <SectionCard title="快捷操作" class="mb-16">
      <el-row :gutter="12">
        <el-col :xs="12" :sm="8" :md="4" v-for="a in quickActions" :key="a.path" class="mb-8">
          <div class="quick-action-card" @click="$router.push(a.path)">
            <el-icon :size="28" :color="a.color"><component :is="a.icon" /></el-icon>
            <span class="quick-action-label">{{ a.label }}</span>
          </div>
        </el-col>
      </el-row>
    </SectionCard>

    <el-row :gutter="16" class="mb-16">
      <el-col :xs="24" :md="14" class="mb-8">
        <SectionCard title="准确率趋势">
          <div ref="chartRef" style="height:280px" />
        </SectionCard>
      </el-col>
      <el-col :xs="24" :md="10" class="mb-8">
        <SectionCard title="系统状态">
          <template #extra>
            <el-tag size="small" :type="aiStatusTagType">{{ aiStatusText }}</el-tag>
          </template>
          <div v-if="!systemStatus.length" class="empty-text">暂无系统状态信息</div>
          <div v-for="s in systemStatus" :key="s.label" class="status-item">
            <span class="text-secondary">{{ s.label }}</span>
            <el-tag size="small" :type="s.status === 'ok' ? 'success' : 'danger'">{{ s.text }}</el-tag>
          </div>
        </SectionCard>
      </el-col>
    </el-row>

    <SectionCard title="近期预测记录">
      <el-table :data="recentPredictions" size="small" empty-text="暂无预测记录" stripe>
        <el-table-column prop="fund_code" label="基金代码" width="100" />
        <el-table-column prop="fund_name" label="基金名称" min-width="160" />
        <el-table-column label="预测涨跌" width="120" align="center">
          <template #default="{row}">
            <span :class="row.predicted_return >= 0 ? 'color-up' : 'color-down'" class="font-bold">
              {{ formatPercent(row.predicted_return) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="方向概率" width="120" align="center">
          <template #default="{row}">
            <span>{{ (row.direction_probability * 100).toFixed(1) }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="预测时间" width="170" align="center">
          <template #default="{row}">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </SectionCard>
  </PageContainer>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '@/stores/app'
import { getStats, getRecentPredictions } from '@/api/dashboard'
import { formatPercent, formatDateTime } from '@/utils/format'

const appStore = useAppStore()
const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
const statCards = ref([
  { label: '已训练模型', value: '--', icon: 'Coin', color: '#409EFF' },
  { label: '平均准确率', value: '--', icon: 'TrendCharts', color: '#67C23A' },
  { label: '今日预测', value: '--', icon: 'DataBoard', color: '#E6A23C' },
  { label: '数据新鲜度', value: '--', icon: 'Clock', color: '#909399' },
])
const recentPredictions = ref([])
const systemStatus = ref([])
const chartRef = ref(null)

let chartInstance = null

const aiStatusTagType = computed(() => {
  return appStore.aiProviderStatus?.available ? 'success' : 'danger'
})

const aiStatusText = computed(() => {
  return appStore.aiProviderStatus?.available ? 'AI 服务可用' : 'AI 服务不可用'
})

const quickActions = [
  { path: '/predict', label: '智能预测', icon: 'TrendCharts', color: '#409EFF' },
  { path: '/intraday', label: '盘中估算', icon: 'Timer', color: '#67C23A' },
  { path: '/train', label: '模型训练', icon: 'Setting', color: '#E6A23C' },
  { path: '/compare', label: '多基金对比', icon: 'Grid', color: '#F56C6C' },
  { path: '/profile', label: '基金画像', icon: 'UserFilled', color: '#909399' },
  { path: '/backtest', label: '回测诊断', icon: 'DataLine', color: '#409EFF' },
]

async function loadStats() {
  try {
    const data = await getStats()
    if (data) {
      statCards.value = [
        { label: '已训练模型', value: data.trained_models ?? '--', icon: 'Coin', color: '#409EFF' },
        { label: '平均准确率', value: data.avg_accuracy != null ? (data.avg_accuracy * 100).toFixed(1) + '%' : '--', icon: 'TrendCharts', color: '#67C23A' },
        { label: '今日预测', value: data.today_predictions ?? '--', icon: 'DataBoard', color: '#E6A23C' },
        { label: '数据新鲜度', value: data.data_freshness || '--', icon: 'Clock', color: '#909399' },
      ]
    }
  } catch {}
}

async function loadRecentPredictions() {
  try {
    const data = await getRecentPredictions()
    if (data) {
      recentPredictions.value = data.results || data || []
    }
  } catch {}
}

function initChart() {
  nextTick(() => {
    if (!chartRef.value) return
    import('echarts').then(echarts => {
      chartInstance = echarts.init(chartRef.value)
      chartInstance.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'], axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 11 } },
        series: [{
          data: [82, 78, 85, 80, 88, 84],
          type: 'line',
          smooth: true,
          lineStyle: { color: '#409EFF', width: 2 },
          areaStyle: { color: 'rgba(64,158,255,0.1)' },
          itemStyle: { color: '#409EFF' }
        }]
      })
    })
  })
}

function handleResize() {
  if (chartInstance) chartInstance.resize()
}

onMounted(() => {
  loadStats()
  loadRecentPredictions()
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) chartInstance.dispose()
})
</script>

<style scoped lang="scss">
.dashboard-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.dashboard-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--text-primary);
}

.quick-action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-card);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out-expo);
  @media (hover: hover) {
    &:hover {
      transform: translateY(-4px);
      box-shadow: var(--shadow-md);
      border-color: var(--primary-light);
    }
  }
}

.quick-action-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  text-align: center;
}

.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-base);
  &:last-child { border-bottom: none; }
}

.empty-text {
  text-align: center;
  padding: 30px 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-base);
}
</style>