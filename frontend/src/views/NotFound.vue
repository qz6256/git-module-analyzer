<template>
  <div class="auth-shell-notfound">
    <el-result icon="info" title="404 · 页面不存在" sub-title="链接可能已失效，或页面已被移动">
      <template #extra>
        <el-button type="primary" @click="router.push('/projects')">返回工作台</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.auth-shell-notfound {
  min-height: 100vh;
  display: grid;
  place-items: center;
}
</style>
