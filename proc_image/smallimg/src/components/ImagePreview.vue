<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ImageItem } from '@/types'
import { formatFileSize } from '@/utils/image-utils'

const props = defineProps<{
  item: ImageItem | null
}>()

const emit = defineEmits<{
  close: []
}>()

const showOriginal = ref(false)

const originalUrl = computed(() => {
  if (!props.item?.file) return ''
  return URL.createObjectURL(props.item.file)
})

const processedUrl = computed(() => {
  return props.item?.result?.url || ''
})

const currentUrl = computed(() => {
  return showOriginal.value ? originalUrl.value : processedUrl.value
})

const handleClose = () => {
  emit('close')
}

const handleBackdropClick = (e: MouseEvent) => {
  if (e.target === e.currentTarget) {
    handleClose()
  }
}
</script>

<template>
  <Transition name="modal">
    <div v-if="item && item.result" class="modal-backdrop" @click="handleBackdropClick">
      <div class="modal-content">
        <div class="modal-header">
          <h3>图片预览</h3>
          <button class="btn-close" @click="handleClose">✕</button>
        </div>

        <div class="modal-body">
          <div class="preview-container">
            <img :src="currentUrl" :alt="item.file.name" class="preview-image" />
          </div>

          <div class="toggle-container">
            <label class="toggle">
              <input v-model="showOriginal" type="checkbox" />
              <span class="toggle-label">
                {{ showOriginal ? '显示原图' : '显示处理后' }}
              </span>
            </label>
          </div>

          <div class="info-container">
            <div class="info-section">
              <h4>原始图片</h4>
              <p>尺寸: {{ item.result.originalWidth }}×{{ item.result.originalHeight }}</p>
              <p>大小: {{ formatFileSize(item.result.originalSize) }}</p>
            </div>
            <div class="info-section">
              <h4>处理后</h4>
              <p>尺寸: {{ item.result.processedWidth }}×{{ item.result.processedHeight }}</p>
              <p>大小: {{ formatFileSize(item.result.processedSize) }}</p>
              <p class="compression">压缩率: {{ item.result.compressionRatio }}%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: white;
  border-radius: 12px;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-close:hover {
  background-color: #f5f5f5;
  color: #333;
}

.modal-body {
  padding: 20px;
}

.preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f5f5;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  min-height: 300px;
}

.preview-image {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  border-radius: 4px;
}

.toggle-container {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.toggle {
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.toggle input[type="checkbox"] {
  margin-right: 8px;
  cursor: pointer;
}

.toggle-label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.info-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding-top: 20px;
  border-top: 1px solid #e0e0e0;
}

.info-section h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #333;
}

.info-section p {
  margin: 4px 0;
  font-size: 14px;
  color: #666;
}

.compression {
  color: #52c41a;
  font-weight: 600;
}

/* 过渡动画 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform 0.3s ease;
}

.modal-enter-from .modal-content,
.modal-leave-to .modal-content {
  transform: scale(0.9);
}

@media (max-width: 768px) {
  .info-container {
    grid-template-columns: 1fr;
  }
}
</style>

