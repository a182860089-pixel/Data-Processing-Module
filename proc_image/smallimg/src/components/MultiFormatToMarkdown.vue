<script setup lang="ts">
import { ref, computed } from "vue";
import WorkbenchShell from "./WorkbenchShell.vue";
import WorkbenchSummaryCard from "./WorkbenchSummaryCard.vue";
import { renderMarkdownPreview } from "@/utils/markdown-preview";

const API_BASE_URL =
  import.meta.env.VITE_PDF_API_BASE_URL ||
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  "http://localhost:8000";

const emit = defineEmits<{
  error: [message: string];
  success: [message: string];
}>();

type ProcessingMode = "sync" | "async";
type PdfMode = "reader" | "debug";

const processingMode = ref<ProcessingMode>("sync");
const pdfMode = ref<PdfMode>("reader");

const selectedFile = ref<File | null>(null);
const fileTypeLabel = ref<string>("");
const loading = ref(false);
const processingTime = ref(0);
const progress = ref(0);
const progressLabel = ref("");
const previewMode = ref<"formatted" | "source">("formatted");
const isDragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const errorMessage = ref<string>("");
const successMessage = ref<string>("");
const markdownContent = ref<string>("");
const downloadUrl = ref<string>("");
const taskId = ref<string>("");
const pipeline = ref<string>("");
const fallbackUsed = ref(false);
const fallbackPdfOnly = ref(false);
const fallbackReason = ref<string>("");

const fullDownloadUrl = computed(() => {
  if (!downloadUrl.value) return "";
  if (downloadUrl.value.startsWith("http")) return downloadUrl.value;
  return `${API_BASE_URL}${downloadUrl.value}`;
});

const validExtensions = [
  "pdf",
  "docx",
  "doc",
  "pptx",
  "ppt",
  "xlsx",
  "xls",
  "jpg",
  "jpeg",
  "png",
  "gif",
  "bmp",
  "tiff",
  "tif",
  "webp",
  "heic",
  "mp4",
  "avi",
  "mov",
  "wmv",
  "mkv",
  "flv",
];

const detectFileType = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const typeMap: Record<string, string> = {
    pdf: "PDF",
    docx: "Word",
    doc: "Word",
    pptx: "PowerPoint",
    ppt: "PowerPoint",
    xlsx: "Excel",
    xls: "Excel",
    jpg: "Image",
    jpeg: "Image",
    png: "Image",
    gif: "Image",
    bmp: "Image",
    tiff: "Image",
    tif: "Image",
    webp: "Image",
    heic: "Image",
    mp4: "Video",
    avi: "Video",
    mov: "Video",
    wmv: "Video",
    mkv: "Video",
    flv: "Video",
  };
  return typeMap[ext] || "Unknown";
};

const isValidFile = (filename: string): boolean => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  return validExtensions.includes(ext);
};

const resetResultState = () => {
  markdownContent.value = "";
  downloadUrl.value = "";
  taskId.value = "";
  pipeline.value = "";
  fallbackUsed.value = false;
  fallbackPdfOnly.value = false;
  fallbackReason.value = "";
  successMessage.value = "";
  errorMessage.value = "";
  processingTime.value = 0;
};

const buildOptions = () => {
  const fileType = fileTypeLabel.value;

  if (fileType === "PDF") {
    if (pdfMode.value === "reader") {
      return {
        include_metadata: false,
        no_pagination_and_metadata: true,
      };
    }
    return {
      include_metadata: true,
      no_pagination_and_metadata: false,
    };
  }

  if (["Word", "PowerPoint", "Excel"].includes(fileType)) {
    return {
      keep_layout: true,
      office_dpi: 96,
      dpi: 144,
    };
  }

  if (fileType === "Image") {
    return {
      page_size: "A4",
      fit_mode: "fit",
      dpi: 144,
    };
  }

  if (fileType === "Video") {
    return {
      output_type: "markdown",
      include_frames: false,
      include_metadata: true,
      keyframe_interval: 5,
      max_frames: 50,
    };
  }

  return {};
};

const buildFormData = (options: Record<string, any>) => {
  const formData = new FormData();
  formData.append("file", selectedFile.value as File);
  formData.append("options", JSON.stringify(options));
  return formData;
};

const parseError = async (resp: Response) => {
  try {
    const data = await resp.json();
    const detail = data?.detail?.message || data?.detail || data?.message;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  } catch {
    return resp.statusText || "请求失败";
  }
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const renderMarkdownAsHtml = (markdown: string): string => {
  if (!markdown) return "";

  let html = markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/^###\s+(.*)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s+(.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s+(.*)$/gm, "<h1>$1</h1>");
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\n\n+/g, "</p><p>");
  html = `<p>${html}</p>`;
  html = html.replace(/<p><\/p>/g, "");
  html = html.replace(/<p>(<h[1-3]>.*?<\/h[1-3]>)<\/p>/g, "$1");
  return html;
};

const applyConversionResult = (
  data: Record<string, any>,
  fromFallback: boolean
) => {
  const resolvedTaskId = data.task_id || taskId.value;
  const resolvedMarkdown = data.markdown_content || data.result?.markdown_content || "";
  const resolvedDownloadUrl =
    data.download_url ||
    data.result?.download_url ||
    (resolvedTaskId ? `/api/v1/download/${resolvedTaskId}` : "");
  const resolvedFileType =
    data.file_type ||
    data.result?.metadata?.output_type ||
    data.metadata?.output_type ||
    "markdown";
  const metadata = data.metadata || data.result?.metadata || {};

  taskId.value = resolvedTaskId || "";
  markdownContent.value = resolvedMarkdown;
  downloadUrl.value = resolvedDownloadUrl;
  pipeline.value = metadata.pipeline || "";

  fallbackUsed.value = fromFallback;
  fallbackPdfOnly.value = fromFallback && resolvedFileType === "pdf" && !resolvedMarkdown;

  if (markdownContent.value) {
    successMessage.value = fromFallback
      ? "新接口失败，已自动回退旧接口并完成转换。"
      : "Markdown 转换完成。";
  } else if (fallbackPdfOnly.value) {
    successMessage.value = "新接口失败，已回退旧接口并返回 PDF 结果。";
  } else {
    successMessage.value = "转换完成。";
  }
  emit("success", successMessage.value);
};

const submitFallbackConvert = async (options: Record<string, any>) => {
  const resp = await fetch(`${API_BASE_URL}/api/v1/convert`, {
    method: "POST",
    body: buildFormData(options),
  });

  if (!resp.ok) {
    const detail = await parseError(resp);
    throw new Error(`回退接口失败 (${resp.status}): ${detail}`);
  }
  return resp.json();
};

const pollTaskResult = async (id: string) => {
  const maxPolls = 600;
  for (let i = 0; i < maxPolls; i++) {
    await sleep(1000);
    const statusResp = await fetch(`${API_BASE_URL}/api/v1/status/${id}`);
    if (!statusResp.ok) continue;

    const statusData = await statusResp.json();
    if (typeof statusData.progress?.percentage === "number") {
      progress.value = Math.min(95, 12 + statusData.progress.percentage * 0.83);
      progressLabel.value = statusData.message || "处理中...";
    }
    if (statusData.status === "completed") {
      return {
        task_id: id,
        file_type: statusData.result?.metadata?.output_type || "markdown",
        markdown_content: statusData.result?.markdown_content || "",
        download_url: statusData.result?.download_url || `/api/v1/download/${id}`,
        metadata: statusData.result?.metadata || {},
      };
    }
    if (statusData.status === "failed") {
      const msg = statusData.error?.details || statusData.error?.message || "任务执行失败";
      throw new Error(msg);
    }
  }
  throw new Error("异步任务轮询超时");
};

const handleFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  if (!isValidFile(file.name)) {
    errorMessage.value = "不支持的文件格式，请选择 PDF/Office/图片/视频 文件。";
    emit("error", errorMessage.value);
    selectedFile.value = null;
    return;
  }

  resetResultState();
  selectedFile.value = file;
  fileTypeLabel.value = detectFileType(file.name);
};

const handleClick = () => {
  fileInput.value?.click();
};

const handleDragEnter = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = true;
};

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = false;
};

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
};

const handleDrop = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (!file) return;
  const mockEvent = { target: { files: [file] } } as unknown as Event;
  handleFileChange(mockEvent);
};

const handleCopy = async () => {
  if (!markdownContent.value) return;
  try {
    await navigator.clipboard.writeText(markdownContent.value);
    successMessage.value = "已复制 Markdown 内容到剪贴板。";
  } catch {
    errorMessage.value = "复制失败，请手动复制。";
    emit("error", errorMessage.value);
  }
};

const handleSubmit = async () => {
  if (!selectedFile.value) {
    errorMessage.value = "请先选择文件。";
    emit("error", errorMessage.value);
    return;
  }

  resetResultState();
  loading.value = true;
  progress.value = 8;
  progressLabel.value = "准备提交任务";
  const start = Date.now();
  const options = buildOptions();

  try {
    if (processingMode.value === "sync") {
      try {
        const resp = await fetch(`${API_BASE_URL}/api/v1/convert/markdown`, {
          method: "POST",
          body: buildFormData(options),
        });
        progress.value = 45;
        progressLabel.value = "同步转换中";
        if (!resp.ok) {
          throw new Error(await parseError(resp));
        }
        const data = await resp.json();
        progress.value = 100;
        progressLabel.value = "转换完成";
        applyConversionResult(data, false);
      } catch (primaryError) {
        fallbackReason.value =
          primaryError instanceof Error ? primaryError.message : "新接口调用失败";
        const fallbackData = await submitFallbackConvert(options);
        applyConversionResult(fallbackData, true);
      }
    } else {
      try {
        const submitResp = await fetch(`${API_BASE_URL}/api/v1/convert/markdown/async`, {
          method: "POST",
          body: buildFormData(options),
        });
        progress.value = 18;
        progressLabel.value = "任务已提交，等待处理";
        if (!submitResp.ok) {
          throw new Error(await parseError(submitResp));
        }
        const submitData = await submitResp.json();
        taskId.value = submitData.task_id || "";
        const taskResult = await pollTaskResult(taskId.value);
        progress.value = 100;
        progressLabel.value = "转换完成";
        applyConversionResult(taskResult, false);
      } catch (primaryError) {
        fallbackReason.value =
          primaryError instanceof Error ? primaryError.message : "新接口调用失败";
        const fallbackData = await submitFallbackConvert(options);
        applyConversionResult(fallbackData, true);
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "转换失败";
    emit("error", errorMessage.value);
  } finally {
    processingTime.value = (Date.now() - start) / 1000;
    loading.value = false;
  }
};
</script>

<template>
  <WorkbenchShell title="实时任务看板" :count="selectedFile ? 1 : 0" :clear-disabled="loading && !selectedFile" @clear="resetResultState">
    <template #controls>
      <div class="panel-card intro-card">
        <p class="panel-caption">第一步：执行管线</p>
        <h2>同步、异步与 PDF 解析模式</h2>
        <p class="panel-copy">左侧负责转换模式、处理策略和文件输入，右侧只负责状态反馈和结果查看。</p>
      </div>

      <div class="upload-zone compact-upload" :class="{ dragging: isDragging }" @click="handleClick" @dragenter="handleDragEnter" @dragleave="handleDragLeave" @dragover="handleDragOver" @drop="handleDrop">
        <input
          ref="fileInput"
          type="file"
          class="hidden-input"
          accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.tif,.webp,.heic,.mp4,.avi,.mov,.wmv,.mkv,.flv"
          @change="handleFileChange"
        />
        <div class="upload-content compact-copy">
          <div class="upload-icon-circle">✦</div>
          <h3>上传待转换文件</h3>
          <p>支持 PDF、Office、图片和视频文件</p>
        </div>
        <p v-if="selectedFile" class="file-name">
          📄 已选择：{{ selectedFile.name }}
          <span class="file-type-badge">{{ fileTypeLabel }}</span>
        </p>
      </div>

      <div class="panel-card">
        <p class="panel-caption">执行方式</p>
        <div class="mode-row compact">
          <label class="mode-item"><input v-model="processingMode" type="radio" value="sync" />同步</label>
          <label class="mode-item"><input v-model="processingMode" type="radio" value="async" />异步</label>
        </div>
      </div>

      <div v-if="fileTypeLabel === 'PDF'" class="panel-card">
        <p class="panel-caption">PDF 模式</p>
        <div class="mode-row compact">
          <label class="mode-item"><input v-model="pdfMode" type="radio" value="reader" />阅读模式</label>
          <label class="mode-item"><input v-model="pdfMode" type="radio" value="debug" />调试模式</label>
        </div>
      </div>

      <button class="launch-button" :class="{ disabled: loading || !selectedFile }" :disabled="loading || !selectedFile" @click="handleSubmit">
        <span v-if="!loading">启动多格式转换</span>
        <span v-else>转换中...</span>
      </button>
    </template>

    <template #preview>
      <div v-if="!selectedFile && !successMessage && !errorMessage" class="empty-preview">
        <div class="empty-mark">✦</div>
        <h3>等待文件进入任务区</h3>
        <p>右侧负责状态反馈和 Markdown 结果预览。</p>
      </div>

      <div v-else class="result-stack">
        <section v-if="loading" class="panel-card message-card">
          <p class="msg-tip">{{ progressLabel || "处理中..." }}</p>
          <div class="progress-rail">
            <div class="progress-bar" :style="{ width: progress + '%' }"></div>
          </div>
          <p class="msg-tip">当前进度：{{ Math.round(progress) }}%</p>
        </section>

        <section v-if="successMessage || errorMessage" class="panel-card message-card">
          <p v-if="successMessage" class="msg-success">✅ {{ successMessage }}</p>
          <p v-if="errorMessage" class="msg-error">❌ {{ errorMessage }}</p>
          <p v-if="fallbackUsed && fallbackReason" class="msg-tip">回退原因：{{ fallbackReason }}</p>
          <p v-if="processingTime > 0" class="msg-tip">耗时：{{ processingTime.toFixed(2) }}s</p>
          <p v-if="pipeline" class="msg-tip">流水线：{{ pipeline }}</p>
        </section>

        <WorkbenchSummaryCard v-if="markdownContent || fullDownloadUrl" eyebrow="转换结果" title="结果已就绪" compact-actions>
          <template #actions>
            <button v-if="markdownContent" class="ghost-button summary-action" @click="handleCopy">复制</button>
            <a v-if="fullDownloadUrl" class="launch-link summary-action" :href="fullDownloadUrl" target="_blank" rel="noopener">下载</a>
          </template>

          <div v-if="markdownContent" class="reader-panel">
            <div class="reader-toolbar">
              <h4 class="reader-title">正文预览</h4>
              <div class="reader-actions">
                <div class="reader-switcher">
                  <button class="reader-switch" :class="{ active: previewMode === 'formatted' }" @click="previewMode = 'formatted'">阅读视图</button>
                  <button class="reader-switch" :class="{ active: previewMode === 'source' }" @click="previewMode = 'source'">源码视图</button>
                </div>
              </div>
            </div>
            <div v-if="previewMode === 'formatted'" class="reader-content reader-markdown" v-html="renderMarkdownPreview(markdownContent)"></div>
            <textarea v-else class="reader-source" readonly :value="markdownContent" />
          </div>
          <div v-else-if="fallbackPdfOnly" class="fallback-hint">已回退到旧接口，当前结果为 PDF，请使用“下载结果”获取文件。</div>
        </WorkbenchSummaryCard>
      </div>
    </template>
  </WorkbenchShell>
</template>

<style scoped>
.multi-format-markdown {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.card {
  background: white;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}

.card-title {
  margin: 0 0 8px 0;
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
}

.card-subtitle {
  margin: 0 0 16px 0;
  color: #6b7280;
  font-size: 14px;
}

.summary-action {
  min-height: 44px;
  padding: 0 16px;
  border-radius: 18px;
  font-size: 14px;
  font-weight: 800;
}

.ghost-button {
  border: none;
  background: rgba(255, 255, 255, 0.88);
  color: #8390ab;
  cursor: pointer;
}

.launch-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: linear-gradient(135deg, #13203c 0%, #0f1730 100%);
  color: #fff;
  text-decoration: none;
  box-shadow: 0 20px 40px rgba(16, 25, 52, 0.2);
}

.mode-row {
  display: flex;
  gap: 16px;
  margin: 12px 0;
  flex-wrap: wrap;
}

.mode-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #374151;
  font-size: 14px;
}

.form-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 8px;
}

.file-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}

.vertical-upload {
  flex-direction: column;
  align-items: flex-start;
}

.hidden-input {
  display: none;
}

.upload-zone {
  position: relative;
  border: 1px dashed #d6def2;
  border-radius: 24px;
  padding: 26px 18px;
  text-align: center;
  cursor: pointer;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 255, 0.8));
  transition: all 0.25s ease;
}

.upload-zone.dragging,
.upload-zone:hover {
  border-color: #93a4ff;
  background: #f3f6ff;
}

.upload-content.compact-copy h3 {
  margin: 0 0 8px;
  color: #15203a;
  font-size: 20px;
}

.upload-icon-circle {
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #eef2ff 0%, #f7f9ff 100%);
  color: #4f67f8;
  font-size: 28px;
  font-weight: 800;
}

.compact-upload-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-name {
  margin-top: 16px;
  color: #374151;
  font-size: 14px;
}

.file-type-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 12px;
}

.btn {
  border: 1px solid transparent;
  background: #4f46e5;
  color: white;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 14px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.message-card {
  padding: 14px 18px;
}

.msg-success {
  color: #166534;
  margin: 0 0 6px 0;
}

.msg-error {
  color: #b91c1c;
  margin: 0 0 6px 0;
}

.msg-tip {
  color: #475569;
  margin: 0;
  font-size: 13px;
}

.result-card {
  padding-top: 16px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.result-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.markdown-view {
  width: 100%;
  min-height: 360px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  padding: 12px;
  resize: vertical;
  font-family: Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
}

.inline-markdown {
  width: 100%;
  min-height: 360px;
  border-radius: 18px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  padding: 16px;
  resize: vertical;
  background: #fbfcff;
  color: #1f2b49;
  line-height: 1.7;
}

.rendered-preview {
  min-height: 360px;
  max-height: 520px;
  overflow: auto;
  border-radius: 18px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  padding: 22px;
  background: #fbfcff;
}

.markdown-reading {
  color: #1f2b49;
  line-height: 1.85;
}

.markdown-reading :deep(h1),
.markdown-reading :deep(h2),
.markdown-reading :deep(h3) {
  color: #13203c;
  margin: 0 0 16px;
}

.markdown-reading :deep(p) {
  margin: 0 0 16px;
}

.markdown-reading :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #eef2ff;
  color: #4f67f8;
}

.switch-chip {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  background: #fff;
  color: #8390ab;
  font-weight: 700;
  cursor: pointer;
}

.switch-chip.active {
  background: #101934;
  color: #fff;
  border-color: #101934;
}

.progress-rail {
  margin-top: 12px;
  height: 8px;
  border-radius: 999px;
  background: #e4e9f7;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6175ff, #4f67f8);
}

.fallback-hint {
  border: 1px dashed #94a3b8;
  border-radius: 10px;
  padding: 14px;
  color: #334155;
  background: #f8fafc;
}

@media (max-width: 768px) {
  .result-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .result-actions {
    width: 100%;
  }
}
</style>
