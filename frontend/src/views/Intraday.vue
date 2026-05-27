<template>
  <div style="max-width:900px;margin:0 auto">
    <h2>盘中实时估值</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:center">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码或名称搜索"
          clearable
          style="flex:1"
          @keyup.enter="doEstimate"
          @select="handleSelect"
        />
        <el-button type="primary" :loading="loading" @click="doEstimate">实时估值</el-button>
        <el-button type="success" :disabled="!result" :loading="saving" @click="doSave">保存记录</el-button>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:14px;color:#606266">市场状态</span>
          <el-tag :type="marketTagType" effect="dark" size="small">
            {{ result?.market_session?.note || '--' }}
          </el-tag>
        </div>
        <div style="display:flex;align-items:center;gap:8px" v-if="result?.market_session?.is_trading">
          <span style="font-size:13px;color:#909399">自动刷新</span>
          <el-switch v-model="autoRefresh" size="small" @change="handleAutoRefresh" />
        </div>
      </div>
    </el-card>

    <template v-if="result && !loading">
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="14">
          <el-card shadow="never" style="text-align:center;padding:20px 0;height:100%">
            <div style="font-size:13px;color:#909399;margin-bottom:8px">估算净值</div>
            <div style="font-size:40px;font-weight:700;color:var(--primary-color)">
              {{ result.estimated_nav?.toFixed(4) || '--' }}
            </div>
            <div style="font-size:12px;color:#909399;margin-top:4px">
              上日净值：{{ result.prev_nav?.toFixed(4) }} ({{ result.prev_date }})
            </div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card shadow="never" style="text-align:center;padding:20px 0;height:100%">
            <div style="font-size:13px;color:#909399;margin-bottom:8px">估算涨跌幅</div>
            <div
              :style="{
                fontSize:'42px',
                fontWeight:700,
                marginTop:'8px',
                color: (result.estimated_return || 0) >= 0 ? 'var(--danger-color)' : 'var(--success-color)'
              }"
            >
              {{ formatPercent(result.estimated_return) }}
            </div>
            <div style="margin-top:10px;font-size:13px;color:#909399">
              置信度：{{ (result.confidence * 100).toFixed(0) }}%
            </div>
            <div style="font-size:11px;color:#c0c4cc;margin-top:4px">
              {{ result.method_display || '--' }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span style="font-weight:600">路径A - 持仓映射</span></template>
            <div style="text-align:center;margin-bottom:12px">
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
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span style="font-weight:600">路径B - 指数回归</span></template>
            <div style="text-align:center;margin-bottom:12px">
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
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">融合权重</span></template>
        <div style="display:flex;align-items:center;gap:20px;padding:10px 0">
          <div style="flex:1;text-align:center">
            <div style="font-size:13px;color:#909399;margin-bottom:4px">持仓(A)</div>
            <el-progress :percentage="(result.fusion_weight?.path_a * 100)" :color="'#409eff'" :stroke-width="18" :format="(p) => p + '%'" />
          </div>
          <div style="flex:1;text-align:center">
            <div style="font-size:13px;color:#909399;margin-bottom:4px">指数(B)</div>
            <el-progress :percentage="(result.fusion_weight?.path_b * 100)" :color="'#67c23a'" :stroke-width="18" :format="(p) => p + '%'" />
          </div>
        </div>
      </el-card>

      <el-card v-if="result.holdings_used && result.holdings_used.length" shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">持仓贡献明细</span></template>
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
      </el-card>
    </template>
  </div>
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
