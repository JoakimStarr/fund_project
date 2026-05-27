<template>
  <div class="news-source-list">
    <div v-if="displayedList.length > 0" class="news-items">
      <div
        v-for="(news, index) in displayedList"
        :key="index"
        class="news-item"
      >
        <div class="news-content">
          <a
            :href="news.url"
            target="_blank"
            rel="noopener noreferrer"
            class="news-title"
          >
            {{ news.title }}
          </a>
          <div class="news-meta">
            <span class="source-tag" :class="getSourceClass(news.source)">
              {{ getSourceLabel(news.source) }}
            </span>
            <span class="publish-time">{{ formatRelativeTime(news.publish_time) }}</span>
          </div>
          <div class="relevance-bar">
            <span class="relevance-label">相关性</span>
            <div class="relevance-progress">
              <div
                class="relevance-fill"
                :style="{ width: `${news.relevance_score || 0}%` }"
                :class="getRelevanceClass(news.relevance_score)"
              ></div>
            </div>
            <span class="relevance-value">{{ news.relevance_score || 0 }}%</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <el-icon :size="32" color="#64748b"><Document /></el-icon>
      <span>暂无相关新闻</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Document } from '@element-plus/icons-vue'

const props = defineProps({
  newsList: {
    type: Array,
    default: () => []
  },
  maxItems: {
    type: Number,
    default: 5
  }
})

// 显示的新闻列表（限制数量）
const displayedList = computed(() => {
  if (!props.newsList || !Array.isArray(props.newsList)) return []
  return props.newsList.slice(0, props.maxItems)
})

// 获取来源标签
function getSourceLabel(source) {
  const sourceMap = {
    'cls': '财联社',
    'eastmoney': '东方财富',
    'sina': '新浪',
    '10jqka': '同花顺',
    'default': '新闻'
  }
  return sourceMap[source] || sourceMap['default']
}

// 获取来源样式类
function getSourceClass(source) {
  const classMap = {
    'cls': 'source-cls',
    'eastmoney': 'source-eastmoney',
    'sina': 'source-sina',
    '10jqka': 'source-10jqka',
    'default': 'source-default'
  }
  return classMap[source] || classMap['default']
}

// 获取相关性样式类
function getRelevanceClass(score) {
  if (score >= 80) return 'relevance-high'
  if (score >= 50) return 'relevance-medium'
  return 'relevance-low'
}

// 格式化相对时间
function formatRelativeTime(timestamp) {
  if (!timestamp) return '-'

  const now = new Date()
  const time = new Date(timestamp)
  const diff = now - time

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`

  // 超过7天显示具体日期
  const month = time.getMonth() + 1
  const day = time.getDate()
  return `${month}月${day}日`
}
</script>

<style lang="scss" scoped>
.news-source-list {
  .news-items {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .news-item {
    background: var(--bg-tertiary);
    border-radius: $radius-md;
    padding: 16px;
    border: 1px solid var(--border);
    transition: all $transition-fast;

    &:hover {
      border-color: var(--border-strong);
      transform: translateX(4px);
    }
  }

  .news-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .news-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    text-decoration: none;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    transition: color $transition-fast;

    &:hover {
      color: var(--primary);
    }
  }

  .news-meta {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .source-tag {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: $radius-sm;
    font-size: 11px;
    font-weight: 600;

    &.source-cls {
      background: rgba($primary, 0.15);
      color: $primary;
    }

    &.source-eastmoney {
      background: rgba($positive, 0.15);
      color: $positive;
    }

    &.source-sina {
      background: rgba($warning, 0.15);
      color: $warning;
    }

    &.source-10jqka {
      background: rgba($negative, 0.15);
      color: $negative;
    }

    &.source-default {
      background: rgba($neutral, 0.15);
      color: $neutral;
    }
  }

  .publish-time {
    font-size: 12px;
    color: var(--text-muted);
  }

  .relevance-bar {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .relevance-label {
    font-size: 11px;
    color: var(--text-muted);
    min-width: 36px;
  }

  .relevance-progress {
    flex: 1;
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
  }

  .relevance-fill {
    height: 100%;
    border-radius: 2px;
    transition: width $transition-normal;

    &.relevance-high {
      background: linear-gradient(90deg, $positive, #fbbf24);
    }

    &.relevance-medium {
      background: linear-gradient(90deg, $warning, #fcd34d);
    }

    &.relevance-low {
      background: $neutral;
    }
  }

  .relevance-value {
    font-size: 11px;
    color: var(--text-secondary);
    min-width: 32px;
    text-align: right;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 40px 20px;
    color: var(--text-muted);
    font-size: 14px;
  }
}
</style>
