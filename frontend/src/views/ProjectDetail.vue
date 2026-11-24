<template>
  <div class="page" v-loading="loading">
    <div class="flex items-center gap-3" style="margin-bottom: 14px">
      <el-button text :icon="ArrowLeft" @click="router.push('/projects')">返回</el-button>
      <div>
        <div class="flex items-center gap-2">
          <h1 class="page-title">{{ project?.name || '项目详情' }}</h1>
          <span v-if="project" class="badge" :class="statusTone(project.status)">
            {{ statusLabel(project.status) }}
          </span>
        </div>
        <div class="page-subtitle">
          {{ project?.description || '暂无项目描述' }}
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <!-- 概览 -->
      <el-tab-pane label="概览" name="overview">
        <div class="grid grid-4" style="margin-bottom: 16px">
          <StatCard label="模块数" :value="overview?.module_count ?? 0" tone="accent" />
          <StatCard label="文件数" :value="overview?.file_count ?? 0" />
          <StatCard label="提交数" :value="overview?.commit_count ?? 0" />
          <StatCard label="待确认关联" :value="overview?.pending_links ?? 0" tone="warning" />
        </div>

        <div class="split">
          <el-card shadow="never">
            <template #header>
              <div class="card-head"><h3>最近活动</h3><span class="small muted">按分析记录倒序</span></div>
            </template>
            <div v-if="overview?.recent_activity?.length" class="timeline">
              <div v-for="(item, index) in overview.recent_activity" :key="item.commit_sha || index" class="tl-item">
                <span class="tl-dot" :class="riskDot(item.risk_level)" />
                <div class="tl-head">
                  <a
                    v-if="item.commit_sha"
                    class="tl-sha"
                    href="javascript:void(0)"
                    @click="openCommit(item)"
                  >{{ shortSha(item.commit_sha) }}</a>
                  <span class="small">{{ item.commit_message || item.message || '未命名变更' }}</span>
                  <RiskTag :risk="item.risk_level" />
                </div>
                <div class="tl-meta">
                  {{ item.author || '未知作者' }} · {{ formatTime(item.committed_at) }}
                  <span v-if="item.repo_name"> · {{ item.repo_name }}</span>
                </div>
              </div>
            </div>
            <EmptyState v-else title="暂无活动" description="初始化仓库并同步后将展示变更记录" />
          </el-card>

          <el-card shadow="never">
            <template #header><div class="card-head"><h3>仓库分布</h3></div></template>
            <el-table v-if="overview?.repo_breakdown?.length" :data="overview.repo_breakdown" size="small">
              <el-table-column label="仓库" min-width="130">
                <template #default="{ row }">
                  <div class="flex items-center gap-2">
                    <span class="ellipsis">{{ row.repo_name || row.display_name || row.name || '未命名' }}</span>
                    <RepoTypeTag :type="row.repo_type" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="module_count" label="模块" width="60" align="center" />
              <el-table-column prop="file_count" label="文件" width="60" align="center" />
              <el-table-column prop="commit_count" label="提交" width="60" align="center" />
            </el-table>
            <EmptyState v-else title="暂无仓库" description="在「仓库」标签下添加仓库" />
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 仓库 -->
      <el-tab-pane label="仓库" name="repositories">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <h3>仓库列表</h3>
              <el-button v-if="canManage" type="primary" size="small" :icon="Plus" @click="repoDialog = true">
                添加仓库
              </el-button>
            </div>
          </template>
          <el-table v-if="repositories.length" :data="repositories" size="small">
            <el-table-column label="仓库" min-width="180">
              <template #default="{ row }">
                <div class="flex items-center gap-2">
                  <span class="ellipsis">{{ row.display_name || row.name }}</span>
                  <RepoTypeTag :type="row.repo_type" />
                </div>
                <div class="small faint ellipsis">{{ row.source }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <span class="badge" :class="repoStatusTone(row.status)">{{ repoStatusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最近分析" width="150">
              <template #default="{ row }"><span class="small muted">{{ formatTime(row.last_analyzed_at) }}</span></template>
            </el-table-column>
            <el-table-column v-if="canManage" label="操作" width="180" align="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" :loading="busyRepo === row.id" @click="initialize(row)">
                  初始化
                </el-button>
                <el-button link size="small" :loading="busyRepo === row.id" @click="sync(row)">
                  同步
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="暂无仓库" description="添加仓库后可初始化与同步分析">
            <el-button v-if="canManage" type="primary" @click="repoDialog = true">添加仓库</el-button>
          </EmptyState>
        </el-card>
      </el-tab-pane>

      <!-- 成员 -->
      <el-tab-pane label="成员管理" name="members">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <h3>项目成员</h3>
              <el-button v-if="canManageMembers" type="primary" size="small" :icon="Plus" @click="memberDialog = true">
                添加成员
              </el-button>
            </div>
          </template>
          <el-table v-if="members.length" :data="members" size="small">
            <el-table-column label="用户" min-width="160">
              <template #default="{ row }">
                <div>{{ row.display_name || row.username || `用户 #${row.user_id}` }}</div>
                <div class="small faint">{{ row.email }}</div>
              </template>
            </el-table-column>
            <el-table-column label="项目角色" width="150">
              <template #default="{ row }">
                <span class="badge badge-blue">{{ roleLabel(row.role_code) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="加入时间" width="160">
              <template #default="{ row }"><span class="small muted">{{ formatTime(row.joined_at) }}</span></template>
            </el-table-column>
            <el-table-column v-if="canManageMembers" label="操作" width="90" align="right">
              <template #default="{ row }">
                <el-popconfirm title="确认移除该成员？" @confirm="removeMember(row)">
                  <template #reference>
                    <el-button link type="danger" size="small">移除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else title="暂无成员" description="项目角色在成员关系内生效" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加仓库 -->
    <el-dialog v-model="repoDialog" title="添加仓库" width="520px" destroy-on-close>
      <el-form :model="repoForm" label-position="top">
        <div class="grid grid-2">
          <el-form-item label="仓库名称"><el-input v-model="repoForm.name" placeholder="例如：order-service" /></el-form-item>
          <el-form-item label="显示名称"><el-input v-model="repoForm.display_name" placeholder="例如：订单服务" /></el-form-item>
        </div>
        <el-form-item label="来源（本地路径或远程地址）">
          <el-input v-model="repoForm.source" placeholder="/path/to/repo 或 https://..." />
        </el-form-item>
        <div class="grid grid-2">
          <el-form-item label="仓库类型">
            <el-select v-model="repoForm.repo_type" style="width: 100%">
              <el-option label="前端" value="frontend" />
              <el-option label="后端" value="backend" />
              <el-option label="App" value="app" />
              <el-option label="小程序" value="miniprogram" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源类型">
            <el-select v-model="repoForm.source_type" style="width: 100%">
              <el-option label="本地" value="local" />
              <el-option label="远程" value="remote" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="默认分支"><el-input v-model="repoForm.default_branch" placeholder="main" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="repoDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRepo">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加成员 -->
    <el-dialog v-model="memberDialog" title="添加成员" width="420px" destroy-on-close>
      <el-form :model="memberForm" label-position="top">
        <el-form-item label="用户 ID"><el-input-number v-model="memberForm.user_id" :min="1" style="width: 100%" /></el-form-item>
        <el-form-item label="项目角色">
          <el-select v-model="memberForm.role_code" style="width: 100%">
            <el-option label="项目负责人" value="project_owner" />
            <el-option label="开发者" value="developer" />
            <el-option label="只读成员" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMember">添加</el-button>
      </template>
    </el-dialog>

    <!-- 任务进度 -->
    <el-dialog v-model="jobDialog" title="分析任务" width="460px" :close-on-click-modal="false" @closed="stopPolling">
      <div v-if="job">
        <div class="small muted" style="margin-bottom: 10px">{{ job.message || '任务进行中…' }}</div>
        <el-progress :percentage="Math.max(0, Math.min(100, job.progress || 0))" :status="jobStatus" />
        <div class="small faint" style="margin-top: 10px">任务 ID：{{ job.job_id }}</div>
      </div>
      <template #footer>
        <el-button type="primary" @click="jobDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import RepoTypeTag from '@/components/RepoTypeTag.vue'
import RiskTag from '@/components/RiskTag.vue'
import { projectsApi } from '@/api/modules/projects'
import { repositoriesApi } from '@/api/modules/repositories'
import { useAuthStore } from '@/stores/auth'
import { formatTime, shortSha } from '@/utils/format'
import type {
  JobInfo,
  MemberOut,
  Project,
  ProjectOverview,
  Repository,
  RepoStatus,
  RepoType,
} from '@/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const projectId = computed(() => Number(route.params.id))
const project = ref<Project | null>(null)
const overview = ref<ProjectOverview | null>(null)
const members = ref<MemberOut[]>([])
const repositories = ref<Repository[]>([])
const loading = ref(false)
const activeTab = ref('overview')

const canManage = computed(
  () => auth.isAdmin || auth.hasRole('project_owner') || auth.hasRole('developer'),
)
const canManageMembers = computed(() => auth.isAdmin || auth.hasRole('project_owner'))

async function loadAll() {
  if (!projectId.value) return
  loading.value = true
  try {
    const [p, o, m, r] = await Promise.all([
      projectsApi.getProject(projectId.value),
      projectsApi.getProjectOverview(projectId.value),
      projectsApi.getMembers(projectId.value),
      projectsApi.getRepositories(projectId.value),
    ])
    project.value = p
    overview.value = o
    members.value = m
    repositories.value = r
  } finally {
    loading.value = false
  }
}

function statusLabel(status?: string) {
  return { planning: '规划中', active: '进行中', archived: '已归档' }[status || ''] || status || '未知'
}
function statusTone(status?: string) {
  if (status === 'active') return 'badge-green'
  if (status === 'planning') return 'badge-blue'
  return 'badge-gray'
}
function repoStatusLabel(status?: RepoStatus | string) {
  return {
    pending: '待初始化',
    initializing: '初始化中',
    ready: '就绪',
    syncing: '同步中',
    error: '异常',
  }[status || ''] || status || '未知'
}
function repoStatusTone(status?: RepoStatus | string) {
  if (status === 'ready') return 'badge-green'
  if (status === 'syncing' || status === 'initializing') return 'badge-blue'
  if (status === 'error') return 'badge-red'
  return 'badge-gray'
}
function roleLabel(code?: string) {
  return { admin: '管理员', project_owner: '项目负责人', developer: '开发者', viewer: '只读成员' }[code || ''] || code || '成员'
}
function riskDot(risk?: string) {
  if (risk === '高') return 'high'
  if (risk === '中') return 'mid'
  return ''
}
function openCommit(item: { commit_sha?: string; repo_id?: number }) {
  if (!item.commit_sha) return
  router.push({
    path: '/commits',
    query: { repo_id: String(item.repo_id || repositories.value[0]?.id || ''), q: item.commit_sha },
  })
}

// ---- 任务轮询 ----
const jobDialog = ref(false)
const job = ref<JobInfo | null>(null)
const busyRepo = ref<number>(0)
let timer: number | undefined

function stopPolling() {
  if (timer !== undefined) window.clearInterval(timer)
  timer = undefined
}

const jobStatus = computed(() => {
  const status = job.value?.status || ''
  if (['failed', 'error'].includes(status)) return 'exception' as const
  if (['succeeded', 'success', 'done', 'completed'].includes(status)) return 'success' as const
  return undefined
})

async function startJob(task: Promise<JobInfo>) {
  const result = await task
  job.value = result
  jobDialog.value = true
  stopPolling()
  timer = window.setInterval(async () => {
    try {
      const info = await repositoriesApi.getJob(result.job_id)
      job.value = info
      if (['succeeded', 'success', 'done', 'completed', 'failed', 'error'].includes(info.status)) {
        stopPolling()
        await loadAll()
      }
    } catch {
      stopPolling()
    }
  }, 1200)
}

async function initialize(repo: Repository) {
  busyRepo.value = repo.id
  try {
    await startJob(repositoriesApi.initializeRepository(repo.id))
    ElMessage.success('初始化任务已提交')
  } finally {
    busyRepo.value = 0
  }
}

async function sync(repo: Repository) {
  busyRepo.value = repo.id
  try {
    await startJob(repositoriesApi.syncRepository(repo.id))
    ElMessage.success('同步任务已提交')
  } finally {
    busyRepo.value = 0
  }
}

// ---- 添加仓库 / 成员 ----
const repoDialog = ref(false)
const memberDialog = ref(false)
const submitting = ref(false)
const repoForm = reactive({
  name: '',
  display_name: '',
  source: '',
  repo_type: 'backend' as RepoType,
  source_type: 'local' as 'local' | 'remote',
  default_branch: 'main',
})
const memberForm = reactive({ user_id: 0, role_code: 'developer' })

async function submitRepo() {
  if (!repoForm.name || !repoForm.source) {
    ElMessage.warning('请填写仓库名称与来源')
    return
  }
  submitting.value = true
  try {
    await repositoriesApi.createRepository(projectId.value, repoForm)
    ElMessage.success('仓库已添加')
    repoDialog.value = false
    await loadAll()
  } finally {
    submitting.value = false
  }
}

async function submitMember() {
  if (!memberForm.user_id) {
    ElMessage.warning('请输入用户 ID')
    return
  }
  submitting.value = true
  try {
    await projectsApi.addMember(projectId.value, {
      user_id: memberForm.user_id,
      role_code: memberForm.role_code,
    })
    ElMessage.success('成员已添加')
    memberDialog.value = false
    await loadAll()
  } finally {
    submitting.value = false
  }
}

async function removeMember(row: MemberOut) {
  await projectsApi.removeMember(projectId.value, row.user_id)
  ElMessage.success('成员已移除')
  await loadAll()
}

onMounted(loadAll)
onBeforeUnmount(stopPolling)
</script>
