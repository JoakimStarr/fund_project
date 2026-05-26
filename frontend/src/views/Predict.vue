<template>
  <div style="max-width:800px;margin:0 auto">
    <h2>智能预测</h2>

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
        <el-button type="primary" :loading="predictStore.loading" @click="doPredict">预测</el-button>
      </div>
    </el-card>

    <el-card v-if="predictStore.loading" shadow="never">
      <el-skeleton :rows="5" animated />
    </el-card>

    <el-alert
      v-if="needTrain"
      :title="'该基金暂无训练好的模型'"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom:16px"
    >
      <template #default>
        <el-button size="small" type="primary" @click="goTrain">前往训练</el-button>
      </template>
    </el-alert>

    <template v-if="predictStore.predictionResult">
      <el-card shadow="never" style="margin-bottom:16px;text-align:center;padding:20px 0">
        <div style="font-size:13px;color:#909399;margin-bottom:8px">T+1 预测涨跌幅</div>
        <div
          :style="{
            fontSize:'52px',
            fontWeight:700,
            color: resultReturn >= 0 ? 'var(--danger-color)' : 'var(--success-color)'
          }"
        >
          {{ formatPercent(resultReturn) }}
        </div>
        <div style="margin-top:12px;font-size:13px;color:#909399">
          置信区间：
          <span class="font-bold">{{ formatPercent(ciLower) }}</span>
          ~
          <span class="font-bold">{{ formatPercent(ciUpper) }}</span>
        </div>
        <div style="margin-top:16px;max-width:300px;margin-left:auto;margin-right:auto">
          <div style="display:flex;justify-content:space-between;font-size:12px;color:#909399;margin-bottom:4px">
            <span>下跌概率 {{ (downProb * 100).toFixed(0) }}%</span>
            <span>上涨概率 {{ (upProb * 100).toFixed(0) }}%</span>
          </div>
          <el-progress
            :percentage="upProb * 100"
            :color="upProb > 0.6 ? 'var(--danger-color)' : 'var(--warning-color)'"
            :stroke-width="16"
            :format="() => ''"
          />
        </div>
      </el-card>

      <el-card shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">模型信息</span></template>
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="模型版本">{{ modelInfo.model_version || '--' }}</el-descriptions-item>
          <el-descriptions-item label="训练天数">{{ modelInfo.training_days ?? '--' }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">{{ modelInfo.model_type || '--' }}</el-descriptions-item>
          <el-descriptions-item label="训练日期">{{ modelInfo.trained_date || '--' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="shapFactors && shapFactors.length" shadow="never" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">SHAP 影响因素</span></template>
        <div v-for="f in shapFactors" :key="f.name" style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:14px">
          <span style="color:#606266">{{ f.name }}</span>
          <span :class="f.value >= 0 ? 'color-up' : 'color-down'" class="font-bold">
            {{ f.value >= 0 ? '+' : '' }}{{ (f.value * 100).toFixed(2) }}%
          </span>
        </div>
      </el-card>

      <el-card v-if="aiSummary" shadow="never">
        <template #header>
          <div style="display:flex;align-items:center;gap:6px">
            <el-icon><MagicStick /></el-icon>
            <span style="font-weight:600">AI 智能分析</span>
          </div>
        </template>
        <div style="white-space:pre-wrap;font-size:14px;line-height:1.8;color:#606266">{{ aiSummary }}</div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePredictStore } from '@/stores/predict'
import { searchFunds } from '@/api/fund'
import { formatPercent } from '@/utils/format'

const router = useRouter()
const predictStore = usePredictStore()
const fundCode = ref('')
const needTrain = ref(false)

const resultReturn = computed(() => predictStore.predictionResult?.predicted_return ?? 0)
const ciLower = computed(() => predictStore.predictionResult?.confidence_interval?.lower ?? 0)
const ciUpper = computed(() => predictStore.predictionResult?.confidence_interval?.upper ?? 0)
const upProb = computed(() => predictStore.predictionResult?.direction_probability ?? 0.5)
const downProb = computed(() => 1 - upProb.value)
const modelInfo = computed(() => predictStore.predictionResult?.model_info || {})
const shapFactors = computed(() => predictStore.predictionResult?.shap_factors || [])
const aiSummary = computed(() => predictStore.predictionResult?.ai_summary || '')

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
  needTrain.value = false
  try {
    await predictStore.predictFund({ fund_code: fundCode.value })
  } catch (e) {
    if (e.needTrain) {
      needTrain.value = true
    }
  }
}

function goTrain() {
  router.push('/train')
}
</script>