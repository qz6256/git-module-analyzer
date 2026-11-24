<template>
  <div class="page" v-loading="loading">
    <div class="flex items-center gap-3" style="margin-bottom: 14px">
      <el-button text :icon="ArrowLeft" @click="router.push('/files')">返回</el-button>
      <h1 class="page-title">文件档案</h1>
    </div>

    <template v-if="detail">
      <el-card shadow="never" style="margin-bottom: 16px">
        <div class="hero-path">{{ detail.file.path }}</div>
        <div class="hero-oneliner">{{ detail.file.one_liner || '暂无一句话说明' }}</div>
        <div class="flex gap-2 flex-wrap" style="margin-top: 10px">
          <span v-if="detail.file.module_name" class="badge badge-blue">{{ detail.file.module_name }}</span>
          <span v-if="detail.file.language" class="badge badge-gray">{{ detail.file.language }}</span>
          <RiskTag :risk="detail.file.risk_level" />
          <span class="badge badge-gray mono">{{ shortSha(detail.file.last_commit_sha) }}</span>
        </div>
        <div v-if="detail.file.evolution_line" class="evolution" style="margin-top: 14px">
          <span class="lbl">演进主线</span>
          {{ detail.file.evolution_line }}
        </div>
      </el-card>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="当前态文档" name="doc">
          <el-card shadow="never">
            <div class="card-head">
              <h3>当前态说明</h3>
              <span class="small muted">持续维护，而非按提交罗列</span>
            </div>
            <div v-if="docText" class="md-body doc-text">{{ docText }}</div>
            <div v-else-if="detail.file.current_doc" class="md-body doc-text">{{ detail.file.current_doc }}</div>
            <EmptyState v-else title="暂无文档" description="分析引擎尚未生成该文件档案" />
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="变更时间线" name="timeline">
          <el-card shadow="never">
            <div v-if="detail.timeline.length" class="timeline">
              <div v-for="event in detail.timeline" :key="event.id" class="tl-item">
                <span class="tl-dot" :class="riskDot(event.risk_level)" />
                <div class="tl-head">
                  <span class="tl-sha">{{ shortSha(event.commit_sha) }}</span>
                  <span class="small">{{ event.commit_message || event.summary || '文件变更' }}</span>
                  <RiskTag :risk="event.risk_level" />
                </div>
                <div class="tl-meta">{{ event.author || '未知作者' }} · {{ formatTime(event.committed_at) }} · {{ event.branch || '—' }}</div>
                <div class="tl-body">
                  <div class="tl-row"><span class="tl-label">摘要</span>{{ event.summary || '—' }}</div>
                  <div v-if="event.blocks?.length" class="blocks">
                    <div v-for="(block, index) in event.blocks" :key="index" class="block">
                      <span class="bn">{{ block.name || '代码块' }}</span>
                      <span class="badge badge-gray">{{ block.change_type || 'modified' }}</span>
                      <span class="bd">{{ block.description || '无描述' }}</span>
                    </div>
                  </div>
                  <div v-if="event.doc_update" class="tl-row"><span class="tl-label">文档更新</span>{{ event.doc_update }}</div>
                  <div class="tl-row"><span class="tl-label">动机</span>{{ event.motivation || '原因未知（证据不足）' }}</div>
                  <div class="tl-row">
                    <span class="tl-label">证据来源</span>{{ event.evidence_source || '未知' }}
                    <span v-if="event.diff_stats?.additions !== undefined" class="tl-meta">
                      &nbsp; +{{ event.diff_stats.additions }} / -{{ event.diff_stats.deletions ?? 0 }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <EmptyState v-else title="暂无变更时间线" description="同步提交后生成文件级变更节点" />
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-card v-else-if="!loading" shadow="never">
      <EmptyState title="未找到文件" description="文件可能已被删除或 ID 不正确" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import EmptyState from '@/components/EmptyState.vue'
import RiskTag from '@/components/RiskTag.vue'
import { filesApi } from '@/api/modules/files'
import { formatTime, shortSha } from '@/utils/format'
import type { FileDetail } from '@/types'

const route = useRoute()
const router = useRouter()

const detail = ref<FileDetail | null>(null)
const docText = ref('')
const loading = ref(false)
const activeTab = ref('doc')

function riskDot(risk?: string) {
  if (risk === '高') return 'high'
  if (risk === '中') return 'mid'
  return ''
}

onMounted(async () => {
  loading.value = true
  const id = Number(route.params.id)
  try {
    detail.value = await filesApi.getFileDetail(id, {
      branch: (route.query.branch as string) || undefined,
      risk: (route.query.risk as string) || undefined,
      author: (route.query.author as string) || undefined,
    })
  } finally {
    loading.value = false
  }
  try {
    docText.value = await filesApi.getFileDoc(id)
  } catch {
    docText.value = ''
  }
})
</script>

<style scoped>
.doc-text {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.8;
}
</style>
