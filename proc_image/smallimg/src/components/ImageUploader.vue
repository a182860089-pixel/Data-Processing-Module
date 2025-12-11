<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { isValidImageFile, isValidFileSize } from '@/utils/image-utils'

const emit = defineEmits<{
  upload: [files: File[]]
  error: [message: string]
}>()

const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// 处理文件选择
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files))
  }
}

// 处理拖拽进入
const handleDragEnter = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = true
}

// 处理拖拽离开
const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
}

// 处理拖拽悬停
const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
}

// 处理文件拖放
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

  files.forEach(file => {
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
    emit('upload', validFiles)
  }
}

// 点击上传区域
const handleClick = () => {
  fileInput.value?.click()
}

// 监听粘贴事件
onMounted(() => {
  window.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  window.removeEventListener('paste', handlePaste)
})
</script>

<template>
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
      <div class="subtitle">支持 JPEG, PNG, BMP, GIF, TIFF, WebP</div>
      <div class="hint">也可以使用 Ctrl+V 粘贴图片</div>
    </div>
  </div>
</template>

<style scoped>
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
</style>

