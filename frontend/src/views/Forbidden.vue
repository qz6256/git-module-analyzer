<template>
  <div class="page">
    <el-card shadow="never">
      <el-result icon="warning" title="403 · 权限不足" sub-title="当前账号无权访问该页面或执行该操作">
        <template #extra>
          <el-button type="primary" @click="router.push('/projects')">返回工作台</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>
