<template>
  <div class="auth-page">
    
    <header class="auth-header">
      <div class="brand">
        <div class="brand-icon">
          <span>📷</span>
        </div>
        <div class="brand-text">
          <div class="brand-name">Photory</div>
          <div class="brand-slogan">记录世间每一份美好，让瞬间成为永恒</div>
        </div>
      </div>
    </header>

    
    <main class="auth-main">
      <!-- 左侧粉色大海卡片 -->
      <section class="auth-hero-card">
        <div class="hero-image-wrapper">
          <img :src="heroImage" alt="Photory hero" class="hero-image" />
          <div class="hero-tag hero-tag-top">
            ✨ 捕捉生活中的每个精彩瞬间
          </div>
          <div class="hero-tag hero-tag-bottom">
            💕 让美好和温暖永远留存心间
          </div>
        </div>
      </section>

      <!-- 右侧表单卡片 -->
      <section class="auth-form-card">
        <div class="form-card-inner">
          <h1 class="form-title">
            <slot name="title" />
          </h1>
          <p class="form-subtitle">
            <slot name="subtitle" />
          </p>
          <slot name="body" />
          <div class="form-footer">
            <slot name="footer" />
          </div>
        </div>
      </section>
    </main>

    <!-- 底部 footer -->
    <footer class="auth-footer">
      2025 Designed by hyk 用心记录每一帧~
    </footer>
  </div>
</template>

<script setup lang="ts">
import heroImage from '@/assets/pink_sky.jpg'
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #ffe7f1 0%, #ffd6e8 50%, #ffd1e3 100%);
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui,
    -apple-system, 'Segoe UI', Roboto, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
}


.auth-header {
  padding: 24px 80px 8px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(255, 143, 177, 0.35);
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-weight: 700;
  font-size: 20px;
  color: #d2517f;
}

.brand-slogan {
  font-size: 13px;
  color: #c27d9e;
}


.auth-main {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  column-gap: 40px;
  padding: 12px 80px 40px;
  align-items: center;
}


.auth-hero-card {
  display: flex;
  justify-content: center;
}

.hero-image-wrapper {
  position: relative;
  width: 100%;
  max-width: 760px;
  aspect-ratio: 16 / 10;
  border-radius: 32px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(192, 113, 145, 0.45);
  background: #fff;
}

.hero-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}


.hero-tag {
  position: absolute;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  color: #c25a88;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 24px rgba(204, 126, 153, 0.35);
}

.hero-tag-top {
  top: 18%;
  right: 9%;
}

.hero-tag-bottom {
  left: 8%;
  bottom: 8%;
}


.auth-form-card {
  display: flex;
  justify-content: flex-start;
}

.form-card-inner {
  width: 100%;
  max-width: 420px;
  padding: 40px 40px 32px;
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 50px rgba(196, 107, 143, 0.35);
}

.form-title {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 700;
  color: #d15584;
}

.form-subtitle {
  margin: 0 0 24px;
  font-size: 14px;
  color: #b37d9b;
}

.form-footer {
  margin-top: 18px;
  font-size: 13px;
  color: #b37d9b;
}


.auth-footer {
  text-align: center;
  padding: 8px 0 18px;
  font-size: 13px;
  color: #b67f9e;
}


@media (max-width: 1100px) {
  .auth-main {
    grid-template-columns: minmax(0, 1fr);
    row-gap: 24px;
  }

  .auth-hero-card {
    order: -1;
  }

  .auth-header {
    padding-inline: 24px;
  }

  .auth-main {
    padding-inline: 24px;
  }

  .form-card-inner {
    margin-inline: auto;
  }
}
</style>
