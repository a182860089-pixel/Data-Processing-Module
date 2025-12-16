<script setup lang="ts">
import { ref } from "vue";

const API_BASE_URL =
  import.meta.env.VITE_PDF_API_BASE_URL ||
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  "http://localhost:8000";

interface CrawlResult {
  success: boolean;
  title?: string;
  content?: string;
  url: string;
  error?: string;
}

const url = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const result = ref<CrawlResult | null>(null);
const extractImages = ref(false);

const isValidWechatUrl = (input: string): boolean => {
  return /^https?:\/\/mp\.weixin\.qq\.com\/s[/?]/.test(input.trim());
};

const handleCrawl = async () => {
  if (!url.value.trim()) {
    error.value = "请输入微信公众号文章链接";
    return;
  }

  if (!isValidWechatUrl(url.value)) {
    error.value = "请输入有效的微信公众号文章链接 (https://mp.weixin.qq.com/s/...)";
    return;
  }

  loading.value = true;
  error.value = null;
  successMessage.value = null;
  result.value = null;

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/crawl/wechat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: url.value.trim(),
        extract_images: extractImages.value,
        timeout: 60,
      }),
    });

    if (!resp.ok) {
      let detail = "";
      try {
        const data = await resp.json();
        detail =
          data?.detail?.message ||
          data?.detail?.details ||
          data?.detail ||
          data?.message ||
          JSON.stringify(data);
      } catch {
        detail = resp.statusText;
      }
      throw new Error(`爬取失败 (${resp.status}): ${detail}`);
    }

    const data = await resp.json();

    if (!data.success) {
      throw new Error(data.message || "爬取失败");
    }

    result.value = data.data;
    successMessage.value = `文章爬取成功: ${data.data?.title || "未知标题"}`;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "爬取失败";
  } finally {
    loading.value = false;
  }
};

const handleCopy = async () => {
  if (!result.value?.content) return;
  try {
    await navigator.clipboard.writeText(result.value.content);
    successMessage.value = "已复制到剪贴板";
    setTimeout(() => {
      if (successMessage.value === "已复制到剪贴板") {
        successMessage.value = null;
      }
    }, 2000);
  } catch {
    error.value = "复制失败，请手动选择文本复制";
  }
};

const handleDownload = () => {
  if (!result.value?.content) return;

  const title = result.value.title || "article";
  const safeName = title.replace(/[\\/:*?"<>|]/g, "_").substring(0, 50);
  const blob = new Blob([result.value.content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${safeName}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const handleClear = () => {
  url.value = "";
  result.value = null;
  error.value = null;
  successMessage.value = null;
};
</script>

<template>
  <div class="wechat-crawler">
    <section class="card">
      <h2 class="card-title">🔗 微信公众号文章爬取</h2>
      <p class="card-subtitle">输入微信公众号文章链接，自动提取内容并转换为 Markdown</p>

      <div class="form-row">
        <input
          v-model="url"
          type="text"
          class="url-input"
          placeholder="https://mp.weixin.qq.com/s/..."
          @keyup.enter="handleCrawl"
          :disabled="loading"
        />
        <button class="btn" :disabled="loading || !url.trim()" @click="handleCrawl">
          <span v-if="!loading">开始爬取</span>
          <span v-else>爬取中...</span>
        </button>
      </div>

      <div class="options-row">
        <label class="checkbox-label">
          <input type="checkbox" v-model="extractImages" :disabled="loading" />
          提取图片链接
        </label>
        <button v-if="result" class="btn-text" @click="handleClear">清除结果</button>
      </div>

      <!-- 错误/成功提示 -->
      <Transition name="fade">
        <div v-if="error" class="alert alert-error">❌ {{ error }}</div>
      </Transition>
      <Transition name="fade">
        <div v-if="successMessage" class="alert alert-success">✅ {{ successMessage }}</div>
      </Transition>
    </section>

    <!-- 结果展示 -->
    <section v-if="result && result.success" class="card result-card">
      <header class="result-header">
        <div>
          <h3>{{ result.title || "文章内容" }}</h3>
          <p class="result-meta">
            内容长度: {{ result.content?.length || 0 }} 字符
          </p>
        </div>
        <div class="result-actions">
          <button class="btn btn-secondary" @click="handleCopy">📋 复制内容</button>
          <button class="btn btn-outline" @click="handleDownload">📄 下载 MD</button>
        </div>
      </header>

      <textarea
        class="markdown-view"
        readonly
        :value="result.content || ''"
      ></textarea>
    </section>

    <!-- 爬取失败展示 -->
    <section v-if="result && !result.success" class="card error-card">
      <div class="error-content">
        <h3>❌ 爬取失败</h3>
        <p>{{ result.error || "未知错误" }}</p>
        <p class="error-hint">请检查链接是否正确，或稍后重试</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.wechat-crawler {
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

.form-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.url-input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  font-size: 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.url-input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.url-input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

.options-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
}

.checkbox-label input {
  cursor: pointer;
}

.btn-text {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.2s ease, background 0.2s ease;
}

.btn-text:hover {
  color: #374151;
  background: #f3f4f6;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.1s ease, box-shadow 0.1s ease, opacity 0.1s ease;
  box-shadow: 0 10px 25px rgba(79, 70, 229, 0.35);
  white-space: nowrap;
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

.btn-outline:hover:enabled {
  background: #f9fafb;
  transform: translateY(-1px);
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
  max-height: 600px;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.result-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1f2937;
}

.result-meta {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #6b7280;
}

.result-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.markdown-view {
  width: 100%;
  flex: 1;
  resize: none;
  min-height: 300px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #1f2937;
}

.error-card {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.error-content h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #991b1b;
}

.error-content p {
  margin: 0;
  font-size: 14px;
  color: #b91c1c;
}

.error-hint {
  margin-top: 8px !important;
  font-size: 12px !important;
  color: #9ca3af !important;
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
    align-items: stretch;
  }

  .result-header {
    flex-direction: column;
  }

  .result-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
