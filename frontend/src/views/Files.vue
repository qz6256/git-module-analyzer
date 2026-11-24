<template>
  <div class="page">
    <PageHeader title="文件检索" subtitle="单文件档案：当前态说明与跨提交演进主线" />

    <template v-if="hasRepo">
      <div class="filter-bar">
        <el-input v-model="filters.q" class="filter-grow" clearable placeholder="搜索文件路径 / 说明" :prefix-icon="Search" @keyup.enter="reload" />
        <el-input v-model="filters.module" clearable placeholder="所属模块" style="width: 150px" @keyup.enter="reload" />
        <el-select v-model="filters.risk" clearable placeholder="风险等级" style="width: 130px" @change="reload">
          <el-option label="高" value="高" />
          <el-option label="中" value="中" />
          <el-option label="低" value="低" />
        </el-select>
        <el-button :icon="Search" @click="reload">查询</el-button>
      </div>

      <el-card shadow="never" v-loading="loading">
        <el-table v-if="rows.length" :data="rows" size="small">
          <el-table-column label="文件路径" min-width="300">
            <template #default="{ row }">
              <router-link :to="{ path: `/files/${row.id}`, query: { repo_id: row.repo_id } }" class="mono accent-text">
                {{ row.path }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column prop="module_name" label="模块" width="150">
            <template #default="{ row }"><span class="small">{{ row.module_name || '—' }}</span></template>
          </el-table-column>
          <el-table-column prop="language" label="语言" width="100" />
          <el-table-column label="风险" width="100">
            <template #default="{ row }"><RiskTag :risk="row.risk_level" /></template>
          </el-table-column>
          <el-table-column prop="change_count" label="变更" width="70" align="center" />
          <el-table-column label="更新于" width="150">
            <template #default="{ row }"><span class="small muted">{{ formatTime(row.updated_at) }}</span></template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="暂无文件" description="尝试调整筛选条件，或先同步仓库" />

        <el-pagination
          v-if="total > 0"
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="reload"
        />
      </el-card>
    </template>

    <el-card v-else shadow="never">
      <EmptyState title="请先选择仓库" description="可在顶栏选择项目与仓库，或使用 ?repo_id= 参数直达">
        <el-button type="primary" @click="router.push('/projects')">前往项目工作台</el-button>
      </EmptyState>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import RiskTag from '@/components/RiskTag.vue'
import { filesApi } from '@/api/modules/files'
import { useRepoContext } from '@/composables/useRepoContext'
import { formatTime } from '@/utils/format'
import type { SourceFile } from '@/types'

const router = useRouter()
const { repoId, hasRepo } = useRepoContext()

const rows = ref<SourceFile[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const filters = reactive({ q: '', module: '', risk: '' })

async function load() {
  if (!repoId.value) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const result = await filesApi.getFiles(repoId.value, {
      q: filters.q || undefined,
      module: filters.module || undefined,
      risk: filters.risk || undefined,
      page: page.value,
      size: size.value,
    })
    rows.value = result.items || []
    total.value = result.total || 0
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

watch(repoId, reload)
</script>
