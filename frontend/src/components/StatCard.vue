<template>
  <el-card class="stat-card" shadow="never">
    <div class="metric">
      <div class="label">{{ label }}</div>
      <div class="value" :class="`tone-${tone}`">{{ value }}</div>
      <div v-if="hint" class="small muted">{{ hint }}</div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    hint?: string
    tone?: 'default' | 'accent' | 'warning' | 'danger'
  }>(),
  { tone: 'default' },
)
</script>

<style scoped>
.stat-card :deep(.el-card__body) {
  padding: 14px 16px;
}

.tone-accent {
  color: var(--color-accent);
}

.tone-warning {
  color: var(--color-warning);
}

.tone-danger {
  color: var(--color-danger);
}
</style>
