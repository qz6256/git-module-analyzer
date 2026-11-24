<template>
  <div class="page projects-page">
    <PageHeader title="项目工作台" subtitle="按项目组织仓库、模块、提交与需求缺陷的追溯链">
      <template #actions>
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">
          新建项目
        </el-button>
      </template>
    </PageHeader>

    <div class="filter-bar">
      <el-select v-model="filters.city" clearable placeholder="城市" @change="load">
        <el-option v-for="city in cityOptions" :key="city" :label="city" :value="city" />
      </el-select>
      <el-select v-model="filters.domain" clearable placeholder="业务域" @change="load">
        <el-option v-for="domain in domainOptions" :key="domain" :label="domain" :value="domain" />
      </el-select>
      <el-select v-model="filters.status" clearable placeholder="状态" @change="load">
        <el-option label="规划中" value="planning" />
        <el-option label="进行中" value="active" />
        <el-option label="已归档" value="archived" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        class="filter-grow"
        clearable
        placeholder="搜索项目名称 / 描述"
        :prefix-icon="Search"
        @keyup.enter="load"
      />
      <div class="filter-actions">
        <el-button :icon="Search" @click="load">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </div>

    <div v-loading="loading" class="projects-workbench">
      <template v-if="projects.length">
        <div class="overview-strip">
          <div class="overview-item">
            <span class="ov-label">项目</span>
            <span class="ov-value">{{ projects.length }}</span>
          </div>
          <div class="overview-item">
            <span class="ov-label">模块</span>
            <span class="ov-value">{{ totals.module_count }}</span>
          </div>
          <div class="overview-item">
            <span class="ov-label">文件</span>
            <span class="ov-value">{{ totals.file_count }}</span>
          </div>
          <div class="overview-item">
            <span class="ov-label">提交</span>
            <span class="ov-value">{{ totals.commit_count }}</span>
          </div>
          <div class="overview-item">
            <span class="ov-label">需求 / 缺陷</span>
            <span class="ov-value">{{ totals.issue_count }}</span>
          </div>
          <div class="overview-item" :class="{ 'is-warn': totals.pending_links > 0 }">
            <span class="ov-label">待确认关联</span>
            <span class="ov-value">{{ totals.pending_links }}</span>
          </div>
        </div>

        <div class="project-grid">
          <article
            v-for="project in projects"
            :key="project.id"
            class="project-card"
            tabindex="0"
            @click="openProject(project.id)"
            @keydown.enter="openProject(project.id)"
          >
            <header class="pc-head">
              <div class="pc-title-wrap">
                <h3 class="pc-title">{{ project.name }}</h3>
                <span v-if="project.code" class="pc-code mono">{{ project.code }}</span>
              </div>
              <span class="badge" :class="statusTone(project.status)">
                {{ statusLabel(project.status) }}
              </span>
            </header>

            <div class="pc-meta">
              <span>
                {{ [project.city, project.business_domain, project.department].filter(Boolean).join(' · ') || '未填写分类信息' }}
              </span>
              <span v-if="project.updated_at" class="pc-updated">更新于 {{ formatDate(project.updated_at) }}</span>
            </div>

            <p class="pc-desc">{{ project.description || '暂无项目描述' }}</p>

            <div v-if="project.tags?.length" class="pc-tags">
              <span v-for="tag in project.tags" :key="tag" class="pc-tag">{{ tag }}</span>
            </div>

            <div class="pc-stats">
              <div class="pc-stat">
                <span class="pc-stat-n">{{ project.stats?.module_count ?? 0 }}</span>
                <span class="pc-stat-l">模块</span>
              </div>
              <div class="pc-stat">
                <span class="pc-stat-n">{{ project.stats?.file_count ?? 0 }}</span>
                <span class="pc-stat-l">文件</span>
              </div>
              <div class="pc-stat">
                <span class="pc-stat-n">{{ project.stats?.commit_count ?? 0 }}</span>
                <span class="pc-stat-l">提交</span>
              </div>
              <div class="pc-stat">
                <span class="pc-stat-n">{{ project.stats?.issue_count ?? 0 }}</span>
                <span class="pc-stat-l">需求</span>
              </div>
              <div class="pc-stat" :class="{ 'is-warn': (project.stats?.pending_links ?? 0) > 0 }">
                <span class="pc-stat-n">{{ project.stats?.pending_links ?? 0 }}</span>
                <span class="pc-stat-l">待确认</span>
              </div>
            </div>

            <footer class="pc-foot">
              <span>查看项目追溯链</span>
              <span class="pc-foot-arrow">→</span>
            </footer>
          </article>
        </div>
      </template>

      <EmptyState v-else title="暂无项目" description="调整筛选条件，或新建一个项目">
        <el-button v-if="canCreate" type="primary" @click="openCreate">新建项目</el-button>
      </EmptyState>
    </div>

    <el-dialog v-model="createVisible" title="新建项目" width="560px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="createForm.name" placeholder="例如：支付中台" />
        </el-form-item>
        <div class="grid grid-2">
          <el-form-item label="城市"><el-input v-model="createForm.city" placeholder="例如：深圳" /></el-form-item>
          <el-form-item label="业务域"><el-input v-model="createForm.department" placeholder="例如：交易平台" /></el-form-item>
        </div>
        <el-form-item label="业务领域">
          <el-input v-model="createForm.business_domain" placeholder="例如：支付 / 结算" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="createForm.status" style="width: 100%">
            <el-option label="规划中" value="planning" />
            <el-option label="进行中" value="active" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
        <div class="grid grid-2">
          <el-form-item label="开始日期">
            <el-date-picker v-model="createForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
          <el-form-item label="计划结束">
            <el-date-picker v-model="createForm.planned_end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item label="标签（逗号分隔）">
          <el-input v-model="tagsText" placeholder="核心, 高优" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="项目目标与范围" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { projectsApi } from '@/api/modules/projects'
import { useAuthStore } from '@/stores/auth'
import type { Project, ProjectStatus } from '@/types'

const router = useRouter()
const auth = useAuthStore()

const projects = ref<Project[]>([])
const loading = ref(false)
const filters = reactive({ city: '', domain: '', status: '', keyword: '' })

const cityOptions = computed(() => Array.from(new Set(projects.value.map((p) => p.city).filter(Boolean))) as string[])
const domainOptions = computed(() =>
  Array.from(new Set(projects.value.map((p) => p.business_domain).filter(Boolean))) as string[],
)
const canCreate = computed(() => auth.isAdmin || auth.hasRole('project_owner'))

const totals = computed(() => {
  const result = { module_count: 0, file_count: 0, commit_count: 0, issue_count: 0, pending_links: 0 }
  for (const project of projects.value) {
    result.module_count += project.stats?.module_count ?? 0
    result.file_count += project.stats?.file_count ?? 0
    result.commit_count += project.stats?.commit_count ?? 0
    result.issue_count += project.stats?.issue_count ?? 0
    result.pending_links += project.stats?.pending_links ?? 0
  }
  return result
})

async function load() {
  loading.value = true
  try {
    projects.value = await projectsApi.getProjects({
      city: filters.city || undefined,
      domain: filters.domain || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
    })
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, { city: '', domain: '', status: '', keyword: '' })
  load()
}

function statusLabel(status?: ProjectStatus | string) {
  return { planning: '规划中', active: '进行中', archived: '已归档' }[status || ''] || status || '未知'
}

function statusTone(status?: ProjectStatus | string) {
  if (status === 'active') return 'badge-green'
  if (status === 'planning') return 'badge-blue'
  if (status === 'archived') return 'badge-gray'
  return 'badge-gray'
}

function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function openProject(id: number) {
  router.push({ path: `/projects/${id}` })
}

// ---- 新建项目 ----
const createVisible = ref(false)
const submitting = ref(false)
const createFormRef = ref<FormInstance>()
const tagsText = ref('')
const createForm = reactive({
  name: '',
  city: '',
  department: '',
  business_domain: '',
  status: 'planning' as ProjectStatus,
  start_date: '',
  planned_end_date: '',
  description: '',
})

const createRules: FormRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
}

function openCreate() {
  Object.assign(createForm, {
    name: '',
    city: '',
    department: '',
    business_domain: '',
    status: 'planning' as ProjectStatus,
    start_date: '',
    planned_end_date: '',
    description: '',
  })
  tagsText.value = ''
  createVisible.value = true
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await projectsApi.createProject({
      ...createForm,
      tags: tagsText.value
        .split(/[,，]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    })
    ElMessage.success('项目创建成功')
    createVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>
