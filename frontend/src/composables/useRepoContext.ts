import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'

/** 各分析页共享：优先使用 URL 中的 repo_id，否则用顶栏选中的仓库 */
export function useRepoContext() {
  const route = useRoute()
  const projectStore = useProjectStore()

  const repoId = computed(() => {
    const fromQuery = Number(route.query.repo_id)
    return fromQuery > 0 ? fromQuery : projectStore.currentRepoId
  })
  const hasRepo = computed(() => repoId.value > 0)

  return { repoId, hasRepo, projectStore }
}
