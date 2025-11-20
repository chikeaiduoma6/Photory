<!-- src/views/Login.vue -->
<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1 class="title">Photory · 登录</h1>
      <p class="subtitle">登录后开始管理你的个人图库</p>

      <el-form :model="form" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" class="full-btn" @click="onSubmit">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="footer">
        <span class="hint">还没有账号？</span>
        <el-link type="primary" disabled>（注册功能稍后实现）</el-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'

const form = reactive({
  email: '',
  password: '',
})

const onSubmit = () => {
  if (!form.email || !form.password) {
    ElMessage.error('请填写邮箱和密码')
    return
  }
  // TODO: 后续接入后端 /api/v1/auth/login
  ElMessage.info('登录接口暂未实现，后续阶段再接入后端 API')
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}

.login-card {
  width: 360px;
}

.title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.subtitle {
  margin: 8px 0 24px;
  color: #909399;
  font-size: 14px;
}

.full-btn {
  width: 100%;
}

.footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  font-size: 13px;
  color: #909399;
}
</style>
