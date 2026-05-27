<template>
  <PageContainer narrow>
    <div class="page-header mb-16">
      <h2 class="page-title">模型监控</h2>
    </div>
    <SectionCard>
      <div class="coming-soon">
        <el-icon :size="48" color="#c0c4cc"><Monitor /></el-icon>
        <p class="coming-soon-text">模型监控功能开发中</p>
      </div>
    </SectionCard>
  </PageContainer>
</template>

<style scoped lang="scss">
.page-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0;
}

.coming-soon-text {
  margin-top: var(--space-md);
  color: var(--text-tertiary);
  font-size: var(--font-size-base);
}
</style>