<template>
  <AuthLayout>
    <div class="login-head">
      <h2>欢迎回来</h2>
      <p>登录以访问代码变更知识库</p>
    </div>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      size="large"
      @keyup.enter="submit"
    >
      <el-form-item label="用户名" prop="username">
        <el-input v-model="form.username" autocomplete="username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          autocomplete="current-password"
          placeholder="请输入密码"
        />
      </el-form-item>
      <el-button
        type="primary"
        class="submit-btn"
        :loading="auth.loading"
        @click="submit"
      >
        登录
      </el-button>
    </el-form>

    <div class="login-foot">
      证据不足时系统只给出「原因未知（证据不足）」，不做运行时判断。
    </div>
  </AuthLayout>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import AuthLayout from '@/layouts/AuthLayout.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' ? redirect : '/projects')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败，请检查用户名或密码')
  }
}
</script>

<style scoped>
.login-head {
  margin-bottom: 24px;
}

.login-head h2 {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: -0.5px;
  margin: 0 0 6px;
}

.login-head p {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 13px;
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
  font-weight: 650;
}

.login-foot {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--color-muted-foreground);
}
</style>
