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
                <div class="tl-meta">{{ event.author || '未知作者' }} · {{ formatTime(event.committed_at) }} · {{ event.branch || '—' }}</div>
                <div class="tl-body">
                  <div class="tl-row"><span class="tl-label">能力变化</span>{{ event.capability_delta || event.summary || '—' }}</div>
                  <div v-if="event.affected_files?.length" class="tl-row">
                    <span class="tl-label">涉及文件</span>
                    <span class="mono small">{{ event.affected_files.join('、') }}</span>
                  </div>
                  <div class="tl-row">
                    <span class="tl-label">动机</span>{{ event.motivation || '原因未知（证据不足）' }}
                  </div>
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

        <el-tab-pane label="文件清单" name="files">
          <el-card shadow="never">
            <el-table v-if="detail.files.length" :data="detail.files" size="small">
              <el-table-column label="文件路径" min-width="260">
                <template #default="{ row }">
                  <router-link :to="{ path: `/files/${row.id}`, query: { repo_id: row.repo_id } }" class="mono accent-text">
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
            </el-table>
            <EmptyState v-else title="暂无文件" description="该模块下尚未归档文件" />
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-card v-else-if="!loading" shadow="never">
      <EmptyState title="未找到模块" description="模块可能已被删除或 ID 不正确" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import EmptyState from '@/components/EmptyState.vue'
import RiskTag from '@/components/RiskTag.vue'
import { modulesApi } from '@/api/modules/modules'
import { formatTime, shortSha } from '@/utils/format'
import type { ModuleDetail } from '@/types'

const route = useRoute()
const router = useRouter()

const detail = ref<ModuleDetail | null>(null)
const loading = ref(false)
const activeTab = ref('timeline')

function statusLabel(status?: string) {
  return { active: '活跃', dormant: '沉寂', new: '新建' }[status || ''] || status || '未知'
}
function statusTone(status?: string) {
  if (status === 'active') return 'badge-green'
  if (status === 'new') return 'badge-blue'
  return 'badge-gray'
}
function riskDot(risk?: string) {
  if (risk === '高') return 'high'
  if (risk === '中') return 'mid'
  return ''
}

onMounted(async () => {
  loading.value = true
  try {
    detail.value = await modulesApi.getModuleDetail(Number(route.params.id))
  } finally {
    loading.value = false
  }
})
</script>
