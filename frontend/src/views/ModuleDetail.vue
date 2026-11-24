<template>
  <div class="page" v-loading="loading">
    <div class="flex items-center gap-3" style="margin-bottom: 14px">
      <el-button text :icon="ArrowLeft" @click="router.push('/modules')">返回</el-button>
      <h1 class="page-title">{{ detail?.module.name || '模块档案' }}</h1>
    </div>

    <template v-if="detail">
      <el-card shadow="never" style="margin-bottom: 16px">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="hero-path">{{ detail.module.name }}</span>
          <span class="badge" :class="statusTone(detail.module.status)">{{ statusLabel(detail.module.status) }}</span>
          <RiskTag :risk="detail.module.risk_level" v-if="detail.module.risk_level" />
          <span class="badge" :class="knowledgeTone(detail.module.knowledge_status)">
            {{ knowledgeLabel(detail.module.knowledge_status) }}
          </span>
        </div>
        <div class="hero-oneliner">{{ detail.module.one_liner || '暂无一句话说明' }}</div>
        <div style="margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap">
          <span v-for="rule in detail.module.path_rules || []" :key="rule" class="badge badge-gray mono">{{ rule }}</span>
        </div>
        <div class="grid grid-3" style="margin-top: 14px">
          <div class="kv"><span class="k">职责</span><span>{{ detail.module.responsibility || '—' }}</span></div>
          <div class="kv"><span class="k">文件数</span><span>{{ detail.module.file_count ?? 0 }}</span></div>
          <div class="kv"><span class="k">变更次数</span><span>{{ detail.module.change_count ?? 0 }}</span></div>
        </div>

        <div class="meta-row">
          <div class="meta-block">
            <span class="k">模块责任人</span>
            <el-select
              v-model="ownerId"
              filterable
              clearable
              placeholder="未指定"
              style="width: 220px"
              @change="saveOwner"
            >
              <el-option v-for="user in users" :key="user.id" :label="user.display_name || user.username" :value="user.id" />
            </el-select>
          </div>
          <div class="meta-block">
            <span class="k">知识状态</span>
            <el-button-group>
              <el-button size="small" :type="detail.module.knowledge_status === 'pending' ? 'primary' : ''" @click="setKnowledge('pending')">待确认</el-button>
              <el-button size="small" :type="detail.module.knowledge_status === 'confirmed' ? 'success' : ''" @click="setKnowledge('confirmed')">已确认</el-button>
              <el-button size="small" :type="detail.module.knowledge_status === 'needs_review' ? 'warning' : ''" @click="setKnowledge('needs_review')">需复核</el-button>
            </el-button-group>
          </div>
          <div class="meta-block" v-if="detail.contributors?.length">
            <span class="k">主要提交人</span>
            <div class="flex gap-2 flex-wrap">
              <el-button v-for="item in detail.contributors" :key="item.key" size="small" text type="primary" @click="filterContributor(item)">
                {{ item.bound_user?.display_name || item.author }}（{{ item.commit_count }}）
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="detail.module.evolution_line" class="evolution" style="margin-top: 6px">
          <span class="lbl">能力演进主线</span>
          {{ detail.module.evolution_line }}
        </div>
      </el-card>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="能力变化时间线" name="timeline">
          <el-card shadow="never">
            <div v-if="detail.timeline.length" class="timeline">
              <div v-for="event in detail.timeline" :key="event.id" class="tl-item">
                <span class="tl-dot" :class="riskDot(event.risk_level)" />
                <div class="tl-head">
                  <span class="tl-sha">{{ shortSha(event.commit_sha) }}</span>
                  <span class="small">{{ event.commit_message || event.summary || '能力变化' }}</span>
                </div>
                <div class="tl-meta">
                  {{ event.bound_user?.display_name || event.author || '未知作者' }}
                  <span v-if="event.author_email"> · {{ event.author_email }}</span>
                  · {{ formatTime(event.committed_at) }} · {{ event.branch || '—' }}
                </div>
                <div class="tl-body">
                  <div class="tl-row"><span class="tl-label">能力变化</span>{{ event.capability_delta || event.summary || '—' }}</div>
                  <div v-if="event.affected_files?.length" class="tl-row">
                    <span class="tl-label">涉及文件</span>
                    <span class="mono small">{{ event.affected_files.join('、') }}</span>
                  </div>
                  <div class="tl-row"><span class="tl-label">动机</span>{{ event.motivation || '原因未知（证据不足）' }}</div>
                  <div class="tl-row">
                    <span class="tl-label">证据来源</span>{{ event.evidence_source || '未知' }}
                    <span style="margin-left: 10px"><RiskTag :risk="event.risk_level" /></span>
                  </div>
                </div>
              </div>
            </div>
            <EmptyState v-else title="暂无能力变化记录" description="同步提交后分析引擎会生成模块级变化时间线" />
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="提交记录" name="commits">
          <el-card shadow="never">
            <div class="filter-bar">
              <el-input v-model="commitQuery.author" clearable placeholder="提交人" style="width: 160px" />
              <el-select v-model="commitQuery.user_id" clearable filterable placeholder="系统用户" style="width: 180px">
                <el-option v-for="user in users" :key="user.id" :label="user.display_name || user.username" :value="user.id" />
              </el-select>
              <el-select v-model="commitQuery.branch" clearable filterable placeholder="分支" style="width: 150px">
                <el-option v-for="branch in detail.branches || []" :key="branch" :label="branch" :value="branch" />
              </el-select>
              <el-input v-model="commitQuery.q" clearable placeholder="SHA / 提交说明" style="width: 240px" />
              <el-button type="primary" @click="loadCommits(1)">筛选</el-button>
            </div>
            <el-table :data="commitRows" size="small" v-loading="commitLoading">
              <el-table-column label="SHA" width="90">
                <template #default="{ row }"><span class="mono">{{ shortSha(row.commit_sha) }}</span></template>
              </el-table-column>
              <el-table-column label="提交人" min-width="180">
                <template #default="{ row }">
                  <span>{{ row.bound_user?.display_name || row.author || '未知作者' }}</span>
                  <div class="faint small">{{ row.author_email || '无邮箱' }}</div>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="160">
                <template #default="{ row }">{{ formatTime(row.committed_at) }}</template>
              </el-table-column>
              <el-table-column prop="branch" label="分支" width="120" />
              <el-table-column label="提交说明 / 能力变化" min-width="260">
                <template #default="{ row }">
                  <div>{{ row.commit_message || row.summary || '—' }}</div>
                  <div class="faint small">{{ row.capability_delta || '暂无能力变化说明' }}</div>
                </template>
              </el-table-column>
              <el-table-column label="风险" width="90">
                <template #default="{ row }"><RiskTag :risk="row.risk_level" /></template>
              </el-table-column>
            </el-table>
            <div class="pager">
              <el-pagination
                background
                layout="total, prev, pager, next"
                :total="commitTotal"
                v-model:current-page="commitQuery.page"
                v-model:page-size="commitQuery.size"
                @current-change="loadCommits"
                @size-change="loadCommits(1)"
              />
            </div>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="文件与代码" name="files">
          <el-card shadow="never">
            <el-table v-if="detail.files.length" :data="detail.files" size="small">
              <el-table-column label="文件路径" min-width="280">
                <template #default="{ row }">
                  <router-link :to="{ path: `/files/${row.id}`, query: { repo_id: String(row.repo_id) } }" class="mono accent-text">
                    {{ row.path }}
                  </router-link>
                </template>
              </el-table-column>
              <el-table-column prop="language" label="语言" width="100" />
              <el-table-column prop="change_count" label="变更" width="70" align="center" />
              <el-table-column label="风险" width="100">
                <template #default="{ row }"><RiskTag :risk="row.risk_level" /></template>
              </el-table-column>
              <el-table-column label="一句话" min-width="220">
                <template #default="{ row }"><span class="small muted">{{ row.one_liner || '—' }}</span></template>
              </el-table-column>
              <el-table-column label="操作" width="100" align="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openSource(row)">预览代码</el-button>
                </template>
              </el-table-column>
            </el-table>
            <EmptyState v-else title="暂无文件" description="该模块下尚未归档文件" />
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="模块文档" name="doc">
          <el-card shadow="never">
            <div v-if="detail.module.current_doc" class="md-body doc-text">{{ detail.module.current_doc }}</div>
            <EmptyState v-else title="暂无模块文档" description="初始化分析后会生成当前态模块档案" />
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-card v-else-if="!loading" shadow="never">
      <EmptyState title="未找到模块" description="模块可能已被删除或 ID 不正确" />
    </el-card>

    <el-dialog v-model="sourceDialog" title="源码预览" width="900px">
      <div v-if="source?.reason" class="small muted">{{ source.reason }}</div>
      <pre v-else class="source-code">{{ source?.content }}</pre>
      <div v-if="source?.truncated" class="small muted" style="margin-top: 8px">
        已截断，共 {{ source.total_lines }} 行；完整内容请到仓库中查看。
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import EmptyState from '@/components/EmptyState.vue'
import RiskTag from '@/components/RiskTag.vue'
import { filesApi } from '@/api/modules/files'
import { modulesApi } from '@/api/modules/modules'
import { usersApi } from '@/api/modules/users'
import { formatTime, shortSha } from '@/utils/format'
import type {
  KnowledgeStatus, ModuleChangeEvent, ModuleContributor, ModuleDetail,
  SourceFile, SourcePreview, User,
} from '@/types'

const route = useRoute()
const router = useRouter()
const moduleId = Number(route.params.id)

const detail = ref<ModuleDetail | null>(null)
const loading = ref(false)
const activeTab = ref('timeline')
const users = ref<User[]>([])
const ownerId = ref<number | null>(null)
const source = ref<SourcePreview | null>(null)
const sourceDialog = ref(false)
const commitRows = ref<ModuleChangeEvent[]>([])
const commitTotal = ref(0)
const commitLoading = ref(false)
const commitQuery = reactive({
  author: '', user_id: undefined as number | undefined,
  branch: '', q: '', page: 1, size: 20,
})

function statusLabel(status?: string) {
  return { active: '活跃', dormant: '沉寂', new: '新建' }[status || ''] || status || '未知'
}
function statusTone(status?: string) {
  if (status === 'active') return 'badge-green'
  if (status === 'new') return 'badge-blue'
  return 'badge-gray'
}
function knowledgeLabel(status?: string) {
  return { pending: '待确认', confirmed: '已确认', needs_review: '需复核' }[status || ''] || status || '未知'
}
function knowledgeTone(status?: string) {
  if (status === 'confirmed') return 'badge-green'
  if (status === 'needs_review') return 'badge-amber'
  return 'badge-gray'
}
function riskDot(risk?: string) {
  if (risk === '高') return 'high'
  if (risk === '中') return 'mid'
  return ''
}

async function loadDetail() {
  detail.value = await modulesApi.getModuleDetail(moduleId)
  ownerId.value = detail.value?.module.module_owner_user_id ?? null
}

async function loadCommits(page = 1) {
  commitQuery.page = page
  commitLoading.value = true
  try {
    const result = await modulesApi.getModuleCommits(moduleId, {
      page: commitQuery.page, size: commitQuery.size,
      author: commitQuery.author || undefined,
      user_id: commitQuery.user_id,
      branch: commitQuery.branch || undefined,
      q: commitQuery.q || undefined,
    })
    commitRows.value = result.items
    commitTotal.value = result.total
  } finally {
    commitLoading.value = false
  }
}

async function saveOwner() {
  await modulesApi.updateModule(moduleId, { module_owner_user_id: ownerId.value })
  ElMessage.success('模块责任人已更新')
  await loadDetail()
}

async function setKnowledge(status: KnowledgeStatus) {
  const reviewDue = status === 'confirmed'
    ? new Date(Date.now() + 90 * 86400000).toISOString()
    : status === 'needs_review' ? new Date().toISOString() : null
  await modulesApi.updateModule(moduleId, {
    knowledge_status: status,
    review_due_at: reviewDue,
  })
  ElMessage.success('知识状态已更新')
  await loadDetail()
}

function filterContributor(item: ModuleContributor) {
  commitQuery.user_id = item.bound_user?.id
  commitQuery.author = item.bound_user ? '' : item.author
  activeTab.value = 'commits'
  void loadCommits(1)
}

async function openSource(row: SourceFile) {
  source.value = await filesApi.getFileSource(row.id, (route.query.branch as string) || undefined)
  sourceDialog.value = true
}

onMounted(async () => {
  loading.value = true
  try {
    const [usersResult] = await Promise.all([usersApi.getUsers(), loadDetail(), loadCommits(1)])
    users.value = usersResult
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.meta-row { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 14px; }
.meta-block { display: flex; flex-direction: column; gap: 6px; }
.meta-block .k, .kv .k { color: var(--color-muted); font-size: 12px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.doc-text { white-space: pre-wrap; font-size: 13px; line-height: 1.8; }
.source-code {
  margin: 0; max-height: 60vh; overflow: auto; padding: 14px;
  background: var(--color-bg-tertiary, rgba(15, 23, 42, 0.04));
  border: 1px solid var(--color-border); border-radius: 8px;
  font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; line-height: 1.6;
}
</style>
