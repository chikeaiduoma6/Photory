<template>
  <AuthShell>
    <template #title>找回密码</template>
    <template #subtitle>我们将发送验证码到您的邮箱</template>

    <template #body>
      <el-form
        :model="form"
        :rules="rules"
        ref="formRef"
        label-position="top"
        @submit.prevent="onSubmit"
      >
        <el-form-item label="邮箱地址" prop="email">
          <el-input
            v-model="form.email"
            placeholder="请输入注册时的邮箱"
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

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :loading="submitting"
            @click="onSubmit"
          >
            下一步
          </el-button>
        </el-form-item>
      </el-form>

      <div class="back-row">
        <el-icon><ArrowLeft /></el-icon>
        <router-link to="/auth/login" class="back-link">返回登录</router-link>
      </div>
    </template>

    <template #footer>
      
    </template>
  </AuthShell>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Message, ArrowLeft } from '@element-plus/icons-vue'
import AuthShell from '@/components/auth/AuthShell.vue'
import axios from 'axios'

const router = useRouter()

const form = reactive({
  email: '',
  code: '',
})

const formRef = ref<FormInstance>()
const submitting = ref(false)
const codeCountdown = ref(0)
let codeTimer: number | null = null

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
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
    await axios.post('/api/v1/auth/send-reset-code', {
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
      await axios.post('/api/v1/auth/verify-reset-code', {
        email: form.email,
        code: form.code,
      })
      ElMessage.success('验证成功～')
      
      router.push('/auth/login')
    } catch {
      ElMessage.error('验证失败')
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

.submit-btn {
  width: 100%;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 600;
  background: linear-gradient(90deg, #ff7fb0, #ff8ec2);
  border: none;
}

.back-row {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #b37d9b;
}

.back-link {
  color: #ff699d;
  text-decoration: none;
}

.back-link:hover {
  text-decoration: underline;
}
</style>
