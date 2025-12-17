<script setup lang="ts">
import { ref, reactive } from "vue";
import { isValidImageFile, isValidFileSize } from "@/utils/image-utils";

const API_BASE_URL =
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  import.meta.env.VITE_PDF_API_BASE_URL ||
  "http://localhost:8000";

interface ConvertTask {
  id: string;
  name: string;
  files: File[];
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  result?: { taskId: string; filename: string; downloadUrl: string };
  error?: string;
  startTime: number;
  endTime?: number;
}

const emit = defineEmits<{
  success: [{ taskId: string; filename: string; downloadUrl: string }]
  error: [message: string]
}>();

const isDragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);
const pageSize = ref<"A4" | "A3" | "A5" | "letter">("A4");
const fitMode = ref<"fit" | "contain" | "cover" | "stretch">("fit");

// 任务列表（支持批量转换）
const tasks = ref<ConvertTask[]>([]);
const isProcessing = ref(false);

const metrics = reactive({
  totalTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
});

const generateTaskId = () =>
  `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files));
    target.value = '';
  }
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

  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    handleFiles(Array.from(e.dataTransfer.files));
  }
};

const handleFiles = (files: File[]) => {
  const validFiles: File[] = [];
  const errors: string[] = [];

  files.forEach((file) => {
    if (!isValidImageFile(file)) {
      errors.push(`${file.name}: 不支持的文件格式`);
    } else if (!isValidFileSize(file)) {
      errors.push(`${file.name}: 文件大小超过50MB`);
    } else {
      validFiles.push(file);
    }
  });

  if (errors.length > 0) {
    emit("error", errors.join("\n"));
  }

  if (validFiles.length > 0) {
    selectedFiles.value.push(...validFiles);
  }
};

const handleClick = () => {
  fileInput.value?.click();
};

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1);
};

const clearFiles = () => {
  selectedFiles.value = [];
  if (fileInput.value) {
    fileInput.value.value = "";
  }
};

// 转换单个任务
const convertTask = async (task: ConvertTask) => {
  task.status = 'processing';
  task.startTime = Date.now();
  task.progress = 10;

  try {
    const formData = new FormData();
    task.files.forEach((file) => {
      formData.append("files", file);
    });

    const convertOptions = {
      page_size: pageSize.value,
      fit_mode: fitMode.value,
    };
    formData.append("options", JSON.stringify(convertOptions));

    task.progress = 30;

    const response = await fetch(`${API_BASE_URL}/api/v1/convert/images`, {
      method: "POST",
      body: formData,
    });

    task.progress = 70;

    if (!response.ok) {
      let detail = "";
      try {
        const data = await response.json();
        detail =
          (data?.detail &&
            (data.detail.message || data.detail.details || data.detail)) ||
          JSON.stringify(data);
      } catch {
        detail = response.statusText;
      }
      throw new Error(`转换失败 (${response.status}): ${detail}`);
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(data.message || "转换失败");
    }

    task.progress = 100;
    task.status = 'completed';
    task.endTime = Date.now();
    task.result = {
      taskId: data.task_id,
      filename: data.filename,
      downloadUrl: data.download_url.startsWith("http")
        ? data.download_url
        : `${API_BASE_URL}${data.download_url}`,
    };

    metrics.completedTasks++;
    emit("success", task.result);
  } catch (err) {
    task.status = 'failed';
    task.error = err instanceof Error ? err.message : "转换失败";
    task.endTime = Date.now();
    task.progress = 0;
    metrics.failedTasks++;
  }
};

// 添加转换任务
const handleConvert = async () => {
  if (selectedFiles.value.length === 0) {
    emit("error", "请至少选择一张图片");
    return;
  }

  // 创建新任务
  const task: ConvertTask = {
    id: generateTaskId(),
    name: selectedFiles.value.length === 1 
      ? selectedFiles.value[0].name 
      : `${selectedFiles.value.length}张图片合并`,
    files: [...selectedFiles.value],
    status: 'pending',
    progress: 0,
    startTime: 0,
  };

  tasks.value.push(task);
  metrics.totalTasks++;
  clearFiles();

  // 立即开始处理
  if (!isProcessing.value) {
    startProcessing();
  }
};

// 开始处理所有待处理任务
const startProcessing = async () => {
  if (isProcessing.value) return;
  isProcessing.value = true;

  while (true) {
    const pendingTask = tasks.value.find(t => t.status === 'pending');
    if (!pendingTask) break;
    await convertTask(pendingTask);
  }

  isProcessing.value = false;
};

// 移除任务
const removeTask = (taskId: string) => {
  const index = tasks.value.findIndex(t => t.id === taskId);
  if (index !== -1) {
    const task = tasks.value[index];
    if (task.status !== 'processing') {
      tasks.value.splice(index, 1);
      metrics.totalTasks = tasks.value.length;
      metrics.completedTasks = tasks.value.filter(t => t.status === 'completed').length;
      metrics.failedTasks = tasks.value.filter(t => t.status === 'failed').length;
    }
  }
};

// 清空所有任务
const clearTasks = () => {
  tasks.value = [];
  metrics.totalTasks = 0;
  metrics.completedTasks = 0;
  metrics.failedTasks = 0;
};

// 重试失败的任务
const retryFailed = async () => {
  tasks.value.forEach(task => {
    if (task.status === 'failed') {
      task.status = 'pending';
      task.progress = 0;
      task.error = undefined;
    }
  });
  metrics.failedTasks = 0;
  startProcessing();
};

// 下载结果
const downloadResult = (task: ConvertTask) => {
  if (!task.result) return;
  const link = document.createElement('a');
  link.href = task.result.downloadUrl;
  link.download = task.result.filename;
  link.click();
};

const totalSize = () => {
  return selectedFiles.value.reduce((sum, file) => sum + file.size, 0);
};

const formatSize = (bytes: number) => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (
    Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i]
  );
};

const getTaskDuration = (task: ConvertTask) => {
  if (!task.startTime) return 0;
  const endTime = task.endTime || Date.now();
  return Math.round((endTime - task.startTime) / 1000);
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: '#999999',
    processing: '#1890ff',
    completed: '#52c41a',
    failed: '#ff4d4f',
  };
  return colors[status] || '#999999';
};

const getStatusIcon = (status: string) => {
  const icons: Record<string, string> = {
    pending: '⏳',
    processing: '⚙️',
    completed: '✅',
    failed: '❌',
  };
  return icons[status] || '❓';
};

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  };
  return texts[status] || status;
};
</script>

<template>
  <div class="converter">
    <h2 class="card-title">🖼️ 多图转PDF</h2>
    <p class="card-subtitle">支持批量上传图片，异步转换为 PDF</p>

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
        accept="image/*"
        multiple
        style="display: none"
        @change="handleFileSelect"
      />

      <div class="uploader-content">
        <div class="icon">📁</div>
        <div class="title">点击或拖拽上传图片</div>
        <div class="subtitle">支持 JPEG, PNG, BMP, GIF, TIFF, WebP（可多选）</div>
      </div>
    </div>

    <!-- 已选择的文件列表 -->
    <div v-if="selectedFiles.length > 0" class="file-list">
      <div class="list-header">
        <h3>已选择 {{ selectedFiles.length }} 张图片</h3>
        <div class="list-size">总大小: {{ formatSize(totalSize()) }}</div>
      </div>

      <div class="files">
        <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
          <div class="file-info">
            <span class="file-index">{{ index + 1 }}</span>
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">({{ formatSize(file.size) }})</span>
          </div>
          <button
            class="remove-btn"
            type="button"
            @click="removeFile(index)"
            title="移除此文件"
          >
            ✕
          </button>
        </div>
      </div>

      <div class="options">
        <div class="option-group">
          <label>页面大小:</label>
          <select v-model="pageSize" class="select">
            <option value="A4">A4</option>
            <option value="A3">A3</option>
            <option value="A5">A5</option>
            <option value="letter">Letter</option>
          </select>
        </div>

        <div class="option-group">
          <label>缩放模式:</label>
          <select v-model="fitMode" class="select">
            <option value="fit">适应 (fit)</option>
            <option value="contain">包含 (contain)</option>
            <option value="cover">覆盖 (cover)</option>
            <option value="stretch">拉伸 (stretch)</option>
          </select>
        </div>
      </div>

      <div class="actions">
        <button
          class="btn btn-secondary"
          type="button"
          @click="() => fileInput?.click()"
        >
          + 添加更多图片
        </button>
        <button
          class="btn btn-danger"
          type="button"
          @click="clearFiles"
        >
          清除所有
        </button>
        <button
          class="btn btn-primary"
          type="button"
          @click="handleConvert"
          :disabled="selectedFiles.length === 0"
        >
          🚀 添加到转换队列
        </button>
      </div>
    </div>

    <!-- 任务列表 -->
    <div v-if="tasks.length > 0" class="tasks-section">
      <div class="tasks-header">
        <h3>📋 转换任务</h3>
        <div class="tasks-summary">
          共 {{ metrics.totalTasks }} 个
          <span v-if="metrics.completedTasks > 0" class="summary-completed">
            · {{ metrics.completedTasks }} 已完成
          </span>
          <span v-if="metrics.failedTasks > 0" class="summary-failed">
            · {{ metrics.failedTasks }} 失败
          </span>
        </div>
        <div class="tasks-actions">
          <button
            v-if="metrics.failedTasks > 0"
            class="btn btn-sm btn-warning"
            @click="retryFailed"
            :disabled="isProcessing"
          >
            🔄 重试失败
          </button>
          <button
            class="btn btn-sm btn-secondary"
            @click="clearTasks"
            :disabled="isProcessing"
          >
            🗑️ 清空
          </button>
        </div>
      </div>

      <div class="tasks-list">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="task-item"
          :class="[`status-${task.status}`]"
        >
          <div class="task-header">
            <div class="task-info">
              <span class="status-icon">{{ getStatusIcon(task.status) }}</span>
              <span class="task-name">{{ task.name }}</span>
              <span class="task-count">({{ task.files.length }}张)</span>
              <span
                class="status-badge"
                :style="{ backgroundColor: getStatusColor(task.status) }"
              >
                {{ getStatusText(task.status) }}
              </span>
            </div>
            <div class="task-actions">
              <span v-if="task.status !== 'pending'" class="task-duration">
                {{ getTaskDuration(task) }}s
              </span>
              <button
                v-if="task.status === 'completed' && task.result"
                class="btn-icon btn-download"
                title="下载"
                @click="downloadResult(task)"
              >
                ⬇️
              </button>
              <button
                v-if="task.status !== 'processing'"
                class="btn-icon btn-remove"
                title="移除"
                @click="removeTask(task.id)"
              >
                ✕
              </button>
            </div>
          </div>

          <!-- 进度条 -->
          <div v-if="task.status === 'processing' || task.progress > 0" class="progress-bar">
            <div
              class="progress-fill"
              :style="{
                width: task.progress + '%',
                backgroundColor: getStatusColor(task.status)
              }"
            >
              <span v-if="task.progress > 10" class="progress-text">
                {{ task.progress }}%
              </span>
            </div>
          </div>

          <!-- 错误信息 -->
          <div v-if="task.error" class="task-error">
            {{ task.error }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.converter {
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

.file-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.list-size {
  font-size: 12px;
  color: #999;
}

.files {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 8px;
  background: white;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 6px;
  font-size: 13px;
}

.file-item:last-child {
  margin-bottom: 0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.file-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #333;
}

.file-size {
  color: #999;
  white-space: nowrap;
  margin-left: 8px;
  flex-shrink: 0;
}

.remove-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: #fee2e2;
  border: none;
  border-radius: 4px;
  color: #dc2626;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  flex-shrink: 0;
}

.remove-btn:hover {
  background: #fecaca;
}

.options {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.option-group {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.option-group label {
  font-weight: 500;
  color: #333;
}

.select {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  background: white;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.select:hover,
.select:focus {
  border-color: #667eea;
  outline: none;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  flex-wrap: wrap;
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

.btn-danger {
  background: #fee2e2;
  color: #dc2626;
}

.btn-danger:hover:not(:disabled) {
  background: #fecaca;
}

.btn-warning {
  background: #faad14;
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background: #d48806;
}

/* 任务列表样式 */
.tasks-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.tasks-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.tasks-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.tasks-summary {
  font-size: 13px;
  color: #666;
  flex: 1;
}

.summary-completed {
  color: #52c41a;
}

.summary-failed {
  color: #ff4d4f;
}

.tasks-actions {
  display: flex;
  gap: 8px;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.task-item {
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 12px 16px;
  transition: all 0.2s ease;
}

.task-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.task-item.status-processing {
  border-color: #1890ff;
  background: #f0f7ff;
}

.task-item.status-completed {
  border-color: #52c41a;
  background: #f6ffed;
}

.task-item.status-failed {
  border-color: #ff4d4f;
  background: #fff1f0;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.task-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.status-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.task-name {
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-count {
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 10px;
  color: white;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.task-duration {
  font-size: 12px;
  color: #666;
  font-family: monospace;
}

.btn-icon {
  width: 28px;
  height: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.btn-download {
  background: #e6f7ff;
  color: #1890ff;
}

.btn-download:hover {
  background: #bae7ff;
}

.btn-remove {
  background: #fff1f0;
  color: #ff4d4f;
}

.btn-remove:hover {
  background: #ffccc7;
}

.progress-bar {
  height: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  margin-top: 8px;
}

.progress-fill {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: width 0.3s ease;
  position: relative;
}

.progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  animation: shimmer 2s infinite;
}

.progress-text {
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  z-index: 1;
  position: relative;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.task-error {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fff1f0;
  border-radius: 4px;
  font-size: 12px;
  color: #ff4d4f;
}

@media (max-width: 768px) {
  .options {
    flex-direction: column;
    gap: 12px;
  }

  .actions {
    flex-direction: column;
  }

  .actions .btn {
    width: 100%;
  }

  .tasks-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
