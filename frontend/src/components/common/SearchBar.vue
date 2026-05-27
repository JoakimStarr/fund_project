<template>
  <div class="search-bar" :class="{ 'search-bar--loading': loading }">
    <el-autocomplete
      v-model="model"
      :fetch-suggestions="fetchSuggestions"
      :placeholder="placeholder"
      clearable
      :debounce="300"
      :trigger-on-focus="false"
      class="search-bar__input"
      @keyup.enter="$emit('search', model)"
      @select="$emit('select', $event)"
    >
      <template #prefix>
        <el-icon class="search-bar__icon"><Search /></el-icon>
      </template>
      <template #default="{ item }">
        <div class="search-suggestion">
          <span class="search-suggestion__code">{{ item.code }}</span>
          <span class="search-suggestion__name">{{ item.name }}</span>
          <el-tag v-if="item.type" size="small" effect="plain">{{ item.type }}</el-tag>
        </div>
      </template>
    </el-autocomplete>
    <slot name="extra" />
  </div>
</template>

<script setup>
const model = defineModel()

defineProps({
  placeholder: { type: String, default: '输入基金代码或名称搜索' },
  loading: { type: Boolean, default: false },
  fetchSuggestions: { type: Function, default: () => [] }
})

defineEmits(['search', 'select'])
</script>

<style scoped lang="scss">
.search-bar {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
}

.search-bar__input {
  flex: 1;
  :deep(.el-autocomplete) {
    width: 100%;
  }
}

.search-bar__icon {
  color: var(--text-tertiary);
}

.search-suggestion {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 4px 0;
}

.search-suggestion__code {
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.search-suggestion__name {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>