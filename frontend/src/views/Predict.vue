<template>
  <div style="max-width:900px;margin:0 auto">
    <h2>净值估算</h2>

    <el-card shadow="never" style="margin-bottom:20px">
      <div style="display:flex;gap:12px">
        <el-autocomplete
          v-model="fundCode"
          :fetch-suggestions="handleSearch"
          placeholder="输入基金代码或名称搜索"
          clearable
          style="flex:1"
          @keyup.enter="doPredict"
          @select="handleSelect"
        />
        <el-button type="primary" :loading="loading" @click="doPredict">估算</el-button>
      </div>
    </el-card>

    <el-card v-if="loading" shadow="never">
      <el-skeleton :rows="6" animated />
    </el-card>

    <template v-if="result && !loading">
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="14">
          <el-card shadow="never" style="text-align:center;padding:20px 0;height:100%">
            <div style="font-size:13px;color:#909399;margin-bottom:8px">T 日估算净值</div>
            <div style="font-size:42px;font-weight:700;color:var(--primary-color)">
              {{ result.predicted_nav?.toFixed(4) || '--' }}
            </div>
            <div style="font-size:12px;color:#909399;margin-top:4px">
              上日净值：{{ result.prev_nav?.toFixed(4) }}
            </div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card shadow="never" style="text-align:center;padding:20px 0;height:100%">
            <div style="font-size:13px;color:#909399;margin-bottom:8px">T 日估算涨跌幅</div>
            <div
              :style="{
                fontSize:'42px',
                fontWeight:700,
                color: result.predicted_return >= 0 ? 'var(--danger-color)' : 'var(--success-color)'
              }"
            >
              {{ formatPercent(result.predicted_return) }}
            </div>
            <div style="margin-top:8px;font-size:13px;color:#909399">
              置信度：{{ (result.confidence * 100).toFixed(0) }}%
            </div>
            <el-tag
              :type="result.market_session?.is_trading ? 'success' : 'info'"
              size="small"
              effect="dark"
              style="margin-top:6px"
            >
              {{ result.market_session?.note || '--' }}
            </el-tag>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">双路径融合详情</span></template>
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="方法">{{ result.method_display }}</el-descriptions-item>
          <el-descriptions-item label="方向">
            <span :style="{ color: result.direction === 'up' ? 'var(--danger-color)' : result.direction === 'down' ? 'var(--success-color)' : '#606266', fontWeight: 600 }">
              {{ result.direction === 'up' ? '看涨 ↑' : result.direction === 'down' ? '看跌 ↓' : '中性 →' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="持仓路径(A)收益">
            <span :class="result.path_a?.return >= 0 ? 'color-up' : 'color-down'" class="font-bold">
              {{ formatPercent(result.path_a?.return) }}
            </span>
            <el-tag v-if="result.path_a?.available" type="success" size="small" style="margin-left:4px">可用</el-tag>
            <el-tag v-else type="danger" size="small" style="margin-left:4px">不可用</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="指数路径(B)收益">
            <span :class="result.path_b?.return >= 0 ? 'color-up' : 'color-down'" class="font-bold">
              {{ formatPercent(result.path_b?.return) }}
            </span>
            <el-tag v-if="result.path_b?.available" type="success" size="small" style="margin-left:4px">可用</el-tag>
            <el-tag v-else type="danger" size="small" style="margin-left:4px">不可用</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="融合权重 A">
            <el-progress :percentage="(result.fusion_weight?.path_a * 100)" :stroke-width="12" :format="(p) => p + '%'" />
          </el-descriptions-item>
          <el-descriptions-item label="融合权重 B">
            <el-progress :percentage="(result.fusion_weight?.path_b * 100)" :stroke-width="12" :format="(p) => p + '%'" />
          </el-descriptions-item>
          <el-descriptions-item label="置信区间" :span="2">
            <span class="font-bold">{{ formatPercent(result.confidence_interval_lower) }}</span>
            ~
            <span class="font-bold">{{ formatPercent(result.confidence_interval_upper) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="校准样本数" :span="2">
            <span :class="{ 'text-warning': (result.model_info?.calibration_size || 0) < 30 }">
              {{ result.model_info?.calibration_size || '--' }}
            </span>
            <el-tag v-if="(result.model_info?.calibration_size || 0) < 30" type="warning" size="small" style="margin-left:8px">
              样本不足，置信区间可能不稳定
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="result.holdings_used && result.holdings_used.length" shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">持仓贡献明细（路径A）</span></template>
        <el-table :data="result.holdings_used" size="small" stripe>
          <el-table-column prop="name" label="持仓标的" min-width="140" />
          <el-table-column prop="code" label="代码" width="90" align="center" />
          <el-table-column prop="weight" label="权重" width="80" align="center">
            <template #default="{row}">{{ (row.weight * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100" align="center">
            <template #default="{row}">
              <span :class="row.pct_change >= 0 ? 'color-up' : 'color-down'">
                {{ row.pct_change >= 0 ? '+' : '' }}{{ row.pct_change?.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="贡献" width="110" align="center">
            <template #default="{row}">
              <span :class="row.contribution >= 0 ? 'color-up' : 'color-down'">
                {{ row.contribution >= 0 ? '+' : '' }}{{ (row.contribution * 100).toFixed(3) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="result.path_b?.meta?.regression_index" shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">指数回归信息（路径B）</span></template>
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="最优指数">{{ result.path_b.meta.regression_index }}</el-descriptions-item>
          <el-descriptions-item label="β系数">{{ result.path_b.meta.beta }}</el-descriptions-item>
          <el-descriptions-item label="R²">{{ result.path_b.meta.r2 }}</el-descriptions-item>
          <el-descriptions-item label="回归窗口">{{ result.path_b.meta.window }}天</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { predictFund } from '@/api/predict'
import { searchFunds } from '@/api/fund'
import { formatPercent } from '@/utils/format'

const fundCode = ref('')
const loading = ref(false)
const result = ref(null)

async function handleSearch(query, cb) {
  if (!query || query.length < 1) return cb([])
  try {
    const data = await searchFunds(query)
    const list = (data || []).map(f => ({ value: f.fund_code + ' - ' + f.fund_name, ...f }))
    cb(list)
  } catch {
    cb([])
  }
}

function handleSelect(item) {
  fundCode.value = item.fund_code || item.value.split(' - ')[0]
}

async function doPredict() {
  if (!fundCode.value) return
  loading.value = true
  result.value = null
  try {
    const res = await predictFund({ fund_code: fundCode.value })
    result.value = res.data || res
  } catch {} finally {
    loading.value = false
  }
}
</script>
