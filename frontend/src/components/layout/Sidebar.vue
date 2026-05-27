<template>
  <aside
    class="sidebar"
    :class="{ 'sidebar--collapsed': appStore.sidebarCollapsed }"
  >
    <router-link to="/" class="sidebar-logo">
      <div class="logo-icon">
        <el-icon :size="24" color="#fff"><DataAnalysis /></el-icon>
      </div>
      <span v-show="!appStore.sidebarCollapsed" class="logo-text">基金预测系统</span>
    </router-link>

    <el-menu
      :default-active="$route.path"
      router
      :collapse="appStore.sidebarCollapsed"
      class="sidebar-menu"
    >
      <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <template #title>{{ item.title }}</template>
      </el-menu-item>
    </el-menu>

    <div v-show="!appStore.sidebarCollapsed" class="sidebar-footer">
      <div class="version-badge">v2.1.0</div>
    </div>
  </aside>
</template>

<script setup>
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const menuItems = [
  { path: '/', title: '决策中心', icon: 'DataAnalysis' },
  { path: '/intraday', title: 'T日盘中估算', icon: 'Timer' },
  { path: '/train', title: '模型训练', icon: 'Setting' },
  { path: '/backtest', title: '回测诊断', icon: 'DataLine' },
  { path: '/compare', title: '多基金对比', icon: 'Grid' },
  { path: '/profile', title: '基金画像', icon: 'UserFilled' },
  { path: '/monitor', title: '模型监控', icon: 'Monitor' },
  { path: '/admin/data', title: '数据管理', icon: 'SetUp' },
]
</script>

<style scoped lang="scss">
.sidebar {
  width: var(--sidebar-width);
  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  transition: width var(--duration-normal) var(--ease-out-expo);

  &--collapsed {
    width: var(--sidebar-collapsed-width);
  }
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-md);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  text-decoration: none;
  flex-shrink: 0;
  overflow: hidden;
}

.logo-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, #1a73e8, #6c5ce7);
  flex-shrink: 0;
}

.logo-text {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  letter-spacing: 0.5px;
}

.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  border-right: none !important;
  background: transparent !important;

  :deep(.el-menu-item) {
    color: rgba(255, 255, 255, 0.65) !important;
    transition: all var(--duration-fast) var(--ease-in-out);
    border-radius: 0;
    margin: 2px 0;

    &:hover {
      background: rgba(255, 255, 255, 0.06) !important;
      color: rgba(255, 255, 255, 0.9) !important;
    }

    &.is-active {
      color: #fff !important;
      background: rgba(26, 115, 232, 0.3) !important;
      position: relative;

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 20px;
        background: var(--primary);
        border-radius: 0 3px 3px 0;
      }
    }
  }
}

.sidebar-footer {
  padding: var(--space-sm) var(--space-md);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.version-badge {
  font-size: var(--font-size-xs);
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
  font-family: var(--font-mono);
}
</style>