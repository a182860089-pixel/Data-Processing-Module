<script setup lang="ts">
import { ref } from "vue";
import ImageCompressor from "./components/ImageCompressor.vue";
import ImagesToPdfConverter from "./components/ImagesToPdfConverter.vue";
import PdfConverter from "./components/PdfConverter.vue";
import MultiFormatToMarkdown from "./components/MultiFormatToMarkdown.vue";
import VideoUploader from "./components/VideoUploader.vue";
import WechatCrawler from "./components/WechatCrawler.vue";
import ImageToWord from "./components/ImageToWord.vue";
import SystemConfig from "./components/SystemConfig.vue";

const errorMessage = ref<string>("");
const successMessage = ref<string>("");

// 当前激活的标签
const activeTab = ref<
  "image" |
  "images-to-pdf" |
  "pdf" |
  "video-to-md" |
  "multi-format-md" |
  "wechat" |
  "image-to-word" |
  "system-config"
>("image");

// 导航菜单配置
const menuItems = [
  { id: 'image', label: '图片压缩', icon: '📷' },
  { id: 'images-to-pdf', label: '多图转 PDF', icon: '🖼️' },
  { id: 'pdf', label: 'PDF 转 Markdown', icon: '📄' },
  { id: 'video-to-md', label: '视频转 MD', icon: '🎬' },
  { id: 'multi-format-md', label: '多格式转 MD', icon: '🧩' },
  { id: 'wechat', label: '微信文章爬取', icon: '🔗' },
  { id: 'image-to-word', label: '图片转 Word', icon: '📝' },
  { id: 'system-config', label: '系统配置', icon: '⚙️' },
] as const;

const handleError = (message: string) => {
  errorMessage.value = message;
  setTimeout(() => {
    errorMessage.value = "";
  }, 5000);
};

const handleSuccess = (message: string) => {
  successMessage.value = message;
  setTimeout(() => {
    successMessage.value = "";
  }, 5000);
};
</script>

<template>
  <div class="app-container">
    <!-- Sidebar Navigation -->
    <aside class="sidebar">
      <div class="logo-area">
        <div class="logo-icon">🛠</div>
        <h1 class="logo-text">数据工具集</h1>
      </div>
      
      <nav class="nav-menu">
        <button
          v-for="item in menuItems"
          :key="item.id"
          class="nav-item"
          :class="{ active: activeTab === item.id }"
          @click="activeTab = item.id"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <p>Version 2.0</p>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="main-content">
      <!-- Top Message Bar -->
      <div class="message-container">
        <Transition name="fade">
          <div v-if="errorMessage" class="alert error">
            ❌ {{ errorMessage }}
          </div>
        </Transition>
        <Transition name="fade">
          <div v-if="successMessage" class="alert success">
            ✅ {{ successMessage }}
          </div>
        </Transition>
      </div>

      <!-- Content Views -->
      <div class="content-wrapper">
        <Transition name="fade-slide" mode="out-in">
          <KeepAlive>
            <component 
              :is="
                activeTab === 'image' ? ImageCompressor :
                activeTab === 'images-to-pdf' ? ImagesToPdfConverter :
                activeTab === 'pdf' ? PdfConverter :
                activeTab === 'video-to-md' ? VideoUploader :
                activeTab === 'multi-format-md' ? MultiFormatToMarkdown :
                activeTab === 'wechat' ? WechatCrawler :
                activeTab === 'image-to-word' ? ImageToWord :
                SystemConfig
              "
              @error="handleError"
              @success="handleSuccess"
            />
          </KeepAlive>
        </Transition>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
  background-color: var(--slate-100);
  font-family: var(--font-sans);
}

/* Sidebar Styling */
.sidebar {
  width: 260px;
  background-color: white;
  border-right: 1px solid var(--slate-200);
  display: flex;
  flex-direction: column;
  position: fixed;
  height: 100vh;
  left: 0;
  top: 0;
  z-index: 10;
}

.logo-area {
  padding: 32px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: var(--primary-500);
  color: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--slate-800);
  margin: 0;
}

.nav-menu {
  flex: 1;
  padding: 0 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: var(--slate-600);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.nav-item:hover {
  background-color: var(--slate-50);
  color: var(--slate-900);
}

.nav-item.active {
  background-color: var(--primary-50);
  color: var(--primary-600);
}

.nav-item.active .nav-icon {
  transform: scale(1.1);
}

.nav-icon {
  font-size: 18px;
  transition: transform 0.2s;
}

.sidebar-footer {
  padding: 24px;
  border-top: 1px solid var(--slate-100);
  color: var(--slate-400);
  font-size: 12px;
  text-align: center;
}

/* Main Content Styling */
.main-content {
  flex: 1;
  margin-left: 260px; /* Width of sidebar */
  padding: 32px 48px;
  max-width: 1400px; /* Prevent too wide on large screens */
}

/* Alerts */
.message-container {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none; /* Let clicks pass through */
}

.alert {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  pointer-events: auto;
  min-width: 300px;
}

.alert.error {
  background-color: #fef2f2;
  color: #ef4444;
  border: 1px solid #fee2e2;
}

.alert.success {
  background-color: #f0fdf4;
  color: #22c55e;
  border: 1px solid #dcfce7;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@media (max-width: 768px) {
  .sidebar {
    width: 64px;
  }
  .nav-label, .logo-text, .sidebar-footer {
    display: none;
  }
  .main-content {
    margin-left: 64px;
    padding: 20px;
  }
  .logo-area {
    padding: 24px 12px;
    justify-content: center;
  }
  .nav-item {
    justify-content: center;
    padding: 12px;
  }
}
</style>
