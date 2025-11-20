<template>
  <AuthShell>
    <template #title>创建Photory账户</template>
    <template #subtitle>开启您的美好记录之旅</template>

    <template #body>
      <el-form
        :model="form"
        :rules="rules"
        ref="formRef"
        label-position="top"
        @submit.prevent="onSubmit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            clearable
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="邮箱地址" prop="email">
          <el-input
            v-model="form.email"
            placeholder="请输入邮箱"
            size="large"
            clearable
          >
            <template #prefix>
              <el-icon><Message /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="验证码" prop="code">
          <div class="inline-row">
            <el-input
              v-model="form.code"
              placeholder="请输入验证码"
              size="large"
              clearable
            />
            <el-button
              class="code-btn"
              size="large"
              :disabled="codeCountdown > 0"
              @click="onSendCode"
            >
              {{ codeCountdown > 0 ? codeCountdown + 's 后可重发' : '获取验证码' }}
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码（至少6位，包含字母和数字）"
            size="large"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入密码"
            size="large"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :loading="submitting"
            @click="onSubmit"
          >
            立即注册
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      已有账户？
      <router-link to="/auth/login" class="link">立即登录</router-link>
    </template>
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

const form = reactive({
  username: '',
  email: '',
  code: '',
  password: '',
  confirmPassword: '',
})

const formRef = ref<FormInstance>()
const submitting = ref(false)
const codeCountdown = ref(0)
let codeTimer: number | null = null

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
    validator: (_rule, value, callback) => {
      if (!value) {
        return callback(new Error('请输入密码'))
      }

      if (value.length < 6) {
        return callback(new Error('密码至少 6 位'))
      }

      const hasLetter = /[A-Za-z]/.test(value)
      const hasNumber = /\d/.test(value)

      if (!hasLetter || !hasNumber) {
        return callback(new Error('密码需同时包含字母和数字'))
      }

      
      callback()
    },
    trigger: 'blur',
    },
    ],

  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const startCountdown = () => {
  codeCountdown.value = 60
  if (codeTimer) {
    window.clearInterval(codeTimer)
  }
  codeTimer = window.setInterval(() => {
    if (codeCountdown.value <= 1) {
      codeCountdown.value = 0
      if (codeTimer) window.clearInterval(codeTimer)
      codeTimer = null
    } else {
      codeCountdown.value -= 1
    }
  }, 1000)
}

const onSendCode = async () => {
  if (!form.email) {
    ElMessage.warning('请先填写邮箱地址')
    return
  }
  startCountdown()
  try {
    
    await axios.post('/api/v1/auth/send-register-code', {
      email: form.email,
    })
  } catch {
    
  }
  ElMessage.success('验证码已发送')
}

const onSubmit = () => {
  if (!formRef.value) return
  formRef.value.validate(async valid => {
    if (!valid) return
    submitting.value = true
    try {
      
      await axios.post('/api/v1/auth/register', {
        username: form.username,
        email: form.email,
        password: form.password,
        code: form.code,
      })
      ElMessage.success('注册成功，去登录试试吧～')
      router.push('/auth/login')
    } catch {
      ElMessage.error('注册失败')
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.inline-row {
  display: flex;
  gap: 10px;
}

.code-btn {
  white-space: nowrap;
  background: #ffe3ec;
  border-color: #ffc8da;
  color: #d45d8a;
}

.code-btn.is-disabled {
  opacity: 0.8;
}

.submit-btn {
  width: 100%;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 600;
  background: linear-gradient(90deg, #ff7fb0, #ff8ec2);
  border: none;
}

.link {
  color: #ff699d;
  text-decoration: none;
  font-weight: 500;
}

.link:hover {
  text-decoration: underline;
}
</style>
