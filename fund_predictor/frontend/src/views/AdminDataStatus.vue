<template>
  <div class="admin-container">
    <div class="page-header">
      <h2>数据管理面板</h2>
      <p class="subtitle">查看系统各数据表的存储状态、行数、最新日期与缓存健康度</p>
    </div>

    <div v-loading="loading" element-loading-text="加载数据状态中...">
      <el-row :gutter="20" v-if="!loading && statusData">
        <!-- 核心统计卡片 -->
        <el-col :span="6" v-for="(card, idx) in summaryCards" :key="idx" style="margin-bottom: 20px;">
          <el-card shadow="hover" :class="['stat-card', card.type]">
            <div class="stat-icon"><el-icon :size="28"><component :is="card.icon" /></el-icon></div>
            <div class="stat-content">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </el-card>
        </el-col>

        <!-- 详细表状态 -->
        <el-col :span="24" style="margin-bottom: 20px;">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header-row">
                <span>数据库表详情</span>
                <el-button size="small" @click="refreshData" :loading="refreshing">
                  <el-icon><Refresh /></el-icon> 刷新
                </el-button>
              </div>
            </template>
            <el-table :data="tableRows" stripe style="width: 100%" :default-sort="{ prop: 'rows', order: 'descending' }">
              <el-table-column prop="table" label="表名" width="160" fixed>
                <template #default="{ row }">
                  <el-tag :type="row.tagType" size="small">{{ row.tableLabel }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="rows" label="总行数" width="120" sortable>
                <template #default="{ row }">
                  <span :class="{ 'text-muted': row.rows === 0 }">{{ formatNumber(row.rows) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="latest_date" label="最新数据日期" width="150">
                <template #default="{ row }">
                  <span v-if="row.latest_date">{{ row.latest_date }}</span>
                  <el-tag v-else type="info" size="small">无数据</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="fresh_count" label="7日内缓存命中" width="130">
                <template #default="{ row }">
                  <span v-if="row.fresh_count != null">{{ row.fresh_count }} 条</span>
                  <span v-else class="text-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="health" label="健康状态" width="140">
                <template #default="{ row }">
                  <el-tag :type="row.healthType" effect="dark" size="small">{{ row.healthText }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="error" label="备注" min-width="200">
                <template #default="{ row }">
                  <span v-if="row.error" class="text-danger">{{ row.error }}</span>
                  <span v-else class="text-muted">正常</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>

        <!-- 最近获取日志 -->
        <el-col :span="24" style="margin-bottom: 20px;">
          <el-card shadow="hover">
            <template #header>
              <span>最近数据获取日志</span>
            </template>
            <el-empty v-if="fetchLogs.length === 0" description="暂无获取日志" :image-size="60" />
            <el-timeline v-else>
              <el-timeline-item
                v-for="(log, idx) in fetchLogs"
                :key="idx"
                :timestamp="log.fetched_at"
                placement="top"
                :type="log.success ? 'success' : 'danger'"
                :hollow="!log.success"
              >
                <div class="log-item">
                  <el-tag size="small" :type="entityTypeTag(log.entity_type)">{{ log.entity_type }}</el-tag>
                  <span class="log-key">{{ log.entity_key }}</span>
                  <span class="log-source">via {{ log.source }}</span>
                  <el-tag v-if="log.success" type="success" size="small" effect="plain">{{ log.rows_affected }} 行</el-tag>
                  <span v-else class="text-error">失败: {{ log.error_message }}</span>
                </div>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-col>

        <!-- 操作区 -->
        <el-col :span="24">
          <el-card shadow="hover">
            <template #header><span>快捷操作</span></template>
            <div class="action-bar">
              <el-alert
                title="训练基金时，NAV和指数数据会自动同步到数据库。此处可手动刷新缓存或清除过期数据。"
                type="info"
                :closable="false"
                show-icon
                style="margin-bottom: 16px;"
              />
              <el-space wrap>
                <el-button type="primary" @click="refreshData" :loading="refreshing">
                  <el-icon><Refresh /></el-icon> 刷新状态
                </el-button>
              </el-space>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-else-if="!loading && !statusData" description="无法加载状态信息" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, DataAnalysis, Document, Coin, UserFilled, SetUp, Monitor } from '@element-plus/icons-vue'

const loading = ref(false)
const refreshing = ref(false)
const statusData = ref<Record<string, any> | null>(null)

interface FetchLog {
  entity_type: string
  entity_key: string
  source: string
  success: number
  rows_affected: number
  error_message: string
  duration_ms: number
  fetched_at: string
}

const fetchLogs = ref<FetchLog[]>([])

const tableLabels: Record<string, string> = {
  tasks: '训练任务',
  fund_profiles: '基金画像',
  fund_nav: '基金净值',
  index_data: '指数行情',
  holdings: '持仓快照',
  train_results: '训练结果',
  data_fetch_log: '获取日志',
}

const tableTagTypes: Record<string, string> = {
  tasks: '',
  fund_profiles: 'success',
  fund_nav: 'warning',
  index_data: '',
  holdings: 'info',
  train_results: 'success',
  data_fetch_log: 'info',
}

const tableRows = computed(() => {
  if (!statusData.value) return []
  return Object.entries(statusData.value).map(([table, info]: [string, any]) => ({
    table,
    tableLabel: tableLabels[table] || table,
    tagType: (tableTagTypes[table] as any) || 'info',
    rows: info.rows || 0,
    latest_date: info.latest_date || null,
    fresh_count: info.fresh_count ?? null,
    error: info.error || null,
    health: _assessHealth(table, info),
    healthType: _assessHealthType(table, info),
    healthText: _assessHealthText(table, info),
  }))
})

const summaryCards = computed(() => {
  const d = statusData.value
  if (!d) return []
  const totalRows = Object.values(d).reduce((sum: number, t: any) => sum + (t?.rows || 0), 0)
  const profileCount = d.fund_profiles?.rows || 0
  const navRows = d.fund_nav?.rows || 0
  const indexRows = d.index_data?.rows || 0

  return [
    { label: '总记录数', value: formatNumber(totalRows), icon: 'DataAnalysis', type: 'primary' },
    { label: '已缓存的基金', value: String(profileCount), icon: 'UserFilled', type: 'success' },
    { label: '净值数据行', value: formatNumber(navRows), icon: 'Coin', type: 'warning' },
    { label: '指数数据行', value: formatNumber(indexRows), icon: 'Monitor', type: '' },
  ]
})

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(n)
}

function entityTypeTag(type: string): string {
  const map: Record<string, string> = { profile: '', fund_nav: 'warning', index: 'success' }
  return (map[type] as any) || 'info'
}

function _assessHealth(table: string, info: any): string {
  if (info.error) return 'error'
  if (info.rows === 0) return 'empty'
  if (table === 'fund_nav') {
    if (!info.latest_date) return 'no_data'
    const daysAgo = _daysSince(info.latest_date)
    if (daysAgo > 5) return 'stale'
    return 'good'
  }
  if (table === 'fund_profiles') {
    const fresh = info.fresh_count || 0
    if (fresh > 0) return 'good'
    return 'stale'
  }
  return 'good'
}

function _assessHealthType(table: string, info: any): string {
  const h = _assessHealth(table, info)
  const map: Record<string, string> = { good: 'success', stale: 'warning', empty: 'info', no_data: 'info', error: 'danger' }
  return map[h] || 'info'
}

function _assessHealthText(table: string, info: any): string {
  const h = _assessHealth(table, info)
  const map: Record<string, string> = { good: '健康', stale: '需更新', empty: '空表', no_data: '无数据', error: '异常' }
  return map[h] || '未知'
}

function _daysSince(dateStr: string): number {
  try {
    const d = new Date(dateStr)
    return Math.floor((Date.now() - d.getTime()) / 86400000)
  } catch {
    return 999
  }
}

async function fetchDataStatus() {
  loading.value = true
  try {
    const res = await fetch('/api/v1/admin/data-status')
    const json = await res.json()
    if (json.ok) {
      statusData.value = json.data
    }
  } catch (e) {
    console.error('Failed to load data status:', e)
  } finally {
    loading.value = false
  }
}

async function refreshData() {
  refreshing.value = true
  await fetchDataStatus()
  setTimeout(() => { refreshing.value = false }, 500)
}

onMounted(() => {
  fetchDataStatus()
})
</script>

<style scoped>
.admin-container {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.subtitle {
  color: var(--text-muted);
  font-size: 14px;
}

.stat-card {
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 4px;
}

.stat-card .el-card__body {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-card.primary .stat-icon { background: rgba(64, 158, 255, 0.1); color: #409eff; }
.stat-card.success .stat-icon { background: rgba(103, 194, 58, 0.1); color: #67c23a; }
.stat-card.warning .stat-icon { background: rgba(230, 162, 60, 0.1); color: #e6a23c; }

.stat-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-muted { color: var(--text-muted); }
.text-danger { color: #f56c6c; }
.text-error { color: #f56c6c; font-size: 12px; }

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.log-key {
  font-weight: 600;
  font-family: monospace;
  font-size: 13px;
}

.log-source {
  color: var(--text-muted);
  font-size: 12px;
}

.action-bar {
  padding: 4px 0;
}
</style>
