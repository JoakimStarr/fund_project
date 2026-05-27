<template>
  <nav class="mobile-tabbar">
    <router-link
      v-for="item in tabItems"
      :key="item.path"
      :to="item.path"
      class="tab-item"
      :class="{ 'tab-item--active': $route.path === item.path }"
    >
      <el-icon :size="20"><component :is="item.icon" /></el-icon>
      <span class="tab-label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<script setup>
const tabItems = [
  { path: '/', label: '决策中心', icon: 'DataAnalysis' },
  { path: '/intraday', label: '盘中估算', icon: 'Timer' },
  { path: '/train', label: '模型训练', icon: 'Setting' },
  { path: '/compare', label: '对比', icon: 'Grid' },
  { path: '/profile', label: '基金画像', icon: 'UserFilled' },
]
</script>

<style scoped lang="scss">
.mobile-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: var(--bg-primary);
  border-top: 1px solid var(--border);
  z-index: 1000;
  padding-bottom: env(safe-area-inset-bottom);
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  color: var(--text-tertiary);
  text-decoration: none;
  transition: color var(--duration-fast) var(--ease-in-out);
  -webkit-tap-highlight-color: transparent;

  &--active {
    color: var(--primary);
  }
}

.tab-label {
  font-size: var(--font-size-xs);
  line-height: 1;
}
</style>