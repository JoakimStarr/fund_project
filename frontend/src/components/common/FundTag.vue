<template>
  <span class="fund-tag" :class="[`fund-tag--${type}`, { 'fund-tag--clickable': clickable }]">
    <span class="fund-tag__code">{{ code }}</span>
    <span v-if="name" class="fund-tag__name">{{ name }}</span>
    <el-tag v-if="typeLabel" size="small" effect="plain" class="fund-tag__type">
      {{ typeLabel }}
    </el-tag>
  </span>
</template>

<script setup>
defineProps({
  code: { type: String, required: true },
  name: { type: String, default: '' },
  type: { type: String, default: 'default' },
  typeLabel: { type: String, default: '' },
  clickable: { type: Boolean, default: false }
})
</script>

<style scoped lang="scss">
.fund-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  transition: all var(--duration-fast) var(--ease-in-out);

  &--default {
    background: var(--bg-secondary);
    color: var(--text-primary);
  }

  &--primary {
    background: rgba(26, 115, 232, 0.08);
    color: var(--primary);
  }

  &--success {
    background: rgba(0, 184, 148, 0.08);
    color: var(--success);
  }

  &--clickable {
    cursor: pointer;
    @media (hover: hover) {
      &:hover {
        background: rgba(26, 115, 232, 0.12);
      }
    }
  }
}

.fund-tag__code {
  font-family: var(--font-mono);
  font-weight: 600;
}

.fund-tag__name {
  color: var(--text-secondary);
}

.fund-tag__type {
  transform: scale(0.85);
}
</style>