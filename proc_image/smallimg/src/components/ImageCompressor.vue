<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useMultiFileProcessor, type FileTask } from '@/composables/useMultiFileProcessor'
import { isValidImageFile, isValidFileSize } from '@/utils/image-utils'
import { generateWebPFileName } from '@/utils/file-utils'
import MultiFileTaskList from './MultiFileTaskList.vue'
import type { ProcessedImage } from '@/types'

const API_BASE_URL =
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  import.meta.env.VITE_PDF_API_BASE_URL ||
  'http://localhost:8000'

const emit = defineEmits<{
  error: [message: string]
}>()

// 压缩选项
const quality = ref(92)
const maxWidth = ref(1920)
const maxHeight = ref(1080)

// 图片压缩处理函数
const compressImage = async (
  file: File,
  onProgress?: (progress: number) => void
): Promise<ProcessedImage> => {
  onProgress?.(5)

  const formData = new FormData()
  formData.append('file', file)

  const payloadOptions = {
    quality: quality.value,
    max_width: maxWidth.value,
    max_height: maxHeight.value,
  }
  formData.append('options', JSON.stringify(payloadOptions))

  onProgress?.(15)

  const resp = await fetch(`${API_BASE_URL}/api/v1/image/compress`, {
    method: 'POST',
    body: formData,
  })

  if (!resp.ok) {
    let detail = ''
    try {
      const data = await resp.json()
      detail =
        (data?.detail && (data.detail.message || data.detail.details || data.detail)) ||
        JSON.stringify(data)
    } catch {
      detail = resp.statusText
    }
    throw new Error(`图片压缩失败 (${resp.status}): ${detail}`)
  }

  const data = await resp.json()
  if (!data.success) {
    throw new Error(data.message || '图片压缩失败')
  }

  onProgress?.(60)

  // 下载压缩后的图片
  const downloadUrl = data.download_url.startsWith('http')
    ? data.download_url
    : `${API_BASE_URL}${data.download_url}`

  const imgResp = await fetch(downloadUrl)
  if (!imgResp.ok) {
    throw new Error(`下载压缩图片失败 (${imgResp.status})`)
  }

  onProgress?.(85)

  const blob = await imgResp.blob()
  if (!blob || blob.size === 0) {
    throw new Error('下载的文件为空')
  }

  const parseDimensions = (dim: string): { width: number; height: number } => {
    const [w, h] = dim.split('x').map((v) => parseInt(v.trim(), 10))
    if (!Number.isFinite(w) || !Number.isFinite(h)) {
      return { width: 0, height: 0 }
    }
    return { width: w, height: h }
  }

  const { original_size, output_size, compression_ratio, original_dimensions, output_dimensions } =
    data.metadata
  const originalDims = parseDimensions(original_dimensions)
  const outputDims = parseDimensions(output_dimensions)

  onProgress?.(100)

  return {
    blob,
    url: URL.createObjectURL(blob),
    originalFile: file,
    originalSize: original_size || file.size,
    originalWidth: originalDims.width,
    originalHeight: originalDims.height,
    processedSize: output_size,
    processedWidth: outputDims.width,
    processedHeight: outputDims.height,
    compressionRatio: Math.round(compression_ratio),
    fileName: data.output_filename || generateWebPFileName(file.name),
  }
}

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
} = useMultiFileProcessor<ProcessedImage>(compressImage, { concurrency: 3 })

const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// 处理文件选择
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files))
    target.value = '' // 清空以允许重复选择同一文件
  }
}

// 处理拖拽
const handleDragEnter = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
}

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false

  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    handleFiles(Array.from(e.dataTransfer.files))
  }
}

// 处理粘贴
const handlePaste = (e: ClipboardEvent) => {
  const items = e.clipboardData?.items
  if (!items) return

  const files: File[] = []
  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf('image') !== -1) {
      const file = items[i].getAsFile()
      if (file) files.push(file)
    }
  }

  if (files.length > 0) {
    handleFiles(files)
  }
}

// 处理文件
const handleFiles = (files: File[]) => {
  const validFiles: File[] = []
  const errors: string[] = []

  files.forEach((file) => {
    if (!isValidImageFile(file)) {
      errors.push(`${file.name}: 不支持的文件格式`)
    } else if (!isValidFileSize(file)) {
      errors.push(`${file.name}: 文件大小超过50MB`)
    } else {
      validFiles.push(file)
    }
  })

  if (errors.length > 0) {
    emit('error', errors.join('\n'))
  }

  if (validFiles.length > 0) {
    addFiles(validFiles)
  }
}

// 点击上传区域
const handleClick = () => {
  fileInput.value?.click()
}

// 下载处理结果
const handleDownload = (task: FileTask<ProcessedImage>) => {
  if (!task.result) return

  const link = document.createElement('a')
  link.href = task.result.url
  link.download = task.result.fileName
  link.click()
}

// 监听粘贴事件
onMounted(() => {
  window.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  window.removeEventListener('paste', handlePaste)
  // 清理 blob URLs
  tasks.value.forEach((task) => {
    if (task.result?.url) {
      URL.revokeObjectURL(task.result.url)
    }
  })
})
</script>

<template>
  <div class="image-compressor">
    <div class="card">
      <h2 class="card-title">📷 图片压缩</h2>
      <p class="card-subtitle">支持批量上传图片，异步压缩处理</p>

      <!-- 压缩选项 -->
      <div class="options-panel">
        <div class="option-item">
          <label>质量 ({{ quality }}%)</label>
          <input type="range" v-model.number="quality" min="50" max="100" step="1" />
        </div>
        <div class="option-item">
          <label>最大宽度</label>
          <input type="number" v-model.number="maxWidth" min="100" max="4096" step="100" />
        </div>
        <div class="option-item">
          <label>最大高度</label>
          <input type="number" v-model.number="maxHeight" min="100" max="4096" step="100" />
        </div>
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
          accept="image/*"
          multiple
          style="display: none"
          @change="handleFileSelect"
        />

        <div class="uploader-content">
          <div class="icon">📁</div>
          <div class="title">点击或拖拽上传图片</div>
          <div class="subtitle">支持 JPEG, PNG, BMP, GIF, TIFF, WebP（可多选）</div>
          <div class="hint">也可以使用 Ctrl+V 粘贴图片</div>
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
    </div>
  </div>
</template>

<style scoped>
.image-compressor {
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

.options-panel {
  display: flex;
  gap: 24px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.option-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 120px;
}

.option-item label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.option-item input[type="range"] {
  width: 150px;
  cursor: pointer;
}

.option-item input[type="number"] {
  width: 100px;
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
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
  margin-bottom: 6px;
}

.hint {
  font-size: 12px;
  color: #999;
}

@media (max-width: 768px) {
  .options-panel {
    flex-direction: column;
    gap: 12px;
  }

  .option-item input[type="range"] {
    width: 100%;
  }
}
</style>
