<template>
  <header class="topbar">
    <div class="topbar-left">
      <el-icon :size="18" class="collapse-btn" @click="appStore.toggleSidebar">
        <Fold v-if="!appStore.sidebarCollapsed" />
        <Expand v-else />
      </el-icon>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item to="/">
          <span class="breadcrumb-home">首页</span>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-if="$route.meta.title">
          <span class="breadcrumb-current">{{ $route.meta.title }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>
    <div class="topbar-right">
      <el-tooltip :content="marketStatus.note" placement="bottom" :show-after="300">
        <div class="market-badge" :class="`market-badge--${marketStatus.session}`">
          <span class="market-dot" />
          <span class="market-label">{{ marketStatus.note }}</span>
        </div>
      </el-tooltip>
      <el-tooltip content="AI 服务状态" placement="bottom" :show-after="300">
        <div class="ai-status" :class="{ 'ai-status--online': appStore.aiProviderStatus?.available }">
          <el-icon :size="16">
            <Monitor />
          </el-icon>
        </div>
      </el-tooltip>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const marketStatus = computed(() => appStore.marketSession)
</script>

<style scoped lang="scss">
.topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-lg);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.collapse-btn {
  cursor: pointer;
  color: var(--text-secondary);
  transition: color var(--duration-fast) var(--ease-in-out);
  &:hover {
    color: var(--primary);
  }
}

.breadcrumb-home {
  color: var(--text-secondary);
  font-size: var(--font-size-base);
}

.breadcrumb-current {
  color: var(--text-primary);
  font-weight: 500;
  font-size: var(--font-size-base);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.market-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  transition: all var(--duration-fast) var(--ease-in-out);

  &--morning,
  &--afternoon {
    background: rgba(0, 184, 148, 0.1);
    color: var(--success);
    .market-dot {
      background: var(--success);
    }
  }

  &--lunch {
    background: rgba(253, 203, 110, 0.15);
    color: #b8860b;
    .market-dot {
      background: var(--warning);
    }
  }

  &--closed {
    .market-dot {
      background: var(--text-tertiary);
    }
  }
}

.market-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.market-label {
  white-space: nowrap;
}

.ai-status {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  cursor: default;
  transition: all var(--duration-fast) var(--ease-in-out);

  &--online {
    color: var(--success);
    background: rgba(0, 184, 148, 0.1);
  }
}
</style>