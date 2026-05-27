<template>
  <PageContainer narrow>
    <div class="page-header mb-16">
      <h2 class="page-title">T日盘中估算</h2>
    </div>

    <SectionCard compact class="mb-16">
      <div class="search-row">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码或名称搜索"
          clearable
          class="search-input"
          @keyup.enter="doEstimate"
          @select="handleSelect"
        />
        <el-button type="primary" :loading="loading" @click="doEstimate">实时估值</el-button>
        <el-button type="success" :disabled="!result" :loading="saving" @click="doSave">保存记录</el-button>
      </div>
    </SectionCard>

    <SectionCard compact class="mb-16" v-if="result">
      <div class="flex-between">
        <div class="flex gap-8">
          <span class="text-secondary">市场状态</span>
          <el-tag :type="marketTagType" effect="dark" size="small">
            {{ result?.market_session?.note || '--' }}
          </el-tag>
        </div>
        <div class="flex gap-8" v-if="result?.market_session?.is_trading">
          <span class="text-tertiary text-sm">自动刷新</span>
          <el-switch v-model="autoRefresh" size="small" @change="handleAutoRefresh" />
        </div>
      </div>
    </SectionCard>

    <template v-if="result && !loading">
      <el-row :gutter="16" class="mb-16">
        <el-col :xs="24" :sm="14" class="mb-8">
          <SectionCard>
            <div class="est-value-card">
              <div class="est-label">估算净值</div>
              <div class="est-number">{{ result.estimated_nav?.toFixed(4) || '--' }}</div>
              <div class="est-sub">上日净值：{{ result.prev_nav?.toFixed(4) }} ({{ result.prev_date }})</div>
            </div>
          </SectionCard>
        </el-col>
        <el-col :xs="24" :sm="10" class="mb-8">
          <SectionCard>
            <div class="est-value-card">
              <div class="est-label">估算涨跌幅</div>
              <div
                class="est-number-large"
                :style="{ color: (result.estimated_return || 0) >= 0 ? 'var(--danger)' : 'var(--success)' }"
              >
                {{ formatPercent(result.estimated_return) }}
              </div>
              <div class="est-sub">置信度：{{ (result.confidence * 100).toFixed(0) }}%</div>
              <div class="est-method">{{ result.method_display || '--' }}</div>
            </div>
          </SectionCard>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="mb-16">
        <el-col :xs="24" :sm="12" class="mb-8">
          <SectionCard title="路径A - 持仓映射">
            <div class="path-result">
              <span class="font-bold" :class="(result.path_a?.return || 0) >= 0 ? 'color-up' : 'color-down'" style="font-size:22px">
                {{ formatPercent(result.path_a?.return) }}
              </span>
              <el-tag :type="result.path_a?.available ? 'success' : 'danger'" size="small" style="margin-left:6px">
                {{ result.path_a?.available ? '可用' : '不可用' }}
              </el-tag>
            </div>
            <template v-if="result.path_a?.meta">
              <el-descriptions :column="2" size="small">
                <el-descriptions-item label="权重覆盖">{{ (result.path_a.meta.weight_coverage * 100).toFixed(1) }}%</el-descriptions-item>
                <el-descriptions-item label="股票数">{{ result.path_a.meta.stock_count || 0 }}</el-descriptions-item>
              </el-descriptions>
            </template>
          </SectionCard>
        </el-col>
        <el-col :xs="24" :sm="12" class="mb-8">
          <SectionCard title="路径B - 指数回归">
            <div class="path-result">
              <span class="font-bold" :class="(result.path_b?.return || 0) >= 0 ? 'color-up' : 'color-down'" style="font-size:22px">
                {{ formatPercent(result.path_b?.return) }}
              </span>
              <el-tag :type="result.path_b?.available ? 'success' : 'danger'" size="small" style="margin-left:6px">
                {{ result.path_b?.available ? '可用' : '不可用' }}
              </el-tag>
            </div>
            <template v-if="result.path_b?.available && result.path_b?.meta">
              <el-descriptions :column="3" size="small">
                <el-descriptions-item label="指数">{{ result.path_b.meta.regression_index }}</el-descriptions-item>
                <el-descriptions-item label="β">{{ result.path_b.meta.beta }}</el-descriptions-item>
                <el-descriptions-item label="R²">{{ result.path_b.meta.r2 }}</el-descriptions-item>
              </el-descriptions>
            </template>
          </SectionCard>
        </el-col>
      </el-row>

      <SectionCard title="融合权重" class="mb-16">
        <div class="fusion-weights">
          <div class="fusion-item">
            <div class="text-secondary text-sm mb-8">持仓(A)</div>
            <el-progress :percentage="(result.fusion_weight?.path_a * 100)" :color="'#409eff'" :stroke-width="18" :format="(p) => p + '%'" />
          </div>
          <div class="fusion-item">
            <div class="text-secondary text-sm mb-8">指数(B)</div>
            <el-progress :percentage="(result.fusion_weight?.path_b * 100)" :color="'#67c23a'" :stroke-width="18" :format="(p) => p + '%'" />
          </div>
        </div>
      </SectionCard>

      <SectionCard v-if="result.holdings_used && result.holdings_used.length" title="持仓贡献明细" class="mb-16">
        <el-table :data="result.holdings_used" size="small" stripe>
          <el-table-column prop="name" label="持仓标的" min-width="130" />
          <el-table-column prop="code" label="代码" width="85" align="center" />
          <el-table-column prop="weight" label="权重" width="75" align="center">
            <template #default="{row}">{{ (row.weight * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="95" align="center">
            <template #default="{row}">
              <span :class="row.pct_change >= 0 ? 'color-up' : 'color-down'">
                {{ row.pct_change >= 0 ? '+' : '' }}{{ row.pct_change?.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="贡献" width="105" align="center">
            <template #default="{row}">
              <span :class="row.contribution >= 0 ? 'color-up' : 'color-down'">
                {{ row.contribution >= 0 ? '+' : '' }}{{ (row.contribution * 100).toFixed(3) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </SectionCard>
    </template>
  </PageContainer>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { getIntradayEstimate, saveIntradayEstimate } from '@/api/intraday'
import { searchFunds } from '@/api/fund'
import { formatPercent } from '@/utils/format'

const fundCode = ref('')
const loading = ref(false)
const saving = ref(false)
const result = ref(null)
const autoRefresh = ref(false)

let refreshTimer = null

const marketTagType = computed(() => {
  const s = result.value?.market_session?.session
  if (s === 'morning' || s === 'afternoon') return 'success'
  if (s === 'lunch_break') return 'warning'
  return 'info'
})

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

async function doEstimate() {
  if (!fundCode.value) return
  loading.value = true
  result.value = null
  try {
    const data = await getIntradayEstimate(fundCode.value)
    result.value = data.data || data
  } catch {} finally {
    loading.value = false
  }
}

async function doSave() {
  if (!fundCode.value) return
  saving.value = true
  try {
    await saveIntradayEstimate(fundCode.value)
  } finally {
    saving.value = false
  }
}

function handleAutoRefresh(val) {
  if (val) {
    refreshTimer = setInterval(() => { if (fundCode.value) doEstimate() }, 30000)
  } else {
    if (refreshTimer) clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped lang="scss">
.page-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.search-row {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 200px;
  :deep(.el-autocomplete) { width: 100%; }
}

.est-value-card {
  text-align: center;
  padding: 12px 0;
}

.est-label {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.est-number {
  font-size: 36px;
  font-weight: 700;
  color: var(--primary);
}

.est-number-large {
  font-size: 38px;
  font-weight: 700;
  margin-top: 8px;
}

.est-sub {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-top: 4px;
}

.est-method {
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
  margin-top: 4px;
}

.path-result {
  text-align: center;
  margin-bottom: 12px;
}

.fusion-weights {
  display: flex;
  gap: 20px;
  padding: 10px 0;
  flex-wrap: wrap;
}

.fusion-item {
  flex: 1;
  min-width: 200px;
  text-align: center;
}
</style>