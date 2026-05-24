<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- Logo 区域 -->
    <div class="sidebar-header">
      <router-link to="/" class="logo-link">
        <div class="logo">QuantDesk</div>
        <div class="logo-subtitle" v-show="!collapsed">量化决策系统</div>
      </router-link>
    </div>

    <!-- 导航菜单 -->
    <nav class="nav-menu">
      <ul class="nav-list">
        <li
          v-for="item in menuItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <router-link :to="item.path" class="nav-link">
            <el-icon :size="20">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-text" v-show="!collapsed">{{ item.title }}</span>
          </router-link>
        </li>
      </ul>
    </nav>

    <!-- 底部信息 -->
    <div class="sidebar-footer" v-show="!collapsed">
      <div class="version-info">
        <span>v1.0.0</span>
        <span class="status-dot online"></span>
      </div>
    </div>

    <!-- 折叠按钮 -->
    <button class="toggle-btn" @click="$emit('toggle')" :title="collapsed ? '展开' : '收起'">
      <el-icon :size="16">
        <Fold v-if="!collapsed" />
        <Expand v-else />
      </el-icon>
    </button>
  </aside>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { Fold, Expand } from '@element-plus/icons-vue'

defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

defineEmits(['toggle'])

const route = useRoute()

const menuItems = [
  { path: '/', title: '决策中心', icon: 'DataAnalysis' },
  { path: '/predict', title: '智能预测', icon: 'TrendCharts' },
  { path: '/train', title: '模型训练', icon: 'Setting' },
  { path: '/backtest', title: '回测诊断', icon: 'DataLine' },
  { path: '/model-monitor', title: '模型监控', icon: 'Monitor' },
  { path: '/compare', title: '多基金对比', icon: 'DataLine' },
  { path: '/profile', title: '基金画像', icon: 'UserFilled' },
  { path: '/intraday', title: 'T日盘中估算', icon: 'Timer' },
  { path: '/admin/data-status', title: '数据管理', icon: 'SetUp' }
]

const isActive = (path) => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}
</script>

<style lang="scss" scoped>
.sidebar {
  width: $sidebar-width;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 100;
  display: flex;
  flex-direction: column;
  transition: width $transition-normal;

  &.collapsed {
    width: 64px;

    .nav-text,
    .logo-subtitle,
    .version-info {
      opacity: 0;
      visibility: hidden;
    }

    .nav-link {
      justify-content: center;
      padding: 12px;
    }

    .toggle-btn {
      right: -12px;
    }
  }
}

.sidebar-header {
  padding: 24px 20px;
  border-bottom: 1px solid var(--border);
}

.logo-link {
  text-decoration: none;
  display: block;
}

.logo {
  font-size: 22px;
  font-weight: 800;
  @extend .gradient-text !optional;
  letter-spacing: -0.5px;
  transition: font-size $transition-normal;

  .collapsed & {
    font-size: 18px;
    text-align: center;
  }
}

.logo-subtitle {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: opacity $transition-fast;
}

.nav-menu {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-item {
  margin-bottom: 4px;

  &.active {
    .nav-link {
      background: var(--primary-soft);
      color: var(--primary);
      border-color: var(--primary-glow);

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 20px;
        background: var(--primary);
        border-radius: 0 2px 2px 0;
      }
    }
  }
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border-radius: $radius-sm;
  border: 1px solid transparent;
  transition: all $transition-fast;
  position: relative;

  &:hover {
    background: var(--glass-bg);
    color: var(--text-primary);
    border-color: var(--glass-border);
  }
}

.nav-text {
  white-space: nowrap;
  transition: opacity $transition-fast;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.version-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  transition: opacity $transition-fast;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &.online {
    background: $success;
    box-shadow: 0 0 8px rgba($success, 0.5);
  }
}

.toggle-btn {
  position: absolute;
  top: 50%;
  right: -12px;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-left: none;
  border-radius: 0 $radius-sm $radius-sm 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all $transition-fast;

  &:hover {
    background: var(--primary-soft);
    color: var(--primary);
    border-color: var(--primary-glow);
  }
}
</style>
