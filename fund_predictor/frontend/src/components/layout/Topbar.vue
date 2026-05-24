<template>
  <header class="topbar">
    <div class="topbar-left">
      <!-- 移动端菜单按钮 -->
      <button class="mobile-menu-btn" @click="$emit('toggle-sidebar')">
        <el-icon :size="20"><Menu /></el-icon>
      </button>

      <!-- 面包屑导航 -->
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item v-if="currentRoute.meta?.title && currentRoute.path !== '/'">
          {{ currentRoute.meta.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="topbar-right">
      <!-- 搜索框（可选） -->
      <div class="search-box hide-mobile">
        <el-input
          v-model="searchQuery"
          placeholder="搜索基金代码..."
          :prefix-icon="Search"
          clearable
          size="default"
          class="search-input"
          @keyup.enter="handleSearch"
        />
      </div>

      <!-- 主题切换 -->
      <button class="theme-toggle" @click="$emit('toggle-theme')" :title="isDark ? '切换浅色模式' : '切换深色模式'">
        <el-icon :size="18">
          <Sunny v-if="isDark" />
          <Moon v-else />
        </el-icon>
      </button>

      <!-- 系统状态 -->
      <div class="system-status hide-mobile">
        <el-tooltip content="系统状态" placement="bottom">
          <div class="status-indicator">
            <span class="status-dot"></span>
            <span class="status-text">运行中</span>
          </div>
        </el-tooltip>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, Menu, Sunny, Moon } from '@element-plus/icons-vue'

defineEmits(['toggle-sidebar', 'toggle-theme'])

const route = useRoute()
const router = useRouter()

const currentRoute = computed(() => route)
const searchQuery = ref('')
const isDark = ref(true)

// 监听主题变化
const observer = new MutationObserver(() => {
  isDark.value = document.documentElement.getAttribute('data-theme') !== 'light'
})

observer.observe(document.documentElement, {
  attributes: true,
  attributeFilter: ['data-theme']
})

const handleSearch = () => {
  if (searchQuery.value.trim()) {
    router.push({
      path: '/predict',
      query: { code: searchQuery.value.trim() }
    })
  }
}
</script>

<style lang="scss" scoped>
.topbar {
  height: $topbar-height;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: blur(10px);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.mobile-menu-btn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: $radius-sm;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: var(--glass-bg);
    color: var(--text-primary);
  }

  @media (max-width: $breakpoint-md) {
    display: flex;
  }
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-box {
  .search-input {
    width: 240px;

    :deep(.el-input__wrapper) {
      background: var(--bg-tertiary);
      border-radius: $radius-full;
      box-shadow: none;
      border: 1px solid var(--border);

      &:hover,
      &.is-focus {
        border-color: var(--primary);
      }
    }
  }
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: $radius-sm;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all $transition-fast;

  &:hover {
    background: var(--glass-bg);
    color: var(--primary);
    border-color: var(--primary-glow);
  }
}

.system-status {
  .status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba($success, 0.1);
    border: 1px solid rgba($success, 0.2);
    border-radius: $radius-full;
    font-size: 12px;
    color: $success;
  }

  .status-dot {
    width: 6px;
    height: 6px;
    background: $success;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
  }

  .status-text {
    font-weight: 500;
  }
}

// 面包屑样式覆盖
:deep(.el-breadcrumb__inner) {
  color: var(--text-secondary);

  &.is-link:hover {
    color: var(--primary);
  }
}

:deep(.el-breadcrumb__separator) {
  color: var(--text-muted);
}

:deep(.el-breadcrumb__inner:last-child) {
  color: var(--text-primary);
  font-weight: 600;
}
</style>
