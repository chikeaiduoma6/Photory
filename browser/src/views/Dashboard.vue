<!-- src/views/Dashboard.vue -->
<template>
  <div class="layout">
    <header class="header">
      <div class="logo">Photory</div>
      <div class="actions">
        <el-input
          v-model="keyword"
          placeholder="搜索你的图片..."
          size="small"
          class="search-input"
          clearable
        />
        <el-button type="primary" size="small">
          上传图片
        </el-button>
      </div>
    </header>

    <main class="content">
      <el-empty description="将来的图库首页（后续阶段实现具体功能）" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const keyword = ref('')
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  height: 56px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
  background: #ffffff;
}

.logo {
  font-weight: 600;
  font-size: 20px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-input {
  width: 260px;
}

.content {
  flex: 1;
  padding: 24px;
  background: #f5f7fa;
}
</style>
