<template>
  <div class="monitor-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">模型监控</h1>
        <p class="page-subtitle">实时监控系统健康状态与模型性能指标</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 系统健康总览 -->
    <div class="health-overview glass-card">
      <div class="overview-header">
        <h3 class="section-title">系统健康度</h3>
        <el-tag :type="systemHealth.type" effect="dark" size="large">
          {{ systemHealth.score }}分 - {{ systemHealth.status }}
        </el-tag>
      </div>

      <div class="health-metrics">
        <div
          v-for="(service, key) in services"
          :key="key"
          class="service-card"
          :class="{ 'is-warning': service.health < 80, 'is-error': service.health < 60 }"
        >
          <div class="service-icon" :style="{ background: service.iconBg }">
            <el-icon :size="24" :color="service.iconColor">
              <component :is="service.icon" />
            </el-icon>
          </div>

          <div class="service-info">
            <div class="service-name">{{ service.name }}</div>
            <div class="service-status" :class="service.status">
              {{ service.statusText }}
            </div>
          </div>

          <div class="service-health">
            <el-progress
              type="circle"
              :percentage="service.health"
              :width="50"
              :stroke-width="6"
              :color="getProgressColor(service.health)"
            />
          </div>

          <div class="service-details">
            <div class="detail-item">
              <span>响应时间</span>
              <strong>{{ service.responseTime }}</strong>
            </div>
            <div class="detail-item">
              <span>成功率</span>
              <strong>{{ service.successRate }}</strong>
            </div>
            <div class="detail-item">
              <span>最后更新</span>
              <strong>{{ service.lastUpdate }}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型性能指标 -->
    <div class="performance-grid">
      <div class="performance-card glass-card">
        <h3 class="section-title">预测延迟分布</h3>
        <BaseChart :option="latencyChartOption" height="280px" />
      </div>

      <div class="performance-card glass-card">
        <h3 class="section-title">请求量趋势</h3>
        <BaseChart :option="requestChartOption" height="280px" />
      </div>
    </div>

    <!-- 模型列表 -->
    <div class="models-section glass-card">
      <div class="section-header">
        <h3 class="section-title">已训练模型</h3>
        <el-input
          v-model="searchQuery"
          placeholder="搜索基金代码..."
          prefix-icon="Search"
          clearable
          style="width: 240px;"
        />
      </div>

      <el-table
        :data="filteredModels"
        stripe
        style="width: 100%"
        empty-text="暂无已训练的模型"
      >
        <el-table-column prop="fundCode" label="基金代码" width="120">
          <template #default="{ row }">
            <router-link :to="{ path: '/predict', query: { code: row.fundCode } }" class="fund-link">
              {{ row.fundCode }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="fundName" label="基金名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="modelVersion" label="版本" width="100" />
        <el-table-column prop="accuracy" label="准确率" width="100">
          <template #default="{ row }">
            <span :class="row.accuracy >= 80 ? 'text-positive' : row.accuracy >= 60 ? '' : 'text-negative'">
              {{ row.accuracy }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="lastTrained" label="最后训练时间" width="170" />
        <el-table-column prop="predictions" label="预测次数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '待更新' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewModelDetail(row)">
              详情
            </el-button>
            <el-button text type="warning" size="small" @click="retrainModel(row)">
              重训
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 资源使用情况 -->
    <div class="resources-grid">
      <div class="resource-card glass-card">
        <h3 class="section-title">CPU 使用率</h3>
        <BaseChart :option="cpuChartOption" height="200px" />
      </div>
      <div class="resource-card glass-card">
        <h3 class="section-title">内存使用</h3>
        <BaseChart :option="memoryChartOption" height="200px" />
      </div>
      <div class="resource-card glass-card">
        <h3 class="section-title">磁盘空间</h3>
        <div class="disk-info">
          <div class="disk-usage">
            <el-progress
              type="dashboard"
              :percentage="diskUsage"
              :width="120"
              :color="diskUsage > 90 ? '#ef4444' : diskUsage > 70 ? '#f59e0b' : '#22c55e'"
            />
          </div>
          <div class="disk-details">
            <div class="detail-row">
              <span>已用</span>
              <strong>{{ diskUsed }} GB</strong>
            </div>
            <div class="detail-row">
              <span>总计</span>
              <strong>{{ diskTotal }} GB</strong>
            </div>
            <div class="detail-row">
              <span>可用</span>
              <strong>{{ diskAvailable }} GB</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { getModelList, getDashboardStats } from '@/api/dashboard'

// 状态
const refreshing = ref(false)
const searchQuery = ref('')
const diskUsage = ref(65)
const diskUsed = ref(128)
const diskTotal = ref(500)
const diskAvailable = ref(372)

// 系统健康
const systemHealth = ref({
  score: 92,
  status: '优秀',
  type: 'success'
})

// 服务状态（从API加载）
const services = ref({
  modelService: {
    name: '模型服务',
    icon: 'Cpu',
    iconBg: 'rgba(59, 130, 246, 0.15)',
    iconColor: '#3b82f6',
    health: 0,
    status: 'unknown',
    statusText: '加载中...',
    responseTime: '-',
    successRate: '-',
    lastUpdate: '-'
  },
  apiService: {
    name: 'API 网关',
    icon: 'Connection',
    iconBg: 'rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    health: 0,
    status: 'unknown',
    statusText: '加载中...',
    responseTime: '-',
    successRate: '-',
    lastUpdate: '-'
  },
  database: {
    name: '数据库',
    icon: 'Coin',
    iconBg: 'rgba(168, 85, 247, 0.15)',
    iconColor: '#a855f7',
    health: 0,
    status: 'unknown',
    statusText: '加载中...',
    responseTime: '-',
    successRate: '-',
    lastUpdate: '-'
  },
  cache: {
    name: '缓存服务',
    icon: 'Monitor',
    iconBg: 'rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    health: 0,
    status: 'unknown',
    statusText: '加载中...',
    responseTime: '-',
    successRate: '-',
    lastUpdate: '-'
  }
})

// 模型列表（从API加载）
const models = ref([])

// 过滤后的模型
const filteredModels = computed(() => {
  if (!searchQuery.value) return models.value
  const query = searchQuery.value.toLowerCase()
  return models.value.filter(m =>
    m.fundCode.includes(query) ||
    m.fundName.toLowerCase().includes(query)
  )
})

// 图表配置
const latencyChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
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
    type: 'category',
    data: ['<100ms', '100-200ms', '200-500ms', '500ms-1s', '>1s'],
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b' }
  },
  yAxis: {
    type: 'value',
    name: '请求占比(%)',
    axisLabel: { color: '#64748b', formatter: '{value}%' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [{
    type: 'bar',
    data: [78, 15, 5, 1.5, 0.5],
    barWidth: '50%',
    itemStyle: {
      borderRadius: [4, 4, 0, 0],
      color: (params) => {
        const colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444']
        return colors[params.dataIndex]
      }
    }
  }]
}))

const requestChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
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
    type: 'category',
    boundaryGap: false,
    data: generateHours(24),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { color: '#64748b', fontSize: 11 }
  },
  yAxis: {
    type: 'value',
    name: '请求/分钟',
    axisLabel: { color: '#64748b' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [{
    type: 'line',
    smooth: true,
    data: Array.from({ length: 24 }, () => Math.floor(Math.random() * 150 + 50)),
    lineStyle: { width: 3, color: '#3b82f6' },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
          { offset: 1, color: 'rgba(59, 130, 246, 0)' }
        ]
      }
    },
    itemStyle: { color: '#3b82f6' }
  }]
}))

const cpuChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: generateMinutes(30),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { show: false }
  },
  yAxis: {
    type: 'value',
    max: 100,
    axisLabel: { formatter: '{value}%', color: '#64748b' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [{
    type: 'line',
    smooth: true,
    data: Array.from({ length: 30 }, () => Math.floor(Math.random() * 40 + 25)),
    lineStyle: { width: 2, color: '#a855f7' },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(168, 85, 247, 0.3)' },
          { offset: 1, color: 'rgba(168, 85, 247, 0)' }
        ]
      }
    }
  }]
}))

const memoryChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: generateMinutes(30),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    axisLabel: { show: false }
  },
  yAxis: {
    type: 'value',
    max: 100,
    axisLabel: { formatter: '{value}%', color: '#64748b' },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [{
    type: 'line',
    smooth: true,
    data: Array.from({ length: 30 }, () => Math.floor(Math.random() * 20 + 60)),
    lineStyle: { width: 2, color: '#06b6d4' },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(6, 182, 212, 0.3)' },
          { offset: 1, color: 'rgba(6, 182, 212, 0)' }
        ]
      }
    }
  }]
}))

// 方法
const refreshData = async () => {
  refreshing.value = true

  try {
    const [statsRes, modelsRes] = await Promise.all([
      getDashboardStats(),
      getModelList()
    ])
    
    // 更新服务状态
    if (statsRes.data?.system_status) {
      const sysStatus = statsRes.data.system_status
      if (sysStatus.model) {
        services.value.modelService.health = sysStatus.model.value || 0
        services.value.modelService.status = sysStatus.model.status || 'unknown'
        services.value.modelService.statusText = sysStatus.model.status === 'healthy' ? '运行正常' : 
          sysStatus.model.status === 'warning' ? '轻微异常' : '离线'
        services.value.modelService.lastUpdate = '刚刚'
      }
      if (sysStatus.api) {
        services.value.apiService.health = sysStatus.api.value || 0
        services.value.apiService.status = sysStatus.api.status || 'unknown'
        services.value.apiService.statusText = sysStatus.api.status === 'healthy' ? '运行正常' : '轻微异常'
        services.value.apiService.lastUpdate = '刚刚'
      }
      if (sysStatus.database) {
        services.value.database.health = sysStatus.database.value || 0
        services.value.database.status = sysStatus.database.status || 'unknown'
        services.value.database.statusText = sysStatus.database.status === 'healthy' ? '运行正常' : '轻微延迟'
        services.value.database.lastUpdate = '刚刚'
      }
      if (sysStatus.cache) {
        services.value.cache.health = sysStatus.cache.value || 0
        services.value.cache.status = sysStatus.cache.status || 'unknown'
        services.value.cache.statusText = sysStatus.cache.status === 'healthy' ? '运行正常' : '内存偏高'
        services.value.cache.lastUpdate = '刚刚'
      }
    }
    
    // 更新模型列表
    if (modelsRes.data && Array.isArray(modelsRes.data)) {
      models.value = modelsRes.data.map(m => ({
        fundCode: m.fundCode,
        fundName: `基金 ${m.fundCode}`,
        modelVersion: '-',
        accuracy: parseFloat(m.accuracy) || 0,
        lastTrained: m.trainedAt || '-',
        predictions: 0,
        status: m.status === 'active' ? 'active' : 'stale'
      }))
    }
    
  } catch (error) {
    console.error('刷新数据失败:', error)
  } finally {
    refreshing.value = false
  }
}

const viewModelDetail = (model) => {
  console.log('查看模型详情:', model)
}

const retrainModel = (model) => {
  console.log('重新训练模型:', model)
}

// 辅助函数
const getProgressColor = (value) => {
  if (value >= 90) return '#22c55e'
  if (value >= 70) return '#f59e0b'
  return '#ef4444'
}

function generateHours(count) {
  const hours = []
  for (let i = count; i >= 0; i--) {
    hours.push(`${String(i).padStart(2, '0')}:00`)
  }
  return hours
}

function generateMinutes(count) {
  const now = new Date()
  const minutes = []
  for (let i = count; i >= 0; i--) {
    const time = new Date(now - i * 60000)
    minutes.push(`${time.getMinutes()}`)
  }
  return minutes
}

// 自动刷新定时器
let autoRefreshTimer = null

onMounted(() => {
  // 初始加载数据
  refreshData()
  // 每30秒自动刷新一次
  autoRefreshTimer = setInterval(refreshData, 30000)
})

onUnmounted(() => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }
})
</script>

<style lang="scss" scoped>
.monitor-page {
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.header-actions {
  display: flex;
  gap: 12px;
}

/* 健康概览 */
.health-overview {
  margin-bottom: 24px;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .section-title {
    margin-bottom: 0;
  }
}

.health-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.service-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-tertiary);
  border-radius: $radius-md;
  border: 1px solid transparent;
  transition: all $transition-normal;

  &.is-warning {
    border-color: rgba($warning, 0.3);
  }

  &.is-error {
    border-color: rgba($danger, 0.3);
  }

  &:hover {
    transform: translateY(-2px);
  }
}

.service-icon {
  width: 48px;
  height: 48px;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.service-info {
  .service-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
  }

  .service-status {
    font-size: 12px;

    &.healthy {
      color: $success;
    }

    &.warning {
      color: $warning;
    }

    &.error {
      color: $danger;
    }
  }
}

.service-health {
  flex-shrink: 0;
}

.service-details {
  display: flex;
  gap: 16px;
  margin-left: auto;

  .detail-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;

    span {
      font-size: 11px;
      color: var(--text-muted);
    }

    strong {
      font-size: 13px;
      color: var(--text-secondary);
      font-variant-numeric: tabular-nums;
    }
  }
}

/* 性能图表 */
.performance-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.performance-card {
  animation: fadeIn 0.5s ease;
}

/* 模型列表 */
.models-section {
  margin-bottom: 24px;
}

.fund-link {
  color: var(--primary);
  font-weight: 600;
  font-family: 'SF Mono', monospace;

  &:hover {
    text-decoration: underline;
  }
}

/* 资源使用 */
.resources-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;

  @media (max-width: $breakpoint-lg) {
    grid-template-columns: 1fr;
  }
}

.resource-card {
  animation: fadeIn 0.5s ease;
}

.disk-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  padding: 20px 0;
}

.disk-details {
  .detail-row {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    padding: 8px 0;
    font-size: 13px;

    span {
      color: var(--text-muted);
    }

    strong {
      color: var(--text-primary);
      font-variant-numeric: tabular-nums;
    }
  }
}
</style>
