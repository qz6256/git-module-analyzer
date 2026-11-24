<template>
  <div class="page">
    <PageHeader title="模块清单" subtitle="功能模块是归纳后的知识单元，而非文件目录的简单罗列" />

    <template v-if="hasRepo">
      <el-card shadow="never" style="margin-bottom: 16px" v-if="candidates.length">
        <template #header>
          <div class="card-head">
            <h3>新模块候选</h3>
            <span class="small muted">由新增文件 / 目录自动发现，等待人工确认</span>
          </div>
        </template>
        <div v-for="candidate in candidates" :key="candidate.id" class="candidate">
          <div class="flex items-center gap-2 flex-wrap">
            <strong class="small">{{ candidate.name }}</strong>
            <span class="badge badge-amber">待确认</span>
            <span v-for="rule in candidate.path_rules" :key="rule" class="badge badge-gray mono">{{ rule }}</span>
          </div>
          <div class="small muted" style="margin-top: 6px">{{ candidate.reason || '暂无发现依据' }}</div>
          <div class="small faint" style="margin-top: 4px">
            证据提交：<span class="mono">{{ shortSha(candidate.evidence_commit) }}</span>
            · 样例文件 {{ candidate.sample_files?.length || 0 }} 个
          </div>
          <div class="flex gap-2" style="margin-top: 10px">
            <el-button type="primary" size="small" :loading="busy === candidate.id" @click="decide(candidate.id, true)">
              确认建模块
            </el-button>
            <el-button size="small" :loading="busy === candidate.id" @click="decide(candidate.id, false)">
              忽略
            </el-button>
          </div>
        </div>
      </el-card>

      <div class="filter-bar">
        <el-input v-model="keyword" class="filter-grow" clearable placeholder="筛选模块名称 / 职责" :prefix-icon="Search" />
        <el-select v-model="statusFilter" clearable placeholder="状态" style="width: 140px">
          <el-option label="活跃" value="active" />
          <el-option label="新建" value="new" />
          <el-option label="沉寂" value="dormant" />
        </el-select>
        <el-select v-model="knowledgeFilter" clearable placeholder="知识状态" style="width: 150px">
          <el-option label="待确认" value="pending" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="需复核" value="needs_review" />
        </el-select>
      </div>

      <el-card shadow="never" v-loading="loading">
        <el-table v-if="filteredModules.length" :data="filteredModules" size="small">
          <el-table-column label="模块" min-width="180">
            <template #default="{ row }">
              <router-link :to="{ path: `/modules/${row.id}`, query: { repo_id: repoId } }" class="accent-text">
                {{ row.name }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column label="路径规则" min-width="200">
            <template #default="{ row }">
              <span v-for="rule in row.path_rules || []" :key="rule" class="badge badge-gray mono" style="margin-right: 4px">{{ rule }}</span>
              <span v-if="!row.path_rules?.length" class="faint">—</span>
            </template>
          </el-table-column>
          <el-table-column label="职责" min-width="220">
            <template #default="{ row }"><span class="small">{{ row.responsibility || row.one_liner || '—' }}</span></template>
          </el-table-column>
          <el-table-column label="责任人" min-width="120">
            <template #default="{ row }">
              <span v-if="row.owner">{{ row.owner.display_name }}</span>
              <span v-else class="faint">未指定</span>
            </template>
          </el-table-column>
          <el-table-column label="知识状态" width="110">
            <template #default="{ row }">
              <span class="badge" :class="knowledgeTone(row.knowledge_status)">{{ knowledgeLabel(row.knowledge_status) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="file_count" label="文件" width="72" align="center" />
          <el-table-column prop="change_count" label="变更" width="72" align="center" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <span class="badge" :class="statusTone(row.status)">{{ statusLabel(row.status) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="暂无模块" description="初始化并同步仓库后，系统将归纳出功能模块" />
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
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { modulesApi } from '@/api/modules/modules'
import { useRepoContext } from '@/composables/useRepoContext'
import { shortSha } from '@/utils/format'
import type { ModuleCandidate, ProjectModule } from '@/types'

const router = useRouter()
const { repoId, hasRepo } = useRepoContext()

const modules = ref<ProjectModule[]>([])
const candidates = ref<ModuleCandidate[]>([])
const loading = ref(false)
const busy = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const knowledgeFilter = ref('')

const filteredModules = computed(() =>
  modules.value.filter((module) => {
    const matchKeyword =
      !keyword.value ||
      `${module.name} ${module.responsibility || ''} ${module.one_liner || ''}`
        .toLowerCase()
        .includes(keyword.value.toLowerCase())
    const matchStatus = !statusFilter.value || module.status === statusFilter.value
    const matchKnowledge = !knowledgeFilter.value || module.knowledge_status === knowledgeFilter.value
    return matchKeyword && matchStatus && matchKnowledge
  }),
)

function knowledgeLabel(status?: string) {
  return { pending: '待确认', confirmed: '已确认', needs_review: '需复核' }[status || ''] || status || '未知'
}
function knowledgeTone(status?: string) {
  if (status === 'confirmed') return 'badge-green'
  if (status === 'needs_review') return 'badge-amber'
  return 'badge-gray'
}

function statusLabel(status?: string) {
  return { active: '活跃', dormant: '沉寂', new: '新建' }[status || ''] || status || '未知'
}
function statusTone(status?: string) {
  if (status === 'active') return 'badge-green'
  if (status === 'new') return 'badge-blue'
  return 'badge-gray'
}

async function load() {
  if (!repoId.value) {
    modules.value = []
    candidates.value = []
    return
  }
  loading.value = true
  try {
    const [list, pending] = await Promise.all([
      modulesApi.getModules(repoId.value),
      modulesApi.getModuleCandidates(repoId.value),
    ])
    modules.value = list
    candidates.value = pending.filter((item) => item.status === 'pending')
  } finally {
    loading.value = false
  }
}

async function decide(id: number, confirm: boolean) {
  busy.value = id
  try {
    if (confirm) {
      const result = await modulesApi.confirmCandidate(id)
      ElMessage.success(`已确认，纳入 ${result.file_count || 0} 个文件`)
    } else {
      await modulesApi.ignoreCandidate(id)
      ElMessage.success('已忽略该候选')
    }
    await load()
  } finally {
    busy.value = 0
  }
}

watch(repoId, load, { immediate: true })
</script>

<style scoped>
.candidate {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.candidate:last-child {
  border-bottom: none;
}
</style>
