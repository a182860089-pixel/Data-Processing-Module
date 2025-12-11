<script setup lang="ts">
import type { ImageItem } from '@/types'
import { formatFileSize } from '@/utils/image-utils'
import { downloadFile } from '@/utils/file-utils'

defineProps<{
  items: ImageItem[]
}>()

const emit = defineEmits<{
  remove: [id: string]
  preview: [item: ImageItem]
}>()

const handleDownload = (item: ImageItem) => {
  if (item.result) {
    downloadFile(item.result.blob, item.result.fileName)
  }
}

const handleRemove = (id: string) => {
  emit('remove', id)
}

const handlePreview = (item: ImageItem) => {
  if (item.result) {
    emit('preview', item)
  }
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[status] || status
}

const getStatusClass = (status: string) => {
  return `status-${status}`
}
</script>

<template>
  <div class="processing-list">
    <div v-if="items.length === 0" class="empty">
      <p>暂无图片，请上传图片开始处理</p>
    </div>

    <div v-for="item in items" :key="item.id" class="item">
      <div class="item-header">
        <div class="file-info">
          <div class="file-name">📷 {{ item.file.name }}</div>
          <div class="status" :class="getStatusClass(item.status)">
            {{ getStatusText(item.status) }}
          </div>
        </div>
        <button
          v-if="item.status === 'completed' || item.status === 'failed'"
          class="btn-remove"
          @click="handleRemove(item.id)"
        >
          ✕
        </button>
      </div>

      <div v-if="item.status === 'processing'" class="progress-bar">
        <div class="progress-fill" :style="{ width: item.progress + '%' }"></div>
        <div class="progress-text">{{ item.progress }}%</div>
      </div>

      <div v-if="item.error" class="error-message">
        ❌ {{ item.error }}
      </div>

      <div v-if="item.result" class="result">
        <div class="result-info">
          <div class="info-row">
            <span class="label">原始:</span>
            <span class="value">
              {{ item.result.originalWidth }}×{{ item.result.originalHeight }}
              ({{ formatFileSize(item.result.originalSize) }})
            </span>
          </div>
          <div class="info-row">
            <span class="label">处理后:</span>
            <span class="value">
              {{ item.result.processedWidth }}×{{ item.result.processedHeight }}
              ({{ formatFileSize(item.result.processedSize) }})
            </span>
          </div>
          <div class="info-row">
            <span class="label">压缩率:</span>
            <span class="value compression">{{ item.result.compressionRatio }}%</span>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-preview" @click="handlePreview(item)">
            预览
          </button>
          <button class="btn btn-download" @click="handleDownload(item)">
            下载
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.processing-list {
  margin-top: 30px;
}

.empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

.item {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  transition: box-shadow 0.3s ease;
}

.item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.file-info {
  flex: 1;
}

.file-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-pending {
  background-color: #f0f0f0;
  color: #666;
}

.status-processing {
  background-color: #e6f7ff;
  color: #1890ff;
}

.status-completed {
  background-color: #f6ffed;
  color: #52c41a;
}

.status-failed {
  background-color: #fff1f0;
  color: #ff4d4f;
}

.btn-remove {
  background: none;
  border: none;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-remove:hover {
  background-color: #f5f5f5;
  color: #ff4d4f;
}

.progress-bar {
  position: relative;
  height: 32px;
  background: linear-gradient(90deg, #f5f5f5, #fafafa);
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 12px;
  border: 1px solid #e8e8e8;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #42b883 0%, #52c41a 50%, #52c41a 100%);
  transition: width 0.15s linear;
  box-shadow: 0 0 12px rgba(66, 184, 131, 0.4);
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
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 13px;
  font-weight: 700;
  color: #333;
  text-shadow: 0 1px 1px rgba(255, 255, 255, 0.5);
  z-index: 10;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.error-message {
  padding: 12px;
  background-color: #fff1f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  color: #ff4d4f;
  font-size: 14px;
}

.result {
  border-top: 1px solid #f0f0f0;
  padding-top: 12px;
}

.result-info {
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 14px;
}

.label {
  color: #666;
  font-weight: 500;
}

.value {
  color: #333;
}

.compression {
  color: #52c41a;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 12px;
}

.btn {
  flex: 1;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-preview {
  background-color: #f0f0f0;
  color: #333;
}

.btn-preview:hover {
  background-color: #e0e0e0;
}

.btn-download {
  background-color: #42b883;
  color: white;
}

.btn-download:hover {
  background-color: #35a372;
}
</style>

