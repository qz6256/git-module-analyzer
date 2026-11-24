<template>
  <div class="page">
    <PageHeader title="系统设置" subtitle="LLM 配置、用户与角色、数据库连接状态" />

    <el-tabs v-model="activeTab">
      <!-- LLM 配置 -->
      <el-tab-pane label="LLM 配置" name="llm">
        <el-card shadow="never" v-loading="llmLoading">
          <template #header>
            <div class="card-head">
              <h3>大模型服务</h3>
              <span class="small muted">{{ auth.isAdmin ? '管理员可修改' : '只读：需要管理员权限' }}</span>
            </div>
          </template>
          <el-form :model="llmForm" label-position="top" :disabled="!auth.isAdmin" style="max-width: 720px">
            <el-form-item label="Base URL">
              <el-input v-model="llmForm.base_url" placeholder="https://api.openai.com/v1" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="llmForm.api_key" type="password" show-password placeholder="留空表示保持原值" />
              <div class="small faint">出于安全考虑，接口返回的 Key 已脱敏；留空即不更新。</div>
            </el-form-item>
            <div class="grid grid-2">
              <el-form-item label="模型">
                <el-input v-model="llmForm.model" placeholder="gpt-4o-mini" />
              </el-form-item>
              <el-form-item label="单次最大 Diff 字符数">
                <el-input-number v-model="llmForm.max_diff_chars" :min="1000" :max="100000" :step="1000" style="width: 100%" />
              </el-form-item>
            </div>
            <el-form-item label="提交 Web 地址模板">
              <el-input v-model="llmForm.commit_web_base_url" placeholder="可选，用于生成提交链接" />
            </el-form-item>
            <el-form-item label="启用 LLM 分析">
              <el-switch v-model="llmForm.llm_enabled" />
            </el-form-item>
          </el-form>
          <div class="flex gap-2">
            <el-button v-if="auth.isAdmin" type="primary" :loading="savingLlm" @click="saveLlm">保存配置</el-button>
            <el-button :loading="testingLlm" @click="testLlm">测试连接</el-button>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <el-card shadow="never" v-loading="usersLoading">
          <template #header>
            <div class="card-head">
              <h3>用户与角色</h3>
              <span class="small muted">{{ users.length }} 个用户</span>
            </div>
          </template>
          <template v-if="auth.isAdmin">
            <el-table v-if="users.length" :data="users" size="small">
              <el-table-column label="用户" min-width="180">
                <template #default="{ row }">
                  <div>{{ row.display_name || row.username }}</div>
                  <div class="small faint">@{{ row.username }} · {{ row.email }}</div>
                </template>
              </el-table-column>
              <el-table-column label="Git 身份" min-width="180">
                <template #default="{ row }">
                  <template v-if="row.git_identity">
                    <div>{{ row.git_identity.name }}</div>
                    <div class="small faint">{{ row.git_identity.email || '（无邮箱）' }}</div>
                  </template>
                  <span v-else class="faint">未绑定</span>
                </template>
              </el-table-column>
              <el-table-column label="角色" min-width="220">
                <template #default="{ row }">
                  <span v-for="role in row.roles || []" :key="role.code" class="badge badge-blue" style="margin-right: 4px">
                    {{ role.code }}
                  </span>
                  <span v-if="row.is_superuser" class="badge badge-green">superuser</span>
                  <span v-if="!row.roles?.length && !row.is_superuser" class="faint">—</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <span class="badge" :class="row.status === 'active' ? 'badge-green' : 'badge-red'">
                    {{ row.status === 'active' ? '启用' : '禁用' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="最近登录" width="160">
                <template #default="{ row }"><span class="small muted">{{ formatTime(row.last_login_at) }}</span></template>
              </el-table-column>
              <el-table-column label="操作" width="300" align="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openRoles(row)">编辑角色</el-button>
                  <el-button link type="primary" size="small" @click="openGit(row)">绑定 Git</el-button>
                  <el-button link size="small" @click="router.push(`/users/${row.id}/commits`)">查看提交</el-button>
                  <el-button
                    link
                    size="small"
                    :type="row.status === 'active' ? 'danger' : 'primary'"
                    @click="toggleStatus(row)"
                  >{{ row.status === 'active' ? '禁用' : '启用' }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <EmptyState v-else title="暂无用户" description="可通过注册接口添加用户" />
          </template>
          <el-result v-else icon="warning" title="需要管理员权限" sub-title="用户管理仅对 admin 角色开放" />
        </el-card>
      </el-tab-pane>

      <!-- 数据库 -->
      <el-tab-pane label="数据库连接" name="database">
        <div class="grid grid-2">
          <el-card shadow="never" v-loading="dbLoading">
            <template #header><div class="card-head"><h3>连接状态</h3></div></template>
            <div class="kv"><span class="k">方言</span><span>{{ database?.dialect || '—' }}</span></div>
            <div class="kv">
              <span class="k">连接</span>
              <span>
                <span v-if="database" class="badge" :class="database.connected ? 'badge-green' : 'badge-red'">
                  {{ database.connected ? '已连接' : '连接失败' }}
                </span>
                <span v-else class="faint">—</span>
              </span>
            </div>
            <div class="kv"><span class="k">服务状态</span><span>{{ health?.status || '—' }}</span></div>
            <div class="kv"><span class="k">版本</span><span class="mono">{{ health?.version || '—' }}</span></div>
          </el-card>

          <el-card shadow="never">
            <template #header>
              <div class="card-head">
                <h3>数据表</h3>
                <span class="small muted">{{ database?.tables?.length || 0 }} 张</span>
              </div>
            </template>
            <div v-if="database?.tables?.length" class="flex flex-wrap gap-2">
              <span v-for="table in database.tables" :key="table" class="badge badge-gray mono">{{ table }}</span>
            </div>
            <EmptyState v-else title="暂无表信息" description="数据库连接正常后将列出数据表" />
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 编辑角色 -->
    <el-dialog v-model="rolesDialog" title="编辑用户角色" width="420px" destroy-on-close>
      <div class="small muted" style="margin-bottom: 12px">
        目标用户：<strong>{{ editingUser?.display_name || editingUser?.username }}</strong>
      </div>
      <el-checkbox-group v-model="selectedRoles">
        <el-checkbox value="admin">admin</el-checkbox>
        <el-checkbox value="project_owner">project_owner</el-checkbox>
        <el-checkbox value="developer">developer</el-checkbox>
        <el-checkbox value="viewer">viewer</el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="rolesDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingRoles" @click="saveRoles">保存</el-button>
      </template>
    </el-dialog>

    <!-- 绑定 Git 身份 -->
    <el-dialog v-model="gitDialog" title="绑定 Git 身份" width="560px" destroy-on-close>
      <div class="small muted" style="margin-bottom: 12px">
        目标用户：<strong>{{ gitUser?.display_name || gitUser?.username }}</strong>
        <span v-if="gitUser?.git_identity" class="badge badge-green" style="margin-left: 6px">
          当前：{{ gitUser.git_identity.name }}
        </span>
      </div>
      <el-form label-position="top">
        <el-form-item label="选择已发现的 Git 用户（来自提交作者）">
          <el-select v-model="selectedIdentity" clearable filterable style="width: 100%" placeholder="可留空">
            <el-option
              v-for="item in identities"
              :key="item.id"
              :label="`${item.name}${item.email ? ' <' + item.email + '>' : ''}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <div class="small faint" style="margin: -6px 0 12px">或手动输入一个新的 Git 身份：</div>
        <div class="grid grid-2">
          <el-form-item label="Git 用户名"><el-input v-model="manualName" placeholder="提交里的 author 名" /></el-form-item>
          <el-form-item label="Git 邮箱"><el-input v-model="manualEmail" placeholder="author 邮箱（可选）" /></el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="gitDialog = false">取消</el-button>
        <el-button :loading="savingGit" @click="unbindGit" :disabled="!gitUser?.git_identity">解绑当前</el-button>
        <el-button type="primary" :loading="savingGit" @click="saveGit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { settingsApi } from '@/api/modules/settings'
import { usersApi } from '@/api/modules/users'
import { gitIdentitiesApi } from '@/api/modules/gitIdentities'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'
import type { DatabaseStatus, GitIdentity, HealthStatus, LlmConfig, User } from '@/types'

const auth = useAuthStore()
const router = useRouter()
const activeTab = ref('llm')

// ---- LLM ----
const llmLoading = ref(false)
const savingLlm = ref(false)
const testingLlm = ref(false)
const llmForm = reactive<LlmConfig>({
  base_url: '',
  api_key: '',
  model: '',
  max_diff_chars: 12000,
  commit_web_base_url: '',
  llm_enabled: true,
})

async function loadLlm() {
  llmLoading.value = true
  try {
    const config = await settingsApi.getLlmConfig()
    Object.assign(llmForm, config)
  } finally {
    llmLoading.value = false
  }
}

async function saveLlm() {
  savingLlm.value = true
  try {
    await settingsApi.updateLlmConfig({
      base_url: llmForm.base_url,
      api_key: llmForm.api_key,
      model: llmForm.model,
      max_diff_chars: llmForm.max_diff_chars,
      commit_web_base_url: llmForm.commit_web_base_url,
      llm_enabled: llmForm.llm_enabled,
    })
    ElMessage.success('配置已保存')
    await loadLlm()
  } finally {
    savingLlm.value = false
  }
}

async function testLlm() {
  testingLlm.value = true
  try {
    const result = await settingsApi.testLlm()
    if (result.ok) ElMessage.success(result.message || '连接正常')
    else ElMessage.warning(result.message || '连接测试未通过')
  } finally {
    testingLlm.value = false
  }
}

// ---- 用户 ----
const usersLoading = ref(false)
const users = ref<User[]>([])
const rolesDialog = ref(false)
const editingUser = ref<User | null>(null)
const selectedRoles = ref<string[]>([])
const savingRoles = ref(false)

async function loadUsers() {
  if (!auth.isAdmin) return
  usersLoading.value = true
  try {
    users.value = await usersApi.getUsers()
  } finally {
    usersLoading.value = false
  }
}

function openRoles(user: User) {
  editingUser.value = user
  selectedRoles.value = (user.roles || []).map((role) => role.code)
  rolesDialog.value = true
}

async function saveRoles() {
  if (!editingUser.value) return
  savingRoles.value = true
  try {
    await usersApi.setUserRoles(editingUser.value.id, selectedRoles.value)
    ElMessage.success('角色已更新')
    rolesDialog.value = false
    await loadUsers()
  } finally {
    savingRoles.value = false
  }
}

async function toggleStatus(user: User) {
  const next = user.status === 'active' ? 'disabled' : 'active'
  await usersApi.updateUser(user.id, { status: next })
  ElMessage.success(next === 'active' ? '用户已启用' : '用户已禁用')
  await loadUsers()
}

// ---- Git 身份绑定 ----
const gitDialog = ref(false)
const gitUser = ref<User | null>(null)
const identities = ref<GitIdentity[]>([])
const selectedIdentity = ref<number | null>(null)
const manualName = ref('')
const manualEmail = ref('')
const savingGit = ref(false)

async function openGit(user: User) {
  gitUser.value = user
  selectedIdentity.value = user.git_identity?.id ?? null
  manualName.value = ''
  manualEmail.value = ''
  try {
    identities.value = (await gitIdentitiesApi.list()).items
  } catch {
    identities.value = []
  }
  gitDialog.value = true
}

async function saveGit() {
  if (!gitUser.value) return
  savingGit.value = true
  try {
    // 先解绑该用户当前身份，避免一对一冲突
    if (gitUser.value.git_identity) {
      await gitIdentitiesApi.bind(gitUser.value.git_identity.id, null)
    }
    if (manualName.value.trim()) {
      const created = await gitIdentitiesApi.createManual({
        name: manualName.value.trim(),
        email: manualEmail.value.trim(),
        user_id: gitUser.value.id,
      })
      await gitIdentitiesApi.bind(created.id, gitUser.value.id)
    } else if (selectedIdentity.value) {
      await gitIdentitiesApi.bind(selectedIdentity.value, gitUser.value.id)
    }
    ElMessage.success('Git 身份已绑定')
    gitDialog.value = false
    await loadUsers()
  } finally {
    savingGit.value = false
  }
}

async function unbindGit() {
  if (!gitUser.value?.git_identity) return
  savingGit.value = true
  try {
    await gitIdentitiesApi.bind(gitUser.value.git_identity.id, null)
    ElMessage.success('已解绑 Git 身份')
    gitDialog.value = false
    await loadUsers()
  } finally {
    savingGit.value = false
  }
}

// ---- 数据库 ----
const dbLoading = ref(false)
const database = ref<DatabaseStatus | null>(null)
const health = ref<HealthStatus | null>(null)

async function loadDatabase() {
  dbLoading.value = true
  try {
    const [dbStatus, healthStatus] = await Promise.all([
      settingsApi.getDatabaseStatus(),
      settingsApi.getHealth(),
    ])
    database.value = dbStatus
    health.value = healthStatus
  } finally {
    dbLoading.value = false
  }
}

onMounted(() => {
  loadLlm()
  loadUsers()
  loadDatabase()
})
</script>
