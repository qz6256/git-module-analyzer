<template>
  <div class="page">
    <PageHeader title="提交检索" subtitle="高信号过滤后的提交记录与证据摘要" />

    <template v-if="hasRepo">
      <div class="filter-bar">
        <el-input v-model="filters.q" class="filter-grow" clearable placeholder="搜索 SHA / 提交信息 / 摘要" :prefix-icon="Search" @keyup.enter="load" />
        <el-input v-model="filters.file" clearable placeholder="涉及文件" style="width: 170px" @keyup.enter="load" />
        <el-input v-model="filters.branch" clearable placeholder="分支" style="width: 130px" @keyup.enter="load" />
        <el-select v-model="filters.risk" clearable placeholder="风险" style="width: 110px" @change="load">
          <el-option label="高" value="高" />
          <el-option label="中" value="中" />
          <el-option label="低" value="低" />
        </el-select>
        <el-select v-model="filters.user_id" clearable filterable placeholder="按人员" style="width: 160px" @change="load">
          <el-option
            v-for="person in people"
            :key="person.id"
            :label="`${person.display_name || person.username} · ${person.git_identity?.name || '未绑定'}`"
            :value="person.id"
          />
        </el-select>
        <el-button :icon="Search" @click="load">查询</el-button>
      </div>

      <el-card shadow="never" v-loading="loading">
        <el-table v-if="rows.length" :data="rows" size="small">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-panel">
                <div class="tl-row"><span class="tl-label">分析摘要</span>{{ row.summary || '—' }}</div>
                <div class="tl-row"><span class="tl-label">动机</span>{{ row.motivation || '原因未知（证据不足）' }}</div>
                <div class="tl-row"><span class="tl-label">证据来源</span>{{ row.evidence_source || '未知' }}</div>
                <div class="tl-row"><span class="tl-label">分析模式</span>{{ row.analysis_mode || '—' }}</div>
                <div v-if="row.filter_reason" class="tl-row"><span class="tl-label">过滤说明</span>{{ row.filter_reason }}</div>
                <div v-if="row.affected_files?.length" class="tl-row">
                  <span class="tl-label">涉及文件</span>
                  <div class="blocks">
                    <span v-for="file in row.affected_files" :key="file" class="badge badge-gray mono">{{ file }}</span>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="提交" width="130">
            <template #default="{ row }"><span class="tl-sha">{{ shortSha(row.commit_sha) }}</span></template>
          </el-table-column>
          <el-table-column label="提交信息" min-width="240">
            <template #default="{ row }"><span class="small">{{ row.message || row.summary || '—' }}</span></template>
          </el-table-column>
          <el-table-column label="作者" width="130">
            <template #default="{ row }"><span class="small">{{ row.author || '未知' }}</span></template>
          </el-table-column>
          <el-table-column label="时间" width="150">
            <template #default="{ row }"><span class="small muted">{{ formatTime(row.committed_at) }}</span></template>
          </el-table-column>
          <el-table-column label="分支" width="120">
            <template #default="{ row }"><span class="badge badge-gray mono">{{ row.branch || '—' }}</span></template>
          </el-table-column>
          <el-table-column label="风险" width="100">
            <template #default="{ row }"><RiskTag :risk="row.risk_level" /></template>
          </el-table-column>
          <el-table-column label="信号" width="90" align="center">
            <template #default="{ row }">
              <span class="badge" :class="row.is_high_signal ? 'badge-green' : 'badge-gray'">
                {{ row.is_high_signal ? '高信号' : '低信号' }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="暂无提交记录" description="尝试放宽筛选条件，或先同步仓库" />
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
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import RiskTag from '@/components/RiskTag.vue'
import { commitsApi } from '@/api/modules/commits'
import { usersApi } from '@/api/modules/users'
import { gitIdentitiesApi } from '@/api/modules/gitIdentities'
import { useRepoContext } from '@/composables/useRepoContext'
import { formatTime, shortSha } from '@/utils/format'
import type { CommitAnalysis, GitIdentity } from '@/types'

const router = useRouter()
const { repoId, hasRepo } = useRepoContext()

const rows = ref<CommitAnalysis[]>([])
const loading = ref(false)
const filters = reactive({ q: '', file: '', branch: '', risk: '', user_id: undefined as number | undefined })
interface PersonOption { id: number; username: string; display_name?: string; git_identity?: GitIdentity | null }
const people = ref<PersonOption[]>([])

async function load() {
  if (!repoId.value) {
    rows.value = []
    return
  }
  loading.value = true
  try {
    rows.value = await commitsApi.getCommits(repoId.value, {
      q: filters.q || undefined,
      file: filters.file || undefined,
      branch: filters.branch || undefined,
      risk: filters.risk || undefined,
      user_id: filters.user_id || undefined,
    })
  } finally {
    loading.value = false
  }
}

async function loadPeople() {
  try {
    const [users, bound] = await Promise.all([
      usersApi.getUsers(),
      gitIdentitiesApi.list(true),
    ])
    const boundByUser = new Map<number, GitIdentity>()
    for (const gi of bound.items) {
      if (gi.user_id) boundByUser.set(gi.user_id, gi)
    }
    people.value = users.map((u) => ({ ...u, git_identity: boundByUser.get(u.id) || null }))
  } catch {
    people.value = []
  }
}

watch(repoId, load)
onMounted(() => {
  load()
  loadPeople()
})
</script>

<style scoped>
.expand-panel {
  padding: 8px 16px 12px 48px;
  background: var(--color-background-tertiary);
  border-radius: var(--radius);
}
</style>
