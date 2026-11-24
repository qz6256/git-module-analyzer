<template>
  <span class="badge" :class="tone">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { REPO_TYPE_LABELS, type RepoType } from '@/types'

const props = defineProps<{ type?: RepoType | string }>()

const label = computed(() =>
  props.type ? REPO_TYPE_LABELS[props.type as RepoType] || props.type : '其他',
)
const tone = computed(() => {
  switch (props.type) {
    case 'frontend':
      return 'badge-blue'
    case 'backend':
      return 'badge-green'
    case 'app':
      return 'badge-amber'
    case 'miniprogram':
      return 'badge-gray'
    default:
      return 'badge-gray'
  }
})
</script>
