<template>
  <div class="page">
    <PageHeader title="需求与缺陷" subtitle="只登记「为什么要改」，结论只做证据充分性评估">
      <template #actions>
        <el-button :icon="Refresh" :loading="relinking" :disabled="!hasRepo" @click="relink">重新关联</el-button>
        <el-button :icon="Upload" :disabled="!hasRepo" @click="importDialog = true">导入 CSV</el-button>
        <el-button type="primary" :icon="Plus" :disabled="!hasRepo" @click="openCreate">新建</el-button>
      </template>
    </PageHeader>

    <template v-if="hasRepo">
      <div class="filter-bar">
        <el-input v-model="filters.q" class="filter-grow" clearable placeholder="搜索编号 / 标题 / 关键词" :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="filters.issue_type" clearable placeholder="类型" style="width: 120px" @change="load">
          <el-option label="缺陷" value="bug" />
          <el-option label="需求" value="story" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 120px" @change="load">
          <el-option label="处理中" value="open" />
          <el-option label="已关闭" value="closed" />
          <el-option label="已解决" value="resolved" />
        </el-select>
        <el-select v-model="filters.assessment" clearable placeholder="结论" style="width: 140px" @change="load">
          <el-option label="证据充分" value="strong" />
          <el-option label="证据较弱" value="weak" />
          <el-option label="需复核" value="review" />
        </el-select>
        <el-button :icon="Search" @click="load">查询</el-button>
      </div>

      <el-card shadow="never" v-loading="loading">
        <el-table v-if="rows.length" :data="rows" size="small">
          <el-table-column label="编号" width="130">
            <template #default="{ row }"><span class="mono accent-text">{{ row.external_id }}</span></template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <span class="badge" :class="row.issue_type === 'bug' ? 'badge-red' : 'badge-blue'">
                {{ row.issue_type === 'bug' ? '缺陷' : '需求' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="240">
            <template #default="{ row }">
              <router-link :to="{ path: `/issues/${row.id}`, query: { repo_id: row.repo_id } }" class="accent-text">
                {{ row.title || '（无标题）' }}
              </router-link>
              <div class="small faint ellipsis">{{ row.description }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <span class="badge" :class="row.status === 'open' ? 'badge-amber' : 'badge-gray'">
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="100" />
          <el-table-column label="相关路径" min-width="180">
            <template #default="{ row }">
              <span v-for="path in (row.related_paths || []).slice(0, 2)" :key="path" class="badge badge-gray mono">{{ path }}</span>
              <span v-if="(row.related_paths || []).length > 2" class="small faint">+{{ row.related_paths.length - 2 }}</span>
              <span v-if="!row.related_paths?.length" class="faint">—</span>
            </template>
          </el-table-column>
          <el-table-column label="发生时间" width="150">
            <template #default="{ row }"><span class="small muted">{{ formatTime(row.occurred_at) }}</span></template>
          </el-table-column>
        </el-table>
        <EmptyState v-else title="暂无需求或缺陷" description="导入 CSV 或手动新建，再执行关联分析" />
      </el-card>
    </template>

    <el-card v-else shadow="never">
      <EmptyState title="请先选择仓库" description="可在顶栏选择项目与仓库，或使用 ?repo_id= 参数直达">
        <el-button type="primary" @click="router.push('/projects')">前往项目工作台</el-button>
      </EmptyState>
    </el-card>

    <!-- CSV 导入 -->
    <el-dialog v-model="importDialog" title="导入需求 / 缺陷 CSV" width="620px" destroy-on-close>
      <div class="small muted" style="margin-bottom: 10px">
        支持包含 external_id、issue_type、title、description、status、related_paths、keywords 等列的 CSV 文本。
      </div>
      <el-upload :show-file-list="false" :auto-upload="false" accept=".csv,text/csv" @change="onFileChange">
        <el-button size="small" :icon="Upload">选择 CSV 文件</el-button>
      </el-upload>
      <el-input v-model="csvText" type="textarea" :rows="10" placeholder="或直接粘贴 CSV 内容" style="margin-top: 12px" />
      <template #footer>
        <el-button @click="importDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!csvText" @click="submitImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 新建 -->
    <el-dialog v-model="createDialog" title="新建需求 / 缺陷" width="560px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <div class="grid grid-2">
          <el-form-item label="外部编号" prop="external_id">
            <el-input v-model="createForm.external_id" placeholder="例如：BUG-1024" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="createForm.issue_type" style="width: 100%">
              <el-option label="缺陷" value="bug" />
              <el-option label="需求" value="story" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="标题"><el-input v-model="createForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="相关路径（逗号分隔）">
          <el-input v-model="relatedPathsText" placeholder="src/order/, src/pay/" />
        </el-form-item>
        <el-form-item label="关键词（逗号分隔）"><el-input v-model="keywordsText" placeholder="支付, 超时" /></el-form-item>
        <el-form-item label="外部链接"><el-input v-model="createForm.external_url" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadFile } from 'element-plus'
import { Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { issuesApi } from '@/api/modules/issues'
import { useRepoContext } from '@/composables/useRepoContext'
import { formatTime } from '@/utils/format'
import type { Issue } from '@/types'

const router = useRouter()
const { repoId, hasRepo } = useRepoContext()

const rows = ref<Issue[]>([])
const loading = ref(false)
const relinking = ref(false)
const filters = reactive({ q: '', issue_type: '', status: '', assessment: '' })

function statusLabel(status?: string) {
  return { open: '处理中', resolved: '已解决', closed: '已关闭' }[status || ''] || status || '未知'
}

async function load() {
  if (!repoId.value) {
    rows.value = []
    return
  }
  loading.value = true
  try {
    rows.value = await issuesApi.getIssues(repoId.value, {
      q: filters.q || undefined,
      issue_type: filters.issue_type || undefined,
      status: filters.status || undefined,
      assessment: filters.assessment || undefined,
    })
  } finally {
    loading.value = false
  }
}

async function relink() {
  relinking.value = true
  try {
    const result = await issuesApi.relink(repoId.value)
    ElMessage.success(`已关联 ${result.linked || 0} 条，待确认 ${result.pending || 0} 条`)
    await load()
  } finally {
    relinking.value = false
  }
}

// ---- CSV 导入 ----
const importDialog = ref(false)
const csvText = ref('')
const submitting = ref(false)

function onFileChange(file: UploadFile) {
  const reader = new FileReader()
  reader.onload = () => {
    csvText.value = String(reader.result || '')
  }
  if (file.raw) reader.readAsText(file.raw)
}

async function submitImport() {
  submitting.value = true
  try {
    const result = await issuesApi.importIssues(repoId.value, csvText.value)
    ElMessage.success(`导入 ${result.imported || 0} 条，更新 ${result.updated || 0} 条`)
    importDialog.value = false
    csvText.value = ''
    await load()
  } finally {
    submitting.value = false
  }
}

// ---- 新建 ----
const createDialog = ref(false)
const createFormRef = ref<FormInstance>()
const keywordsText = ref('')
const relatedPathsText = ref('')
const createForm = reactive({
  external_id: '',
  issue_type: 'bug',
  title: '',
  description: '',
  external_url: '',
})
const createRules: FormRules = {
  external_id: [{ required: true, message: '请输入外部编号', trigger: 'blur' }],
}

function split(text: string) {
  return text
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function openCreate() {
  Object.assign(createForm, { external_id: '', issue_type: 'bug', title: '', description: '', external_url: '' })
  keywordsText.value = ''
  relatedPathsText.value = ''
  createDialog.value = true
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await issuesApi.createIssue(repoId.value, {
      ...createForm,
      keywords: split(keywordsText.value),
      related_paths: split(relatedPathsText.value),
      source: 'manual',
    })
    ElMessage.success('创建成功')
    createDialog.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

watch(repoId, load)
onMounted(load)
</script>
