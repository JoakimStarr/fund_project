<template>
  <div class="app-wrapper" :class="{ 'is-dark': isDarkTheme }">
    <!-- 侧边导航 -->
    <Sidebar :collapsed="sidebarCollapsed" @toggle="toggleSidebar" />

    <!-- 主内容区 -->
    <div class="main-container" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <!-- 顶部栏 -->
      <Topbar @toggle-sidebar="toggleSidebar" @toggle-theme="toggleTheme" />

      <!-- 路由视图 -->
      <main class="content-area">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- 全局加载遮罩 -->
    <div v-if="globalLoading" class="global-loading-overlay">
      <div class="loading-content">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <span>{{ globalLoadingText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onErrorCaptured } from 'vue'
import { useAppStore } from '@/stores/app'
import logger from '@/utils/logger'
import Sidebar from '@/components/layout/Sidebar.vue'
import Topbar from '@/components/layout/Topbar.vue'

onErrorCaptured((err, instance, info) => {
  logger.error('vue', `组件渲染错误: ${err.message}`, {
    component: instance?.$options?.name || instance.type?.name || 'unknown',
    info,
    stack: err.stack,
    message: err.message,
  })
  if (import.meta.env.DEV) {
    console.error('[Vue Error]', err, info)
  }
})

const appStore = useAppStore()
const sidebarCollapsed = ref(false)
const isDarkTheme = ref(true)
const globalLoading = ref(false)
const globalLoadingText = ref('')

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const toggleTheme = () => {
  isDarkTheme.value = !isDarkTheme.value
  document.documentElement.setAttribute('data-theme', isDarkTheme.value ? 'dark' : 'light')
}

onMounted(() => {
  // 初始化主题
  const savedTheme = localStorage.getItem('theme')
  isDarkTheme.value = savedTheme !== 'light'
  document.documentElement.setAttribute('data-theme', isDarkTheme.value ? 'dark' : 'light')

  // 监听全局加载状态
  appStore.$onAction(({ name, after }) => {
    if (name === 'setLoading') {
      after((loading) => {
        globalLoading.value = loading
        globalLoadingText.value = appStore.loadingText || '加载中...'
      })
    }
  })
})
</script>

<style lang="scss">
.app-wrapper {
  display: flex;
  min-height: 100vh;
  background: $dark-bg-primary;
  color: $text-primary;
  transition: background-color $transition-normal, color $transition-normal;

  &.is-light {
    background: #f8fafc;
    color: #1e293b;
  }
}

.main-container {
  flex: 1;
  margin-left: $sidebar-width;
  transition: margin-left $transition-normal;
  min-height: 100vh;
  display: flex;
  flex-direction: column;

  &.sidebar-collapsed {
    margin-left: 64px;
  }
}

.content-area {
  flex: 1;
  padding: $content-padding;
  overflow-y: auto;
  max-width: calc(100vw - #{$sidebar-width});
  transition: max-width $transition-normal;
}

.sidebar-collapsed .content-area {
  max-width: calc(100vw - 64px);
}

/* 全局加载遮罩 */
.global-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(11, 18, 32, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: $text-secondary;
  font-size: 14px;
}

/* 页面过渡动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
