<template>
  <div class="page" v-loading="loading">
    <PageHeader title="项目模块总览" subtitle="按工程项目聚合多个代码仓库的功能模块，快速查看责任人、知识状态与最近变更" />

    <div class="filter-bar">
      <el-select
        v-model="projectId"
        filterable
        placeholder="选择项目"
        style="width: 260px"
        @change="load"
      >
        <el-option v-for="item in projectStore.projects" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
      <el-input v-model="keyword" class="filter-grow" clearable placeholder="筛选模块 / 仓库 / 责任人" :prefix-icon="Search" />
      <el-select v-model="statusFilter" clearable placeholder="知识状态" style="width: 160px">
        <el-option label="待确认" value="pending" />
        <el-option label="已确认" value="confirmed" />
        <el-option label="需复核" value="needs_review" />
      </el-select>
    </div>

    <el-card shadow="never">
      <el-table v-if="filtered.length" :data="filtered" size="small">
        <el-table-column label="仓库" min-width="150">
          <template #default="{ row }">
            <span>{{ row.repo?.display_name || row.repo?.name || `#${row.repo_id}` }}</span>
            <div class="faint small">{{ row.repo?.repo_type || 'other' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="功能模块" min-width="240">
          <template #default="{ row }">
            <router-link :to="{ path: `/modules/${row.id}`, query: { repo_id: String(row.repo_id) } }" class="accent-text">
              {{ row.name }}
            </router-link>
            <div class="faint small">{{ row.one_liner || row.responsibility || '暂无说明' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="file_count" label="文件" width="70" align="center" />
        <el-table-column prop="commit_count" label="提交" width="70" align="center" />
        <el-table-column prop="change_count" label="变更" width="70" align="center" />
        <el-table-column label="责任人" min-width="130">
          <template #default="{ row }">
            <span v-if="row.owner">{{ row.owner.display_name }}</span>
            <span v-else class="faint">未指定</span>
          </template>
        </el-table-column>
        <el-table-column label="知识状态" width="110">
          <template #default="{ row }">
            <span class="badge" :class="statusTone(row.knowledge_status)">{{ statusLabel(row.knowledge_status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近变更" width="170">
          <template #default="{ row }">{{ formatTime(row.last_change_at) || '—' }}</template>
        </el-table-column>
      </el-table>
      <EmptyState v-else title="暂无模块" description="请先添加仓库并完成冷启动分析" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { modulesApi } from '@/api/modules/modules'
import { useProjectStore } from '@/stores/project'
import { formatTime } from '@/utils/format'
import type { ProjectModuleOverview } from '@/types'

const route = useRoute()
const projectStore = useProjectStore()
const projectId = ref(Number(route.query.project_id) || projectStore.currentProjectId)
const rows = ref<ProjectModuleOverview[]>([])
const keyword = ref('')
const statusFilter = ref('')
const loading = ref(false)

const filtered = computed(() => rows.value.filter((row) => {
  const text = `${row.name} ${row.one_liner || ''} ${row.repo?.display_name || row.repo?.name || ''} ${row.owner?.display_name || ''}`.toLowerCase()
  return (!keyword.value || text.includes(keyword.value.toLowerCase()))
    && (!statusFilter.value || row.knowledge_status === statusFilter.value)
}))

function statusLabel(status?: string) {
  return { pending: '待确认', confirmed: '已确认', needs_review: '需复核' }[status || ''] || status || '未知'
}
function statusTone(status?: string) {
  if (status === 'confirmed') return 'badge-green'
  if (status === 'needs_review') return 'badge-amber'
  return 'badge-gray'
}

async function load() {
  if (!projectId.value) {
    rows.value = []
    return
  }
  loading.value = true
  try {
    rows.value = await modulesApi.getProjectModules(projectId.value)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!projectStore.projects.length) await projectStore.fetchProjects()
  if (!projectId.value) projectId.value = projectStore.currentProjectId
  await load()
})

watch(projectId, (id) => {
  if (id && id !== projectStore.currentProjectId) projectStore.selectProject(id)
})
</script>
