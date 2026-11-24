<template>
  <div class="page">
    <PageHeader :title="pageTitle" subtitle="按该用户绑定的 Git 身份（姓名 / 邮箱）检索全部提交">
      <template #actions>
        <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" v-loading="loading">
      <div class="filter-bar">
        <el-input
          v-model="q"
          class="filter-grow"
          clearable
          placeholder="搜索 SHA / 提交信息"
          :prefix-icon="Search"
          @keyup.enter="load(1)"
        />
        <el-button :icon="Search" @click="load(1)">查询</el-button>
      </div>

      <el-table v-if="rows.length" :data="rows" size="small">
        <el-table-column label="提交" width="120">
          <template #default="{ row }"><span class="tl-sha">{{ row.sha_short }}</span></template>
        </el-table-column>
        <el-table-column label="提交信息" min-width="260">
          <template #default="{ row }">
            <span class="small">{{ row.message || row.summary || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="作者" width="160">
          <template #default="{ row }">
            <div class="small">{{ row.author || '未知' }}</div>
            <div class="x-small faint">{{ row.author_email || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="仓库 ID" width="90">
          <template #default="{ row }"><span class="small muted">#{{ row.repo_id }}</span></template>
        </el-table-column>
        <el-table-column label="分支" width="120">
          <template #default="{ row }"><span class="badge badge-gray mono">{{ row.branch || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }"><span class="small muted">{{ formatTime(row.committed_at) }}</span></template>
        </el-table-column>
      </el-table>
      <EmptyState v-else title="暂无提交" description="该用户尚未绑定 Git 身份，或没有匹配的提交记录" />

      <div v-if="total > size" class="pager">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="size"
          :current-page="page"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { gitIdentitiesApi, type UserCommitPage } from '@/api/modules/gitIdentities'
import { usersApi } from '@/api/modules/users'
import { formatTime } from '@/utils/format'
import type { User } from '@/types'

const route = useRoute()
const router = useRouter()
const userId = Number(route.params.id)

const user = ref<User | null>(null)
const pageTitle = computed(() => `${user.value?.display_name || user.value?.username || '用户'}的提交`)
const loading = ref(false)
const q = ref('')
const page = ref(1)
const size = 30
const total = ref(0)
const rows = ref<UserCommitPage['items']>([])

async function load(p = 1) {
  page.value = p
  loading.value = true
  try {
    const res = await gitIdentitiesApi.userCommits(userId, q.value, page.value, size)
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const all = await usersApi.getUsers()
    user.value = all.find((u) => u.id === userId) || null
  } catch {
    // 非管理员无法列用户，标题退回默认
  }
  await load(1)
})
</script>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
