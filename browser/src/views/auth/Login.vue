<template>
  <AuthShell>
    <template #title>欢迎回来</template>
    <template #subtitle>登录您的 Photory 账户</template>

    <template #body>
      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="邮箱或用户名" prop="identifier">
          <el-input v-model="form.identifier" placeholder="请输入邮箱或用户名" size="large" clearable>
            <template #prefix><el-icon><Message /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" size="large">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item style="margin-top: 16px">
          <el-button type="primary" size="large" class="submit-btn" :loading="submitting" @click="onSubmit">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      还没有账号？
      <router-link to="/auth/register" class="link">立即注册</router-link>
    </template>
  </AuthShell>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Message, Lock } from '@element-plus/icons-vue'
import axios from 'axios'
import AuthShell from '@/components/auth/AuthShell.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({ identifier: '', password: '' })
const formRef = ref<FormInstance>()
const submitting = ref(false)

const rules: FormRules = {
  identifier: [{ required: true, message: '请输入邮箱或用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const onSubmit = () => {
  if (!formRef.value) return
  formRef.value.validate(async valid => {
    if (!valid) return
    submitting.value = true
    try {
      const res = await axios.post('/api/v1/auth/login', {
        identifier: form.identifier,
        password: form.password,
      })
      authStore.setAuth(res.data.access_token, res.data.user)
      ElMessage.success('登录成功')
      router.push('/')
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.message || '登录失败')
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.submit-btn { width: 100%; border-radius: 999px; font-size: 15px; font-weight: 600; background: linear-gradient(90deg, #ff7fb0, #ff8ec2); border: none; }
.link { color: #ff699d; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
