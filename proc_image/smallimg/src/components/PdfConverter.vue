<script setup lang="ts">
import { ref, reactive } from "vue";
import { useMultiFileProcessor, type FileTask } from "@/composables/useMultiFileProcessor";
import MultiFileTaskList from "./MultiFileTaskList.vue";

const API_BASE_URL =
  import.meta.env.VITE_PDF_API_BASE_URL ||
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  "http://localhost:8000";

interface ConvertResult {
  taskId: string;
  markdown: string;
  downloadUrl: string;
  processingTime: number;
}

const emit = defineEmits<{
  error: [message: string]
}>();

// 选项
const mode = ref<"reader" | "debug">("reader");

const isDragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

// 验证文件类型
const isValidFile = (filename: string): boolean => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const validExt = [
    "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
    "jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"
  ];
  return validExt.includes(ext);
};

// 检测文件类型
const detectFileType = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const typeMap: Record<string, string> = {
    pdf: "PDF",
    docx: "Word", doc: "Word",
    pptx: "PowerPoint", ppt: "PowerPoint",
    xlsx: "Excel", xls: "Excel",
    jpg: "Image", jpeg: "Image", png: "Image",
    gif: "Image", bmp: "Image", tiff: "Image", webp: "Image",
  };
  return typeMap[ext] || "Unknown";
};

// 构建选项
const buildOptions = (fileType: string) => {
  if (fileType === "PDF") {
    if (mode.value === "reader") {
      return { include_metadata: false, no_pagination_and_metadata: true };
    }
    return { include_metadata: true, no_pagination_and_metadata: false };
  }
  
  if (["Word", "PowerPoint", "Excel"].includes(fileType)) {
    return { keep_layout: true, office_dpi: 96, dpi: 144 };
  }
  
  if (fileType === "Image") {
    return { page_size: "A4", fit_mode: "fit", dpi: 144 };
  }
  
  return {};
};

// 转换单个文件
const convertFile = async (
  file: File,
  onProgress?: (progress: number) => void
): Promise<ConvertResult> => {
  const startTime = Date.now();
  onProgress?.(5);

  const fileType = detectFileType(file.name);
  const formData = new FormData();
  formData.append("file", file);
  formData.append("options", JSON.stringify(buildOptions(fileType)));

  onProgress?.(20);

  const resp = await fetch(`${API_BASE_URL}/api/v1/convert`, {
    method: "POST",
    body: formData,
  });

  onProgress?.(70);

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
  const processingTime = (Date.now() - startTime) / 1000;

  onProgress?.(100);

  const markdown = data.markdown_content || data.data?.markdown_content || "";
  const taskId = data.task_id || data.data?.task_id || "";
  const downloadUrl = data.download_url || (taskId ? `/api/v1/download/${taskId}` : "");

  return {
    taskId,
    markdown,
    downloadUrl: downloadUrl.startsWith("http") ? downloadUrl : `${API_BASE_URL}${downloadUrl}`,
    processingTime,
  };
};

const {
  tasks,
  isProcessing,
  metrics,
  addFiles,
  removeTask,
  clearTasks,
  startProcessing,
  stopProcessing,
  retryFailed,
  formatFileSize,
  getTaskDuration,
} = useMultiFileProcessor<ConvertResult>(convertFile, { concurrency: 2 });

// 处理文件选择
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files));
    target.value = "";
  }
};

// 处理拖拽
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

  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    handleFiles(Array.from(e.dataTransfer.files));
  }
};

// 处理文件
const handleFiles = (files: File[]) => {
  const validFiles: File[] = [];
  const errors: string[] = [];

  files.forEach((file) => {
    if (!isValidFile(file.name)) {
      errors.push(`${file.name}: 不支持的文件格式`);
    } else {
      validFiles.push(file);
    }
  });

  if (errors.length > 0) {
    emit("error", errors.join("\n"));
  }

  if (validFiles.length > 0) {
    addFiles(validFiles);
  }
};

// 点击上传区域
const handleClick = () => {
  fileInput.value?.click();
};

// 复制Markdown内容
const handleCopy = async (task: FileTask<ConvertResult>) => {
  if (!task.result?.markdown) return;
  try {
    await navigator.clipboard.writeText(task.result.markdown);
  } catch {
    emit("error", "复制失败");
  }
};

// 下载结果
const handleDownload = (task: FileTask<ConvertResult>) => {
  if (!task.result?.downloadUrl) return;
  const link = document.createElement("a");
  link.href = task.result.downloadUrl;
  link.target = "_blank";
  link.click();
};

// 预览的任务
const previewTask = ref<FileTask<ConvertResult> | null>(null);

const showPreview = (task: FileTask<ConvertResult>) => {
  previewTask.value = task;
};

const closePreview = () => {
  previewTask.value = null;
};
</script>

<template>
  <div class="pdf-converter">
    <div class="card">
      <h2 class="card-title">📄 PDF → Markdown</h2>
      <p class="card-subtitle">支持批量上传 PDF、Office文档、图片，异步转换为 Markdown</p>

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

      <!-- 上传区域 -->
      <div
        class="uploader"
        :class="{ dragging: isDragging }"
        @click="handleClick"
        @dragenter="handleDragEnter"
        @dragleave="handleDragLeave"
        @dragover="handleDragOver"
        @drop="handleDrop"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.webp"
          multiple
          style="display: none"
          @change="handleFileSelect"
        />

        <div class="uploader-content">
          <div class="icon">📁</div>
          <div class="title">点击或拖拽上传文件</div>
          <div class="subtitle">支持 PDF、Word、PowerPoint、Excel、图片（可多选）</div>
        </div>
      </div>

      <!-- 任务列表 -->
      <MultiFileTaskList
        :tasks="tasks"
        :metrics="metrics"
        :is-processing="isProcessing"
        :show-metrics="true"
        :format-file-size="formatFileSize"
        :get-task-duration="getTaskDuration"
        @remove="removeTask"
        @start="startProcessing"
        @stop="stopProcessing"
        @clear="clearTasks"
        @retry-failed="retryFailed"
        @download="handleDownload"
      />

      <!-- 结果操作按钮 -->
      <div v-if="tasks.filter(t => t.status === 'completed').length > 0" class="results-actions">
        <div
          v-for="task in tasks.filter(t => t.status === 'completed')"
          :key="task.id"
          class="result-item"
        >
          <span class="result-name">{{ task.name }}</span>
          <div class="result-buttons">
            <button
              v-if="task.result?.markdown"
              class="btn btn-sm btn-secondary"
              @click="showPreview(task)"
            >
              👁️ 预览
            </button>
            <button
              v-if="task.result?.markdown"
              class="btn btn-sm btn-secondary"
              @click="handleCopy(task)"
            >
              📋 复制
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 预览模态框 -->
    <Teleport to="body">
      <div v-if="previewTask" class="modal-overlay" @click.self="closePreview">
        <div class="modal-content">
          <div class="modal-header">
            <h3>{{ previewTask.name }} - Markdown 预览</h3>
            <button class="btn-close" @click="closePreview">✕</button>
          </div>
          <div class="modal-body">
            <textarea
              class="markdown-view"
              readonly
              :value="previewTask.result?.markdown || ''"
            ></textarea>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="handleCopy(previewTask)">📋 复制</button>
            <button class="btn btn-primary" @click="closePreview">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.pdf-converter {
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
  cursor: pointer;
}

.uploader {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #fafafa;
}

.uploader:hover {
  border-color: #667eea;
  background-color: #f0f7ff;
}

.uploader.dragging {
  border-color: #667eea;
  background-color: #e6f7ff;
  transform: scale(1.02);
}

.uploader-content {
  pointer-events: none;
}

.icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 14px;
  color: #666;
}

.results-actions {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 6px;
}

.result-name {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.result-buttons {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
}

.btn-secondary:hover:not(:disabled) {
  background: #d1d5db;
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: #f3f4f6;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.btn-close:hover {
  background: #e5e7eb;
}

.modal-body {
  flex: 1;
  padding: 16px 20px;
  overflow: hidden;
}

.markdown-view {
  width: 100%;
  height: 400px;
  resize: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

@media (max-width: 768px) {
  .mode-switch {
    flex-direction: column;
    gap: 8px;
  }

  .modal-content {
    width: 95%;
    max-height: 90vh;
  }
}
</style>
