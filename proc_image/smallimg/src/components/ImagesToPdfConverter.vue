<script setup lang="ts">
import { ref } from "vue";
import { useMultiImageToPdf } from "@/composables/useMultiImageToPdf";
import { isValidImageFile, isValidFileSize } from "@/utils/image-utils";

const emit = defineEmits<{
  success: [{ taskId: string; filename: string; downloadUrl: string }]
  error: [message: string]
}>();

const { converting, progress, error, convertImagesToPdf } = useMultiImageToPdf();

const isDragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFiles = ref<File[]>([]);
const pageSize = ref<"A4" | "A3" | "A5" | "letter">("A4");
const fitMode = ref<"fit" | "contain" | "cover" | "stretch">("fit");

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files));
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

const handleConvert = async () => {
  if (selectedFiles.value.length === 0) {
    emit("error", "请至少选择一张图片");
    return;
  }

  try {
    const result = await convertImagesToPdf(selectedFiles.value, {
      page_size: pageSize.value,
      fit_mode: fitMode.value,
    });
    emit("success", result);
    clearFiles();
  } catch (err) {
    const message = err instanceof Error ? err.message : "转换失败";
    emit("error", message);
  }
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
</script>

<template>
  <div class="converter">
    <div
      v-if="selectedFiles.length === 0"
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
        <div class="icon">🖼️</div>
        <div class="title">点击或拖拽上传图片</div>
        <div class="subtitle">支持 JPEG, PNG, BMP, GIF, TIFF, WebP</div>
        <div class="hint">也可以使用 Ctrl+V 粘贴图片（支持多张）</div>
      </div>
    </div>

    <div v-else class="file-list">
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
          :disabled="converting"
        >
          + 添加更多图片
        </button>
        <button
          class="btn btn-danger"
          type="button"
          @click="clearFiles"
          :disabled="converting"
        >
          清除所有
        </button>
        <button
          class="btn btn-primary"
          type="button"
          @click="handleConvert"
          :disabled="converting || selectedFiles.length === 0"
        >
          <span v-if="!converting">🚀 转换为 PDF</span>
          <span v-else>转换中... {{ Math.round(progress) }}%</span>
        </button>
      </div>
    </div>

    <div v-if="converting" class="progress-bar">
      <div class="progress" :style="{ width: progress + '%' }"></div>
    </div>

    <div v-if="error" class="error-message">
      ⚠️ {{ error }}
    </div>
  </div>
</template>

<style scoped>
.converter {
  background: white;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.uploader {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 60px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #fafafa;
}

.uploader:hover {
  border-color: #42b883;
  background-color: #f0f9ff;
}

.uploader.dragging {
  border-color: #42b883;
  background-color: #e6f7ff;
  transform: scale(1.02);
}

.uploader-content {
  pointer-events: none;
}

.icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.hint {
  font-size: 12px;
  color: #999;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.list-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.list-size {
  font-size: 12px;
  color: #999;
}

.files {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 8px;
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
}

.file-name {
  flex: 1;
  word-break: break-all;
  color: #333;
}

.file-size {
  color: #999;
  white-space: nowrap;
  margin-left: 8px;
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
  font-size: 16px;
  flex-shrink: 0;
}

.remove-btn:hover {
  background: #fecaca;
}

.options {
  display: flex;
  gap: 24px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 6px;
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
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #5568d3;
  transform: translateY(-2px);
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

.progress-bar {
  height: 4px;
  background: #eee;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 12px;
}

.progress {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
}

.error-message {
  margin-top: 12px;
  padding: 12px;
  background: #fee2e2;
  border-left: 4px solid #dc2626;
  border-radius: 4px;
  color: #b91c1c;
  font-size: 13px;
}
</style>
