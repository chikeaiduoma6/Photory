<template>
  <AuthShell>
    <template #title>创建Photory账户</template>
    <template #subtitle>开启您的美好记录之旅</template>

    <template #body>
      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" clearable>
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="邮箱地址" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" size="large" clearable>
            <template #prefix><el-icon><Message /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少6位，含字母和数字" size="large">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入密码" size="large">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" class="submit-btn" :loading="submitting" @click="onSubmit">
            立即注册
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <template #footer>已有账户？<router-link to="/auth/login" class="link">立即登录</router-link></template>
  </AuthShell>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Message, Lock } from '@element-plus/icons-vue'
import AuthShell from '@/components/auth/AuthShell.vue'
import axios from 'axios'

const router = useRouter()
const form = reactive({ username: '', email: '', password: '', confirmPassword: '' })
const formRef = ref<FormInstance>()
const submitting = ref(false)

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (!v) return cb(new Error('请输入密码'))
        if (v.length < 6) return cb(new Error('密码至少 6 位'))
        if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) return cb(new Error('需包含字母和数字'))
        return cb()
      },
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: (_r, v, cb) => (v !== form.password ? cb(new Error('两次输入的密码不一致')) : cb()), trigger: 'blur' },
  ],
}

const onSubmit = () => {
  if (!formRef.value) return
  formRef.value.validate(async valid => {
    if (!valid) return
    submitting.value = true
    try {
      await axios.post('/api/v1/auth/register', form)
      ElMessage.success('注册成功，去登录试试吧～')
      router.push('/auth/login')
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.message || '注册失败')
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.inline-row { display: flex; gap: 10px; }
.code-btn { white-space: nowrap; background: #ffe3ec; border-color: #ffc8da; color: #d45d8a; }
.code-btn.is-disabled { opacity: 0.8; }
.submit-btn { width: 100%; border-radius: 999px; font-size: 15px; font-weight: 600; background: linear-gradient(90deg, #ff7fb0, #ff8ec2); border: none; }
.link { color: #ff699d; text-decoration: none; font-weight: 500; }
.link:hover { text-decoration: underline; }
</style>
