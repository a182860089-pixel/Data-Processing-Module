<script setup lang="ts">
import { ref } from "vue";

const API_BASE_URL = import.meta.env.VITE_PDF_API_BASE_URL || "http://localhost:8000";

const file = ref<File | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const markdown = ref<string>("");
const downloadUrl = ref<string>("");
const taskId = ref<string>("");

// 选项：阅读模式（不带分页/元数据）或 调试模式（带分页/元数据）
const mode = ref<"reader" | "debug">("reader");

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement;
  const files = target.files;
  if (!files || files.length === 0) {
    file.value = null;
    return;
  }
  const f = files[0];
  if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
    error.value = "请选择 PDF 文件";
    file.value = null;
    return;
  }
  error.value = null;
  successMessage.value = null;
  markdown.value = "";
  downloadUrl.value = "";
  taskId.value = "";
  file.value = f;
};

const buildOptions = () => {
  if (mode.value === "reader") {
    // 阅读模式：不带分页、不带元数据，更适合直接阅读
    return {
      include_metadata: false,
      no_pagination_and_metadata: true,
    };
  }
  // 调试模式：带分页和元数据，方便查看每页 OCR 情况
  return {
    include_metadata: true,
    no_pagination_and_metadata: false,
  };
};

const handleSubmit = async () => {
  if (!file.value) {
    error.value = "请先选择一个 PDF 文件";
    return;
  }

  loading.value = true;
  error.value = null;
  successMessage.value = null;
  markdown.value = "";
  downloadUrl.value = "";
  taskId.value = "";

  try {
    const formData = new FormData();
    formData.append("file", file.value);

    const options = buildOptions();
    formData.append("options", JSON.stringify(options));

    const resp = await fetch(`${API_BASE_URL}/api/v1/convert`, {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      let detail = "";
      try {
        const data = await resp.json();
        detail = data?.detail?.message || data?.detail || JSON.stringify(data);
      } catch {
        detail = resp.statusText;
      }
      throw new Error(`转换失败 (${resp.status}): ${detail}`);
    }

    const data = await resp.json();
    // 兼容 README 中示例的字段
    markdown.value = data.markdown_content || data.data?.markdown_content || "";
    taskId.value = data.task_id || data.data?.task_id || "";
    downloadUrl.value =
      data.download_url ||
      (taskId.value ? `/api/v1/download/${taskId.value}` : "");

    if (!markdown.value) {
      throw new Error("后端未返回 markdown_content 字段");
    }

    successMessage.value = "PDF 转换完成";
  } catch (e) {
    error.value = e instanceof Error ? e.message : "转换失败";
  } finally {
    loading.value = false;
  }
};

const handleCopy = async () => {
  if (!markdown.value) return;
  try {
    await navigator.clipboard.writeText(markdown.value);
    successMessage.value = "已复制到剪贴板";
    setTimeout(() => {
      if (successMessage.value === "已复制到剪贴板") {
        successMessage.value = null;
      }
    }, 2000);
  } catch (e) {
    error.value = "复制失败，请手动选择文本复制";
  }
};

const fullDownloadUrl = () => {
  if (!downloadUrl.value) return "";
  if (downloadUrl.value.startsWith("http")) return downloadUrl.value;
  return `${API_BASE_URL}${downloadUrl.value}`;
};
</script>

<template>
  <div class="pdf-uploader">
    <section class="card">
      <h2 class="card-title">📄 PDF 转 Markdown</h2>
      <p class="card-subtitle">上传 PDF，后端通过 DeepSeek OCR 将其转换为 Markdown 文本</p>

      <!-- 模式选择 -->
      <div class="mode-switch">
        <label>
          <input type="radio" value="reader" v-model="mode" />
          阅读模式（不带分页/元数据）
        </label>
        <label>
          <input type="radio" value="debug" v-model="mode" />
          调试模式（带分页和元数据）
        </label>
      </div>

      <div class="form-row">
        <label class="file-label">
          <span>选择 PDF 文件</span>
          <input type="file" accept="application/pdf,.pdf" @change="handleFileChange" />
        </label>

        <button class="btn" :disabled="loading" @click="handleSubmit">
          <span v-if="!loading">开始转换</span>
          <span v-else>正在转换...</span>
        </button>
      </div>

      <p v-if="file" class="file-name">已选择：{{ file.name }}</p>

      <!-- 错误/成功提示 -->
      <Transition name="fade">
        <div v-if="error" class="alert alert-error">❌ {{ error }}</div>
      </Transition>
      <Transition name="fade">
        <div v-if="successMessage" class="alert alert-success">✅ {{ successMessage }}</div>
      </Transition>
    </section>

    <!-- 结果展示 -->
    <section v-if="markdown" class="card result-card">
      <header class="result-header">
        <h3>转换结果 Markdown</h3>
        <div class="result-actions">
          <button class="btn btn-secondary" @click="handleCopy">复制内容</button>
          <a v-if="fullDownloadUrl()" class="btn btn-outline" :href="fullDownloadUrl()" target="_blank" rel="noopener">
            下载 Markdown 文件
          </a>
        </div>
      </header>

      <textarea class="markdown-view" readonly :value="markdown"></textarea>
    </section>
  </div>
</template>

<style scoped>
.pdf-uploader {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.card {
  background: white;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
}

.card-title {
  margin: 0 0 8px 0;
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
}

.card-subtitle {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #6b7280;
}

.mode-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #374151;
}

.mode-switch label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.file-label {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
  font-size: 14px;
  cursor: pointer;
}

.file-label input[type="file"] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.1s ease, box-shadow 0.1s ease, opacity 0.1s ease;
  box-shadow: 0 10px 25px rgba(79, 70, 229, 0.35);
}

.btn:hover:enabled {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(79, 70, 229, 0.4);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #4b5563;
  box-shadow: 0 10px 25px rgba(31, 41, 55, 0.35);
}

.btn-outline {
  background: white;
  color: #4b5563;
  border: 1px solid #d1d5db;
  box-shadow: none;
}

.file-name {
  margin-top: 8px;
  font-size: 13px;
  color: #4b5563;
}

.alert {
  margin-top: 16px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}

.alert-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

.alert-success {
  background-color: #ecfdf3;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.result-card {
  max-height: 520px;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-header h3 {
  margin: 0;
  font-size: 18px;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.markdown-view {
  width: 100%;
  flex: 1;
  resize: none;
  min-height: 260px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .result-actions {
    flex-wrap: wrap;
    justify-content: flex-start;
  }
}
</style>
