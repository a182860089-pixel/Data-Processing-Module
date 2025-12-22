<script setup lang="ts">
import { ref, onMounted } from "vue";
import ImageCompressor from "./components/ImageCompressor.vue";
import ImagesToPdfConverter from "./components/ImagesToPdfConverter.vue";
import PdfConverter from "./components/PdfConverter.vue";
import WechatCrawler from "./components/WechatCrawler.vue";
import ImageToWord from "./components/ImageToWord.vue";

const errorMessage = ref<string>("");
const successMessage = ref<string>("");

// 当前激活的标签
const activeTab = ref<"image" | "images-to-pdf" | "pdf" | "wechat" | "image-to-word">("image");

// 处理错误
const handleError = (message: string) => {
  errorMessage.value = message;
  setTimeout(() => {
    errorMessage.value = "";
  }, 5000);
};

// 处理成功
const handleSuccess = (message: string) => {
  successMessage.value = message;
  setTimeout(() => {
    successMessage.value = "";
  }, 5000);
};
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>🛠 数据处理小工具</h1>
      <p class="subtitle">图片压缩 & PDF 转 Markdown 一站式工具</p>

      <div class="tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'image' }"
          type="button"
          @click="activeTab = 'image'"
        >
          📷 图片压缩
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'images-to-pdf' }"
          type="button"
          @click="activeTab = 'images-to-pdf'"
        >
          🖼️ 多图转 PDF
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'pdf' }"
          type="button"
          @click="activeTab = 'pdf'"
        >
          📄 PDF → Markdown
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'wechat' }"
          type="button"
          @click="activeTab = 'wechat'"
        >
          🔗 微信文章爬取
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'image-to-word' }"
          type="button"
          @click="activeTab = 'image-to-word'"
        >
          📝 图片转Word
        </button>
      </div>
    </header>

    <main class="main">
      <div class="container">
        <!-- 错误提示 -->
        <Transition name="message">
          <div v-if="errorMessage" class="message message-error">❌ {{ errorMessage }}</div>
        </Transition>

        <!-- 成功提示 -->
        <Transition name="message">
          <div v-if="successMessage" class="message message-success">✅ {{ successMessage }}</div>
        </Transition>

        <!-- 图片压缩页面 -->
        <template v-if="activeTab === 'image'">
          <ImageCompressor @error="handleError" />
        </template>

        <!-- 多图转PDF页面 -->
        <template v-else-if="activeTab === 'images-to-pdf'">
          <ImagesToPdfConverter @error="handleError" />
        </template>

        <!-- PDF 转换页面 -->
        <template v-else-if="activeTab === 'pdf'">
          <PdfConverter @error="handleError" />
        </template>

        <!-- 微信文章爬取页面 -->
        <template v-else-if="activeTab === 'wechat'">
          <WechatCrawler />
        </template>

        <!-- 图片转Word页面 -->
        <template v-else-if="activeTab === 'image-to-word'">
          <ImageToWord @error="handleError" />
        </template>
      </div>
    </main>

    <footer class="footer">
      <p>数据处理工具集 · 图片压缩 · 多图合并PDF · PDF转Markdown · 微信文章爬取 · 图片转Word</p>
    </footer>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.header {
  text-align: center;
  padding: 40px 20px 24px;
  color: white;
}

.header h1 {
  margin: 0 0 12px 0;
  font-size: 32px;
  font-weight: 700;
}

.subtitle {
  margin: 0 0 16px 0;
  font-size: 15px;
  opacity: 0.9;
}

.tabs {
  margin-top: 8px;
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.25);
}

.tab-btn {
  border: none;
  background: transparent;
  color: #e5e7eb;
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, transform 0.1s ease;
}

.tab-btn.active {
  background: white;
  color: #111827;
  transform: translateY(-1px);
}

.main {
  flex: 1;
  padding: 20px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #111827;
  font-size: 13px;
}

.status-pill .label {
  opacity: 0.7;
}

.value-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.value-tag.ok {
  background-color: #ecfdf3;
  color: #16a34a;
}

.value-tag.warn {
  background-color: #fffbeb;
  color: #d97706;
}

.value-tag.err {
  background-color: #fef2f2;
  color: #b91c1c;
}

.status-refresh {
  margin-left: auto;
  padding: 6px 12px;
  border-radius: 999px;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: #111827;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.1s ease;
}

.status-refresh:hover {
  background: #ffffff;
  transform: translateY(-1px);
}

.status-error {
  margin: 0 0 10px 0;
  font-size: 12px;
  color: #fee2e2;
}

.message {
  padding: 16px 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 14px;
  font-weight: 500;
  animation: slideDown 0.3s ease;
}

.message-error {
  background-color: #fff1f0;
  border: 1px solid #ffccc7;
  color: #ff4d4f;
}

.message-success {
  background-color: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #52c41a;
}

.footer {
  text-align: center;
  padding: 16px 20px 20px;
  color: white;
  font-size: 13px;
  opacity: 0.9;
}

.footer p {
  margin: 2px 0;
}

/* 过渡动画 */
.message-enter-active,
.message-leave-active {
  transition: all 0.3s ease;
}

.message-enter-from {
  opacity: 0;
  transform: translateY(-20px);
}

.message-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .header h1 {
    font-size: 26px;
  }

  .subtitle {
    font-size: 13px;
  }
}
</style>
