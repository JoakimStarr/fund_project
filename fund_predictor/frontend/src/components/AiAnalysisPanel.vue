<template>
  <div class="ai-analysis-panel glass-card">
    <!-- 标题栏 -->
    <div class="panel-header">
      <div class="header-left">
        <el-icon class="ai-icon" :size="20"><MagicStick /></el-icon>
        <span class="panel-title">AI 解读</span>
        <el-tag v-if="providerInfo.name" size="small" :type="providerType" effect="plain">
          {{ providerInfo.name }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-button
          type="primary"
          size="small"
          text
          :loading="loading"
          @click="refreshAnalysis"
        >
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button
          size="small"
          text
          @click="toggleCollapse"
        >
          <el-icon>
            <component :is="isCollapsed ? 'ArrowDown' : 'ArrowUp'" />
          </el-icon>
        </el-button>
      </div>
    </div>

    <!-- 内容区域 -->
    <transition name="collapse">
      <div v-show="!isCollapsed" class="panel-content">
        <!-- 加载状态 - 骨架屏 -->
        <div v-if="loading" class="skeleton-loader">
          <div class="skeleton-line skeleton-title"></div>
          <div class="skeleton-line skeleton-text"></div>
          <div class="skeleton-line skeleton-text short"></div>
          <div class="skeleton-grid">
            <div class="skeleton-card"></div>
            <div class="skeleton-card"></div>
          </div>
          <div class="skeleton-tags">
            <div class="skeleton-tag"></div>
            <div class="skeleton-tag"></div>
          </div>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="error-state">
          <el-icon :size="40" color="#64748b"><WarningFilled /></el-icon>
          <p class="error-text">{{ error }}</p>
          <el-button size="small" @click="retryLoad">重试</el-button>
        </div>

        <!-- AI 不可用 -->
        <div v-else-if="!analysisData || !analysisData.available" class="unavailable-state">
          <el-icon :size="40" color="#64748b"><Connection /></el-icon>
          <p class="unavailable-text">AI 分析暂时不可用</p>
          <p class="unavailable-hint">{{ providerInfo.unavailableReason || '请稍后再试' }}</p>
        </div>

        <!-- 分析内容 -->
        <div v-else class="analysis-content">
          <!-- 分析摘要 -->
          <div v-if="analysisData.summary" class="summary-section">
            <div class="section-label">分析摘要</div>
            <p class="summary-text">{{ analysisData.summary }}</p>
          </div>

          <!-- 关键驱动因素 -->
          <div v-if="analysisData.drivers && analysisData.drivers.length > 0" class="drivers-section">
            <div class="section-label">关键驱动因素</div>
            <div class="drivers-list">
              <div
                v-for="(driver, index) in analysisData.drivers"
                :key="index"
                class="driver-item"
                :class="driver.direction === 'positive' ? 'driver-positive' : 'driver-negative'"
              >
                <el-icon :size="16">
                  <component :is="driver.direction === 'positive' ? 'CaretTop' : 'CaretBottom'" />
                </el-icon>
                <span class="driver-text">{{ driver.text }}</span>
              </div>
            </div>
          </div>

          <!-- 风险提示 -->
          <div v-if="analysisData.risks && analysisData.risks.length > 0" class="risks-section">
            <div class="section-label">风险提示</div>
            <div class="risks-list">
              <el-tag
                v-for="(risk, index) in analysisData.risks"
                :key="index"
                type="warning"
                effect="light"
                round
                class="risk-tag"
              >
                {{ risk }}
              </el-tag>
            </div>
          </div>

          <!-- 操作建议 -->
          <div v-if="analysisData.suggestion" class="suggestion-section">
            <div class="suggestion-badge" :class="getSuggestionClass(analysisData.suggestion.action)">
              {{ getSuggestionLabel(analysisData.suggestion.action) }}
            </div>
            <p v-if="analysisData.suggestion.reason" class="suggestion-reason">
              {{ analysisData.suggestion.reason }}
            </p>
          </div>

          <!-- 参考新闻来源 -->
          <div v-if="analysisData.news && analysisData.news.length > 0" class="news-section">
            <div class="section-label">参考新闻</div>
            <NewsSourceList :news-list="analysisData.news" :max-items="3" />
          </div>

          <!-- 更新时间 -->
          <div v-if="analysisData.updated_at" class="update-time">
            更新于: {{ formatTime(analysisData.updated_at) }}
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import {
  MagicStick, Refresh, ArrowUp, ArrowDown,
  WarningFilled, Connection, CaretTop, CaretBottom
} from '@element-plus/icons-vue'
import NewsSourceList from './NewsSourceList.vue'
import { getAIAnalysis, getProviderStatus } from '@/api/ai_analysis'

const props = defineProps({
  fundCode: {
    type: String,
    required: true
  },
  estimationReturn: {
    type: [Number, String],
    default: null
  },
  lowerBound: {
    type: [Number, String],
    default: null
  },
  upperBound: {
    type: [Number, String],
    default: null
  },
  source: {
    type: String,
    default: ''
  }
})

// 状态
const loading = ref(false)
const error = ref('')
const isCollapsed = ref(false)
const analysisData = reactive({
  available: false,
  summary: '',
  drivers: [],
  risks: [],
  suggestion: null,
  news: [],
  updated_at: null,
  provider: null
})

// Provider 信息
const providerInfo = reactive({
  name: '',
  available: false,
  unavailableReason: ''
})

// Provider 标签类型
const providerType = computed(() => {
  if (!providerInfo.available) return 'info'
  return 'success'
})

// 监听 fundCode 变化自动加载
watch(() => props.fundCode, (newCode) => {
  if (newCode) {
    loadAnalysis()
  }
}, { immediate: false })

// 组件挂载时加载数据
onMounted(() => {
  if (props.fundCode) {
    loadAnalysis()
    checkProviderStatus()
  }
})

// 加载 AI 分析数据
async function loadAnalysis(forceRefresh = false) {
  if (!props.fundCode) return

  loading.value = true
  error.value = ''

  try {
    const params = {}
    if (props.source) params.source = props.source
    if (forceRefresh) params._t = Date.now() // 绕过缓存

    // 如果有估算参数，传递给后端
    if (props.estimationReturn !== null) {
      params.estimation_return = props.estimationReturn
    }
    if (props.lowerBound !== null) {
      params.lower_bound = props.lowerBound
    }
    if (props.upperBound !== null) {
      params.upper_bound = props.upperBound
    }

    const res = await getAIAnalysis(props.fundCode, params)
    const data = res.data || res

    if (data) {
      Object.assign(analysisData, {
        available: data.available !== false,
        summary: data.summary || '',
        drivers: data.drivers || [],
        risks: data.risks || [],
        suggestion: data.suggestion || null,
        news: data.news || [],
        updated_at: data.updated_at || new Date().toISOString(),
        provider: data.provider || null
      })

      // 更新 Provider 信息
      if (data.provider) {
        providerInfo.name = data.provider.name || 'AI'
        providerInfo.available = true
      }
    }
  } catch (err) {
    console.error('AI 分析加载失败:', err)

    // 判断是否是 AI 不可用的错误
    if (err.response?.status === 503 || err.message?.includes('unavailable')) {
      analysisData.available = false
      providerInfo.available = false
      providerInfo.unavailableReason = err.response?.data?.error?.message || '服务暂时不可用'
    } else {
      error.value = err.message || '加载失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}

// 检查 Provider 状态
async function checkProviderStatus() {
  try {
    const res = await getProviderStatus()
    const data = res.data || res

    if (data) {
      providerInfo.name = data.provider_name || 'AI'
      providerInfo.available = data.available !== false
      providerInfo.unavailableReason = data.unavailable_reason || ''
    }
  } catch (err) {
    console.error('检查 Provider 状态失败:', err)
  }
}

// 刷新分析（绕过缓存）
function refreshAnalysis() {
  loadAnalysis(true)
}

// 重试加载
function retryLoad() {
  error.value = ''
  loadAnalysis()
}

// 折叠/展开
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

// 获取建议样式类
function getSuggestionClass(action) {
  const classMap = {
    'buy': 'suggestion-buy',
    'hold': 'suggestion-hold',
    'sell': 'suggestion-sell',
    'watch': 'suggestion-watch'
  }
  return classMap[action] || 'suggestion-watch'
}

// 获取建议标签
function getSuggestionLabel(action) {
  const labelMap = {
    'buy': '增持',
    'hold': '持有',
    'sell': '减持',
    'watch': '观望'
  }
  return labelMap[action] || '观望'
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return '-'

  const date = new Date(timestamp)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}
</script>

<style lang="scss" scoped>
.ai-analysis-panel {
  margin-bottom: 24px;
  overflow: hidden;
}

/* 标题栏 */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;

  .ai-icon {
    color: var(--primary);
    animation: sparkle 2s ease-in-out infinite;
  }

  .panel-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

@keyframes sparkle {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.1);
  }
}

/* 内容区域 */
.panel-content {
  padding: 20px;
}

/* 折叠动画 */
.collapse-enter-active,
.collapse-leave-active {
  transition: all $transition-normal;
  max-height: 2000px;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* 骨架屏 */
.skeleton-loader {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 0;
}

.skeleton-line {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    rgba(255, 255, 255, 0.08) 50%,
    var(--bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
  border-radius: $radius-sm;

  &.skeleton-title {
    height: 20px;
    width: 40%;
  }

  &.skeleton-text {
    height: 14px;
    width: 100%;

    &.short {
      width: 60%;
    }
  }
}

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;

  @media (max-width: $breakpoint-sm) {
    grid-template-columns: 1fr;
  }
}

.skeleton-card {
  height: 80px;
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    rgba(255, 255, 255, 0.08) 50%,
    var(--bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
  border-radius: $radius-md;
}

.skeleton-tags {
  display: flex;
  gap: 8px;
}

.skeleton-tag {
  height: 28px;
  width: 80px;
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    rgba(255, 255, 255, 0.08) 50%,
    var(--bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite;
  border-radius: $radius-full;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* 错误和不可用状态 */
.error-state,
.unavailable-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  text-align: center;

  .error-text,
  .unavailable-text {
    font-size: 15px;
    color: var(--text-secondary);
    margin: 0;
  }

  .unavailable-hint {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0;
  }
}

/* 分析内容 */
.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: fadeIn 0.5s ease;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

/* 摘要 */
.summary-section {
  .summary-text {
    font-size: 14px;
    line-height: 1.7;
    color: var(--text-secondary);
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

/* 驱动因素 */
.drivers-section {
  .drivers-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .driver-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: $radius-md;
    font-size: 13px;
    transition: all $transition-fast;

    &.driver-positive {
      background: rgba($positive, 0.08);
      color: $positive;
      border-left: 3px solid $positive;
    }

    &.driver-negative {
      background: rgba($negative, 0.08);
      color: $negative;
      border-left: 3px solid $negative;
    }

    .driver-text {
      flex: 1;
    }
  }
}

/* 风险提示 */
.risks-section {
  .risks-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .risk-tag {
    font-size: 12px;
  }
}

/* 操作建议 */
.suggestion-section {
  text-align: center;
  padding: 20px;
  background: var(--bg-tertiary);
  border-radius: $radius-lg;
}

.suggestion-badge {
  display: inline-block;
  padding: 12px 32px;
  border-radius: $radius-full;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 2px;
  margin-bottom: 12px;

  &.suggestion-buy {
    background: linear-gradient(135deg, rgba($positive, 0.2), rgba($positive, 0.1));
    color: $positive;
    border: 2px solid rgba($positive, 0.3);
    text-shadow: 0 0 30px rgba($positive, 0.3);
  }

  &.suggestion-hold {
    background: linear-gradient(135deg, rgba($warning, 0.2), rgba($warning, 0.1));
    color: $warning;
    border: 2px solid rgba($warning, 0.3);
    text-shadow: 0 0 30px rgba($warning, 0.3);
  }

  &.suggestion-sell {
    background: linear-gradient(135deg, rgba($negative, 0.2), rgba($negative, 0.1));
    color: $negative;
    border: 2px solid rgba($negative, 0.3);
    text-shadow: 0 0 30px rgba($negative, 0.3);
  }

  &.suggestion-watch {
    background: linear-gradient(135deg, rgba($neutral, 0.2), rgba($neutral, 0.1));
    color: $neutral;
    border: 2px solid rgba($neutral, 0.3);
  }
}

.suggestion-reason {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

/* 新闻区域 */
.news-section {
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

/* 更新时间 */
.update-time {
  font-size: 11px;
  color: var(--text-muted);
  text-align: right;
  font-family: 'SF Mono', monospace;
}

/* 淡入动画 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
