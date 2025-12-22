<script setup lang="ts">
import { ref, computed } from "vue";

const emit = defineEmits<{
  (e: "error", message: string): void;
}>();

// API 基础地址
const API_BASE = "http://localhost:8000";

// 状态
const selectedFile = ref<File | null>(null);
const isProcessing = ref(false);
const processingProgress = ref("");
const result = ref<{
  success: boolean;
  task_id: string;
  filename: string;
  output_filename: string;
  download_url: string;
  markdown_content?: string;
  metadata: {
    original_size: number;
    output_size: number;
    markdown_length: number;
    processing_time: number;
  };
} | null>(null);

// 选项
const options = ref({
  title: "",
  include_markdown: true,
  font_name: "Microsoft YaHei",
  font_size: 11,
});

// 预览图片URL
const previewUrl = computed(() => {
  if (selectedFile.value) {
    return URL.createObjectURL(selectedFile.value);
  }
  return null;
});

// 格式化文件大小
const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
};

// 处理文件选择
const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    // 检查文件类型
    const allowedTypes = [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowedTypes.includes(ext)) {
      emit("error", `不支持的文件格式: ${ext}`);
      return;
    }
    selectedFile.value = file;
    result.value = null;
  }
};

// 处理拖拽
const handleDrop = (event: DragEvent) => {
  event.preventDefault();
  const files = event.dataTransfer?.files;
  if (files && files.length > 0) {
    const file = files[0];
    const allowedTypes = [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowedTypes.includes(ext)) {
      emit("error", `不支持的文件格式: ${ext}`);
      return;
    }
    selectedFile.value = file;
    result.value = null;
  }
};

const handleDragOver = (event: DragEvent) => {
  event.preventDefault();
};

// 开始转换
const startConvert = async () => {
  if (!selectedFile.value) {
    emit("error", "请先选择图片文件");
    return;
  }

  isProcessing.value = true;
  processingProgress.value = "正在上传图片...";
  result.value = null;

  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    formData.append("options", JSON.stringify(options.value));

    processingProgress.value = "正在进行OCR识别并生成Word...";

    const response = await fetch(`${API_BASE}/api/v1/image/to-word`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail?.message || errorData.detail || "转换失败");
    }

    const data = await response.json();
    result.value = data;
    processingProgress.value = "转换完成！";
  } catch (error: any) {
    emit("error", error.message || "转换失败");
    processingProgress.value = "";
  } finally {
    isProcessing.value = false;
  }
};

// 下载Word文档
const downloadWord = () => {
  if (result.value?.download_url) {
    window.open(`${API_BASE}${result.value.download_url}`, "_blank");
  }
};

// 清空选择
const clearSelection = () => {
  selectedFile.value = null;
  result.value = null;
  processingProgress.value = "";
};
</script>

<template>
  <div class="image-to-word">
    <div class="section-header">
      <h2>📝 图片 → Word</h2>
      <p class="desc">通过OCR识别图片内容，转换为格式化的Word文档，保持表格、标题、列表等格式</p>
    </div>

    <!-- 选项设置 -->
    <div class="options-panel">
      <div class="option-item">
        <label>文档标题（可选）</label>
        <input
          v-model="options.title"
          type="text"
          placeholder="留空则不添加标题"
          :disabled="isProcessing"
        />
      </div>
      <div class="option-item">
        <label>字体</label>
        <select v-model="options.font_name" :disabled="isProcessing">
          <option value="Microsoft YaHei">微软雅黑</option>
          <option value="SimSun">宋体</option>
          <option value="SimHei">黑体</option>
          <option value="KaiTi">楷体</option>
          <option value="Arial">Arial</option>
        </select>
      </div>
      <div class="option-item">
        <label>字号</label>
        <input
          v-model.number="options.font_size"
          type="number"
          min="8"
          max="72"
          :disabled="isProcessing"
        />
      </div>
      <div class="option-item checkbox">
        <label>
          <input
            v-model="options.include_markdown"
            type="checkbox"
            :disabled="isProcessing"
          />
          返回Markdown内容（用于预览）
        </label>
      </div>
    </div>

    <!-- 文件上传区域 -->
    <div
      class="upload-area"
      :class="{ 'has-file': selectedFile, processing: isProcessing }"
      @drop="handleDrop"
      @dragover="handleDragOver"
    >
      <template v-if="!selectedFile">
        <div class="upload-icon">🖼️</div>
        <p class="upload-text">点击或拖拽上传图片</p>
        <p class="upload-hint">支持 JPG、PNG、TIFF、BMP、WebP 格式</p>
        <input
          type="file"
          accept=".jpg,.jpeg,.png,.tiff,.tif,.bmp,.webp"
          @change="handleFileSelect"
          :disabled="isProcessing"
        />
      </template>

      <template v-else>
        <div class="file-preview">
          <img v-if="previewUrl" :src="previewUrl" alt="预览" class="preview-image" />
          <div class="file-info">
            <p class="file-name">{{ selectedFile.name }}</p>
            <p class="file-size">{{ formatSize(selectedFile.size) }}</p>
          </div>
          <button class="clear-btn" @click="clearSelection" :disabled="isProcessing">✕</button>
        </div>
      </template>
    </div>

    <!-- 操作按钮 -->
    <div class="actions">
      <button
        class="btn btn-primary"
        @click="startConvert"
        :disabled="!selectedFile || isProcessing"
      >
        <span v-if="isProcessing">⏳ 处理中...</span>
        <span v-else>🚀 开始转换</span>
      </button>
    </div>

    <!-- 处理进度 -->
    <div v-if="processingProgress" class="progress-info">
      <div class="progress-bar">
        <div class="progress-fill" :class="{ complete: result }"></div>
      </div>
      <p>{{ processingProgress }}</p>
    </div>

    <!-- 转换结果 -->
    <div v-if="result" class="result-panel">
      <h3>✅ 转换完成</h3>
      
      <div class="result-stats">
        <div class="stat-item">
          <span class="label">原始大小</span>
          <span class="value">{{ formatSize(result.metadata.original_size) }}</span>
        </div>
        <div class="stat-item">
          <span class="label">Word大小</span>
          <span class="value">{{ formatSize(result.metadata.output_size) }}</span>
        </div>
        <div class="stat-item">
          <span class="label">处理时间</span>
          <span class="value">{{ result.metadata.processing_time }}s</span>
        </div>
        <div class="stat-item">
          <span class="label">识别字数</span>
          <span class="value">{{ result.metadata.markdown_length }}</span>
        </div>
      </div>

      <div class="result-actions">
        <button class="btn btn-success" @click="downloadWord">
          📥 下载 Word 文档
        </button>
      </div>

      <!-- Markdown 预览 -->
      <div v-if="result.markdown_content" class="markdown-preview">
        <h4>📄 识别内容预览</h4>
        <pre class="markdown-content">{{ result.markdown_content }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-to-word {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.section-header {
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: #1f2937;
}

.section-header .desc {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.options-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 12px;
  margin-bottom: 20px;
}

.option-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.option-item label {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}

.option-item input[type="text"],
.option-item input[type="number"],
.option-item select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  min-width: 150px;
}

.option-item.checkbox {
  flex-direction: row;
  align-items: center;
}

.option-item.checkbox label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.upload-area {
  position: relative;
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  transition: all 0.2s ease;
  cursor: pointer;
  background: #fafafa;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f5f3ff;
}

.upload-area.has-file {
  border-style: solid;
  border-color: #667eea;
  padding: 20px;
}

.upload-area.processing {
  opacity: 0.7;
  pointer-events: none;
}

.upload-area input[type="file"] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 16px;
  color: #374151;
  margin: 0 0 8px 0;
}

.upload-hint {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 16px;
}

.preview-image {
  width: 120px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.file-info {
  flex: 1;
  text-align: left;
}

.file-name {
  font-size: 15px;
  font-weight: 500;
  color: #1f2937;
  margin: 0 0 4px 0;
  word-break: break-all;
}

.file-size {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.clear-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f3f4f6;
  color: #6b7280;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s ease;
}

.clear-btn:hover {
  background: #fee2e2;
  color: #dc2626;
}

.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn {
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.btn-success:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

.progress-info {
  margin-top: 20px;
  text-align: center;
}

.progress-bar {
  height: 6px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  width: 60%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 999px;
  animation: progress-animation 1.5s ease-in-out infinite;
}

.progress-fill.complete {
  width: 100%;
  animation: none;
  background: #10b981;
}

@keyframes progress-animation {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}

.progress-info p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.result-panel {
  margin-top: 24px;
  padding: 20px;
  background: #f0fdf4;
  border-radius: 12px;
  border: 1px solid #bbf7d0;
}

.result-panel h3 {
  margin: 0 0 16px 0;
  font-size: 18px;
  color: #166534;
}

.result-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  background: white;
  padding: 12px;
  border-radius: 8px;
  text-align: center;
}

.stat-item .label {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.stat-item .value {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.result-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.markdown-preview {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #bbf7d0;
}

.markdown-preview h4 {
  margin: 0 0 12px 0;
  font-size: 15px;
  color: #374151;
}

.markdown-content {
  background: white;
  padding: 16px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  border: 1px solid #e5e7eb;
}

@media (max-width: 768px) {
  .options-panel {
    flex-direction: column;
  }
  
  .option-item input[type="text"],
  .option-item input[type="number"],
  .option-item select {
    min-width: 100%;
  }
  
  .file-preview {
    flex-direction: column;
    text-align: center;
  }
  
  .file-info {
    text-align: center;
  }
}
</style>
