<template>
  <el-empty :image-size="72" class="empty-state">
    <template #description>
      <div class="empty-custom">
        <div class="big">{{ title }}</div>
        <div v-if="description" class="small muted">{{ description }}</div>
      </div>
    </template>
    <slot />
  </el-empty>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style scoped>
.empty-custom .big {
  font-size: 14px;
  font-weight: 650;
  color: var(--color-foreground);
  margin-bottom: 4px;
}
</style>
