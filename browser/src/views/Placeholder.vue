<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()
const title = computed(() => (route.meta.title as string) || '敬请期待')
</script>

<template>
  <div class="placeholder">
    <h2>{{ title }}</h2>
    <p>该功能即将上线，先去首页看看吧～</p>
    <button @click="router.push('/')">回首页</button>
  </div>
</template>

<style scoped>
.placeholder { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg,#ffeef5,#ffe5f0); color:#4b4b4b; text-align:center; }
button { border:none; border-radius:999px; padding:8px 16px; background:linear-gradient(135deg,#ff8bb3,#ff6fa0); color:#fff; cursor:pointer; }
</style>
