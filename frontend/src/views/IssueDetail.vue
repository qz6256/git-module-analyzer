<template>
  <div class="page" v-loading="loading">
    <div class="flex items-center gap-3" style="margin-bottom: 14px">
      <el-button text :icon="ArrowLeft" @click="router.push('/issues')">返回</el-button>
      <h1 class="page-title">追溯详情</h1>
    </div>

    <template v-if="detail">
      <el-card shadow="never" style="margin-bottom: 16px">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="hero-path">{{ detail.issue.external_id }}</span>
          <span class="badge" :class="detail.issue.issue_type === 'bug' ? 'badge-red' : 'badge-blue'">
            {{ detail.issue.issue_type === 'bug' ? '缺陷' : '需求' }}
          </span>
          <span class="badge" :class="detail.issue.status === 'open' ? 'badge-amber' : 'badge-gray'">
            {{ detail.issue.status === 'open' ? '处理中' : detail.issue.status }}
          </span>
          <span v-if="detail.issue.source" class="badge badge-gray">来源 {{ detail.issue.source }}</span>
        </div>
        <div class="hero-oneliner">{{ detail.issue.title || '（无标题）' }}</div>
        <div v-if="detail.issue.description" class="small muted" style="margin-top: 8px; white-space: pre-wrap">
          {{ detail.issue.description }}
        </div>
        <div class="grid grid-3" style="margin-top: 14px">
          <div class="kv"><span class="k">报告人</span><span>{{ detail.issue.reporter || '—' }}</span></div>
          <div class="kv"><span class="k">发生时间</span><span>{{ formatTime(detail.issue.occurred_at) }}</span></div>
          <div class="kv"><span class="k">相关路径</span><span class="mono small">{{ (detail.issue.related_paths || []).join('、') || '—' }}</span></div>
        </div>
        <div v-if="detail.issue.external_url" style="margin-top: 6px" class="small">
          <a :href="detail.issue.external_url" target="_blank" rel="noopener noreferrer">查看原始单据 ↗</a>
        </div>
      </el-card>

      <div class="grid grid-4" style="margin-bottom: 16px">
        <StatCard label="关联提交" :value="detail.stats?.link_count ?? detail.links.length" />
        <StatCard label="证据充分" :value="detail.stats?.strong_count ?? strongCount" tone="accent" />
        <StatCard label="需人工复核" :value="detail.stats?.review_count ?? reviewCount" tone="warning" />
        <StatCard label="待确认" :value="detail.stats?.pending_count ?? pendingCount" />
      </div>

      <el-tabs v-model="activeTab">
        <!-- 关联提交时间线 -->
        <el-tab-pane label="关联提交时间线" name="links">
          <el-card shadow="never">
            <div v-if="detail.links.length" class="timeline">
              <div v-for="link in detail.links" :key="link.id" class="tl-item">
                <span class="tl-dot" :class="assessmentDot(link.assessment)" />
                <div class="tl-head">
                  <span class="tl-sha">{{ shortSha(link.commit_sha) }}</span>
                  <span class="small">{{ commitMessage(link) }}</span>
                  <span class="badge" :class="assessmentTone(link.assessment)">{{ assessmentLabel(link.assessment) }}</span>
                  <ReviewTag :status="link.review_status" />
                </div>
                <div class="tl-meta">
                  {{ link.link_type || '未标注' }} · 置信度 {{ link.confidence ?? 0 }}
                  · {{ commitAuthor(link) }} · {{ formatTime(commitTime(link)) }}
                </div>
                <div class="tl-body">
                  <div class="tl-row"><span class="tl-label">证据</span>{{ link.evidence || '暂无证据描述' }}</div>
                  <div class="tl-row"><span class="tl-label">结论</span>{{ link.assessment_note || '原因未知（证据不足）' }}</div>
                  <div v-if="link.llm_note" class="tl-row"><span class="tl-label">复核意见</span>{{ link.llm_note }}</div>
                  <div class="tl-row">
                    <span class="tl-label">信号矩阵</span>
                    <div class="signal-grid">
                      <span
                        v-for="signal in linkSignals(link)"
                        :key="signal.key"
                        class="sig"
                        :class="{ hit: signal.hit }"
                      >{{ signal.label }}</span>
                    </div>
                  </div>
                  <div class="flex gap-2" style="margin-top: 10px">
                    <el-button
                      v-if="link.review_status !== 'confirmed'"
                      type="primary"
                      size="small"
                      :loading="busyLink === link.id"
                      @click="review(link.id, true)"
                    >确认关联</el-button>
                    <el-button
                      v-if="link.review_status !== 'rejected'"
                      size="small"
                      :loading="busyLink === link.id"
                      @click="review(link.id, false)"
                    >否决关联</el-button>
                    <span v-if="link.decided_at" class="small faint">复核于 {{ formatTime(link.decided_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
            <EmptyState
              v-else
              title="暂无关联提交"
              description="可执行「重新关联」，或在证据不足时保持原因未知"
            />
          </el-card>
        </el-tab-pane>

        <!-- 四项信号矩阵 -->
        <el-tab-pane label="信号矩阵" name="signals">
          <el-card shadow="never">
            <div class="card-head"><h3>四项信号</h3><span class="small muted">命中信号越多，证据越充分</span></div>
            <el-table :data="signalRows" size="small">
              <el-table-column prop="label" label="信号" width="160" />
              <el-table-column label="命中">
                <template #default="{ row }">
                  <span class="sig" :class="{ hit: row.hit }">{{ row.hit ? '命中' : '未命中' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="count" label="关联提交数" width="130" align="center" />
              <el-table-column prop="key" label="字段" width="160">
                <template #default="{ row }"><span class="mono small faint">{{ row.key }}</span></template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <!-- 证据结论 -->
        <el-tab-pane label="证据结论" name="conclusion">
          <el-card shadow="never">
            <div class="card-head"><h3>证据充分性评估</h3></div>
            <p class="small muted">
              系统不输出「已修复 / 未修复」这类运行时判断，只评估现有证据是否足以支撑结论。
            </p>
            <div class="grid grid-3">
              <div class="evolution">
                <span class="lbl">证据充分</span>{{ detail.stats?.strong_count ?? strongCount }} 条关联
              </div>
              <div class="evolution">
                <span class="lbl">证据较弱</span>{{ detail.stats?.weak_count ?? weakCount }} 条关联
              </div>
              <div class="evolution">
                <span class="lbl">需人工复核</span>{{ detail.stats?.review_count ?? reviewCount }} 条关联
              </div>
            </div>
            <div v-if="!detail.links.length" class="empty-hint">
              当前证据不足：原因未知（证据不足）。可补充相关路径或重新关联后再评估。
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-card v-else-if="!loading" shadow="never">
      <EmptyState title="未找到追溯记录" description="需求或缺陷可能已被删除，或 ID 不正确" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import StatCard from '@/components/StatCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import ReviewTag from '@/components/ReviewTag.vue'
import { issuesApi } from '@/api/modules/issues'
import { formatTime, shortSha } from '@/utils/format'
import {
  ASSESSMENT_LABELS,
  SIGNAL_LABELS,
  type Assessment,
  type IssueCommitLink,
  type IssueDetail,
} from '@/types'

const route = useRoute()
const router = useRouter()

const detail = ref<IssueDetail | null>(null)
const loading = ref(false)
const busyLink = ref(0)
const activeTab = ref('links')

const strongCount = computed(
  () => detail.value?.links.filter((link) => link.assessment === 'strong').length || 0,
)
const reviewCount = computed(
  () => detail.value?.links.filter((link) => link.assessment === 'review').length || 0,
)
const weakCount = computed(
  () => detail.value?.links.filter((link) => link.assessment === 'weak').length || 0,
)
const pendingCount = computed(
  () => detail.value?.links.filter((link) => link.review_status === 'pending').length || 0,
)

const signalRows = computed(() =>
  Object.entries(SIGNAL_LABELS).map(([key, label]) => {
    const fromDetail = detail.value?.signals?.[key]
    const count = detail.value?.links.filter((link) => link.signals?.[key]).length || 0
    const hit = Boolean(fromDetail) || count > 0
    return {
      key,
      label,
      hit,
      count: fromDetail !== undefined ? String(fromDetail) : String(count),
    }
  }),
)

function assessmentLabel(assessment?: Assessment | string) {
  return ASSESSMENT_LABELS[assessment as Assessment] || assessment || '待评估'
}
function assessmentTone(assessment?: Assessment | string) {
  if (assessment === 'strong') return 'badge-green'
  if (assessment === 'review') return 'badge-amber'
  return 'badge-red'
}
function assessmentDot(assessment?: Assessment | string) {
  if (assessment === 'strong') return ''
  if (assessment === 'review') return 'mid'
  return 'high'
}
function commitMessage(link: IssueCommitLink) {
  return link.commit?.message || link.message || link.commit?.summary || '关联提交'
}
function commitAuthor(link: IssueCommitLink) {
  return link.commit?.author || link.author || '未知作者'
}
function commitTime(link: IssueCommitLink) {
  return link.commit?.committed_at || link.committed_at
}
function linkSignals(link: IssueCommitLink) {
  return Object.entries(SIGNAL_LABELS).map(([key, label]) => ({
    key,
    label,
    hit: Boolean(link.signals?.[key]),
  }))
}

async function load() {
  loading.value = true
  try {
    detail.value = await issuesApi.getIssueDetail(Number(route.params.id))
  } finally {
    loading.value = false
  }
}

async function review(linkId: number, confirm: boolean) {
  busyLink.value = linkId
  try {
    if (confirm) {
      await issuesApi.confirmLink(linkId)
      ElMessage.success('关联已确认')
    } else {
      await issuesApi.rejectLink(linkId)
      ElMessage.success('关联已否决（不会重建）')
    }
    await load()
  } finally {
    busyLink.value = 0
  }
}

onMounted(load)
</script>
