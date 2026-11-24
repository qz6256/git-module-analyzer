<template>
  <span class="badge" :class="tone">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { REVIEW_STATUS_LABELS, type ReviewStatus } from '@/types'

const props = defineProps<{ status?: ReviewStatus | string }>()

const label = computed(() =>
  props.status ? REVIEW_STATUS_LABELS[props.status as ReviewStatus] || props.status : '待复核',
)
const tone = computed(() => {
  if (props.status === 'confirmed') return 'badge-green'
  if (props.status === 'rejected') return 'badge-red'
  return 'badge-amber'
})
</script>
