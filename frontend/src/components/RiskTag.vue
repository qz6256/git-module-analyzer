<template>
  <span class="badge" :class="tone">风险 {{ risk || '低' }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ risk?: string }>()

const tone = computed(() => {
  if (props.risk === '高') return 'badge-red'
  if (props.risk === '中') return 'badge-amber'
  return 'badge-gray'
})
</script>
