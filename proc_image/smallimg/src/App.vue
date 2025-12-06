<script setup lang="ts">
import { ref, watch, onUnmounted, onMounted } from "vue";
import ImageUploader from "./components/ImageUploader.vue";
import ProcessingList from "./components/ProcessingList.vue";
import ImagePreview from "./components/ImagePreview.vue";
import PdfUploader from "./components/PdfUploader.vue";
import { useImageProcess } from "./composables/useImageProcess";
import { generateId } from "./utils/image-utils";
import type { ImageItem } from "./types";

const { processImage, cleanup, progress } = useImageProcess();

const items = ref<ImageItem[]>([]);
const previewItem = ref<ImageItem | null>(null);
const errorMessage = ref<string>("");
const successMessage = ref<string>("");

// 当前激活的标签：image = 图片压缩，pdf = PDF 转 Markdown
const activeTab = ref<"image" | "pdf">("image");

// 后端服务状态（阶段1验收）
const API_BASE_URL =
  (import.meta as any).env?.VITE_PDF_API_BASE_URL ||
  (import.meta as any).env?.VITE_IMAGE_API_BASE_URL ||
  "http://localhost:8000";

const healthStatus = ref<string>("未知");
const imageServiceStatus = ref<string>("未知");
const batchServiceStatus = ref<string>("未知");
const statusError = ref<string>("");

const fetchServiceStatus = async () => {
  try {
    statusError.value = "";

    const [healthResp, imageResp, batchResp] = await Promise.all([
      fetch(`${API_BASE_URL}/api/v1/health`),
      fetch(`${API_BASE_URL}/api/v1/image/status`),
      fetch(`${API_BASE_URL}/api/v1/batch/status`),
    ]);

    if (healthResp.ok) {
      const data = await healthResp.json();
      healthStatus.value = data.status || "unknown";
    } else {
      healthStatus.value = `错误 ${healthResp.status}`;
    }

    if (imageResp.ok) {
      const data = await imageResp.json();
      imageServiceStatus.value = data.status || "unknown";
    } else {
      imageServiceStatus.value = `错误 ${imageResp.status}`;
    }

    if (batchResp.ok) {
      const data = await batchResp.json();
      batchServiceStatus.value = data.status || "unknown";
    } else {
      batchServiceStatus.value = `错误 ${batchResp.status}`;
    }
  } catch (e) {
    statusError.value =
      e instanceof Error ? `无法获取服务状态: ${e.message}` : "无法获取服务状态";
  }
};

onMounted(() => {
  fetchServiceStatus();
});

// 处理上传
const handleUpload = async (files: File[]) => {
  errorMessage.value = "";
  successMessage.value = "";

  // 创建图片项
  const newItems: ImageItem[] = files.map((file) => ({
    id: generateId(),
    file,
    status: "pending" as const,
    progress: 0,
  }));

  items.value.push(...newItems);

  // 逐个处理图片
  for (const item of newItems) {
    // 将 composable 的进度绑定到当前条目
    const stopWatch = watch(progress, (val) => {
      try {
        console.debug("[App] progress", val);
      } catch {}
      item.progress = Math.max(0, Math.min(100, Math.floor(val)));
    });

    try {
      item.status = "processing";
      const result = await processImage(item.file);
      item.result = result;
      item.status = "completed";
      item.progress = 100;
      try {
        console.debug("[App] item completed", item.id);
      } catch {}
    } catch (error) {
      item.status = "failed";
      item.error = error instanceof Error ? error.message : "处理失败";
    } finally {
      // 解绑当前条目的进度监听
      stopWatch();
    }
  }

  // 显示成功消息
  const successCount = newItems.filter((item) => item.status === "completed").length;
  if (successCount > 0) {
    successMessage.value = `成功处理 ${successCount} 张图片`;
    setTimeout(() => {
      successMessage.value = "";
    }, 3000);
  }
};

// 处理错误
const handleError = (message: string) => {
  errorMessage.value = message;
  setTimeout(() => {
    errorMessage.value = "";
  }, 5000);
};

// 移除项
const handleRemove = (id: string) => {
  const index = items.value.findIndex((item) => item.id === id);
  if (index !== -1) {
    const item = items.value[index];
    // 清理URL
    if (item.result?.url) {
      URL.revokeObjectURL(item.result.url);
    }
    items.value.splice(index, 1);
  }
};

// 预览
const handlePreview = (item: ImageItem) => {
  previewItem.value = item;
};

// 关闭预览
const handleClosePreview = () => {
  previewItem.value = null;
};

// 清理资源
onUnmounted(() => {
  cleanup();
  items.value.forEach((item) => {
    if (item.result?.url) {
      URL.revokeObjectURL(item.result.url);
    }
  });
});
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
          :class="{ active: activeTab === 'pdf' }"
          type="button"
          @click="activeTab = 'pdf'"
        >
          📄 PDF → Markdown
        </button>
      </div>
    </header>

    <main class="main">
      <div class="container">
        <!-- 后端服务状态概览（阶段1 可视化验收） -->
        <section class="status-bar">
          <div class="status-pill">
            <span class="label">API Health:</span>
            <span class="value" :class="['value-tag', healthStatus === 'healthy' ? 'ok' : 'warn']">
              {{ healthStatus }}
            </span>
          </div>
          <div class="status-pill">
            <span class="label">Image Service:</span>
            <span
              class="value"
              :class="[
                'value-tag',
                imageServiceStatus === 'operational'
                  ? 'ok'
                  : imageServiceStatus === 'unavailable'
                  ? 'err'
                  : 'warn',
              ]"
            >
              {{ imageServiceStatus }}
            </span>
          </div>
          <div class="status-pill">
            <span class="label">Batch Service:</span>
            <span
              class="value"
              :class="[
                'value-tag',
                batchServiceStatus === 'not_implemented' ? 'warn' : 'ok',
              ]"
            >
              {{ batchServiceStatus }}
            </span>
          </div>
          <button class="status-refresh" type="button" @click="fetchServiceStatus">
            刷新状态
          </button>
        </section>

        <p v-if="statusError" class="status-error">{{ statusError }}</p>

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
          <ImageUploader @upload="handleUpload" @error="handleError" />
          <ProcessingList :items="items" @remove="handleRemove" @preview="handlePreview" />
        </template>

        <!-- PDF 转换页面 -->
        <template v-else>
          <PdfUploader />
        </template>
      </div>
    </main>

    <!-- 预览模态框，仅在图片页使用 -->
    <ImagePreview v-if="activeTab === 'image'" :item="previewItem" @close="handleClosePreview" />

    <footer class="footer">
      <p>
        图片支持: JPEG, PNG, BMP, GIF, TIFF, WebP | 最大尺寸: 1920×1080 | WebP 质量: 92
      </p>
      <p>PDF 服务: 通过 DeepSeek OCR / PDF 分析，将 PDF 转换为 Markdown 文本</p>
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
