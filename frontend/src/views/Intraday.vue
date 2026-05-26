<template>
  <div style="max-width:800px;margin:0 auto">
    <h2>T 日盘中估算</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:center">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码"
          clearable
          style="flex:1"
          @keyup.enter="doEstimate"
          @select="handleSelect"
        />
        <el-select v-model="mode" style="width:130px">
          <el-option label="自动模式" value="auto" />
          <el-option label="持仓估算" value="holdings" />
          <el-option label="指数拟合" value="index" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="doEstimate">估算</el-button>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:14px;color:#606266">市场状态</span>
          <el-tag
            :type="marketTagType"
            effect="dark"
            size="small"
          >
            {{ appStore.marketSession.note }}
          </el-tag>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:13px;color:#909399">自动刷新</span>
          <el-switch v-model="autoRefresh" size="small" @change="handleAutoRefresh" />
        </div>
      </div>
    </el-card>

    <template v-if="result">
      <el-card shadow="never" style="text-align:center;padding:24px 0;margin-bottom:16px">
        <div style="font-size:13px;color:#909399;margin-bottom:8px">估算净值</div>
        <div style="font-size:36px;font-weight:700;color:var(--primary-color)">
          {{ result.estimated_nav?.toFixed(4) || '--' }}
        </div>
        <div
          :style="{
            fontSize:'48px',
            fontWeight:700,
            marginTop:'12px',
            color: (result.estimated_return || 0) >= 0 ? 'var(--danger-color)' : 'var(--success-color)'
          }"
        >
          {{ formatPercent(result.estimated_return) }}
        </div>
        <div style="margin-top:8px;font-size:13px;color:#909399">
          估算方法：{{ result.method_display || '--' }}
        </div>
      </el-card>

      <el-card v-if="holdings && holdings.length" shadow="never">
        <template #header><span style="font-weight:600">持仓贡献明细</span></template>
        <el-table :data="holdings" size="small" stripe>
          <el-table-column prop="name" label="持仓标的" min-width="140" />
          <el-table-column prop="weight" label="权重" width="100" align="center">
            <template #default="{row}">{{ (row.weight * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="估算涨跌" width="120" align="center">
            <template #default="{row}">
              <span :class="row.return >= 0 ? 'color-up' : 'color-down'">
                {{ formatPercent(row.return) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="贡献" width="120" align="center">
            <template #default="{row}">
              <span :class="row.contribution >= 0 ? 'color-up' : 'color-down'">
                {{ formatPercent(row.contribution) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { getIntradayEstimate } from '@/api/intraday'
import { searchFunds } from '@/api/fund'
import { formatPercent } from '@/utils/format'

const appStore = useAppStore()
const fundCode = ref('')
const mode = ref('auto')
const loading = ref(false)
const result = ref(null)
const holdings = ref([])
const autoRefresh = ref(false)

let refreshTimer = null

const marketTagType = computed(() => {
  const s = appStore.marketSession.session
  if (s === 'morning' || s === 'afternoon') return 'success'
  if (s === 'lunch') return 'warning'
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
  holdings.value = []
  try {
    const data = await getIntradayEstimate(fundCode.value, { mode: mode.value })
    result.value = data
    holdings.value = data.holdings_contribution || []
  } catch {} finally {
    loading.value = false
  }
}

function handleAutoRefresh(val) {
  if (val) {
    refreshTimer = setInterval(() => {
      if (fundCode.value) doEstimate()
    }, 60000)
  } else {
    if (refreshTimer) clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>