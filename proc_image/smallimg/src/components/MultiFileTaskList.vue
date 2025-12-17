<script setup lang="ts">
import type { FileTask, ProcessorMetrics } from '@/composables/useMultiFileProcessor'

const props = defineProps<{
  tasks: FileTask[]
  metrics: ProcessorMetrics
  isProcessing: boolean
  showMetrics?: boolean
  formatFileSize: (bytes: number) => string
  getTaskDuration: (task: FileTask) => number
}>()

const emit = defineEmits<{
  remove: [taskId: string]
  start: []
  stop: []
  clear: []
  retryFailed: []
  download: [task: FileTask]
}>()

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: '#999999',
    processing: '#1890ff',
    completed: '#52c41a',
    failed: '#ff4d4f',
  }
  return colors[status] || '#999999'
}

const getStatusIcon = (status: string) => {
  const icons: Record<string, string> = {
    pending: '⏳',
    processing: '⚙️',
    completed: '✅',
    failed: '❌',
  }
  return icons[status] || '❓'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return texts[status] || status
}
</script>

<template>
  <div class="task-list-container">
    <!-- 控制按钮 -->
    <div v-if="tasks.length > 0" class="control-bar">
      <div class="task-summary">
        已添加 {{ tasks.length }} 个文件
        <span v-if="metrics.completedTasks > 0" class="summary-completed">
          · {{ metrics.completedTasks }} 已完成
        </span>
        <span v-if="metrics.failedTasks > 0" class="summary-failed">
          · {{ metrics.failedTasks }} 失败
        </span>
      </div>
      <div class="control-buttons">
        <button
          v-if="!isProcessing"
          class="btn btn-primary"
          :disabled="tasks.filter(t => t.status === 'pending').length === 0"
          @click="emit('start')"
        >
          🚀 开始处理
        </button>
        <button
          v-else
          class="btn btn-danger"
          @click="emit('stop')"
        >
          ⏹️ 停止
        </button>
        <button
          v-if="metrics.failedTasks > 0"
          class="btn btn-warning"
          :disabled="isProcessing"
          @click="emit('retryFailed')"
        >
          🔄 重试失败
        </button>
        <button
          class="btn btn-secondary"
          :disabled="isProcessing"
          @click="emit('clear')"
        >
          🗑️ 清空
        </button>
      </div>
    </div>

    <!-- 指标面板 -->
    <div v-if="showMetrics && tasks.length > 0" class="metrics-panel">
      <div class="metric-item">
        <span class="metric-label">总数</span>
        <span class="metric-value">{{ metrics.totalTasks }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">完成</span>
        <span class="metric-value success">{{ metrics.completedTasks }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">失败</span>
        <span class="metric-value danger">{{ metrics.failedTasks }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">总耗时</span>
        <span class="metric-value">{{ Math.round(metrics.totalDuration / 1000) }}s</span>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="tasks-list">
      <TransitionGroup name="task">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="task-item"
          :class="[`status-${task.status}`]"
        >
          <div class="task-header">
            <div class="task-info">
              <span class="status-icon">{{ getStatusIcon(task.status) }}</span>
              <span class="task-name" :title="task.name">{{ task.name }}</span>
              <span class="task-size">({{ formatFileSize(task.size) }})</span>
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
                @click="emit('download', task)"
              >
                ⬇️
              </button>
              <button
                v-if="task.status !== 'processing'"
                class="btn-icon btn-remove"
                title="移除"
                @click="emit('remove', task.id)"
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
      </TransitionGroup>
    </div>

    <!-- 空状态 -->
    <div v-if="tasks.length === 0" class="empty-state">
      <p>暂无任务</p>
    </div>
  </div>
</template>

<style scoped>
.task-list-container {
  margin-top: 16px;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 12px;
}

.task-summary {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.summary-completed {
  color: #52c41a;
}

.summary-failed {
  color: #ff4d4f;
}

.control-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  background: #ff4d4f;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #d9363e;
}

.btn-warning {
  background: #faad14;
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background: #d48806;
}

.metrics-panel {
  display: flex;
  gap: 16px;
  padding: 12px 16px;
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.metric-label {
  font-size: 12px;
  color: #999;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  color: #333;
  font-family: monospace;
}

.metric-value.success {
  color: #52c41a;
}

.metric-value.danger {
  color: #ff4d4f;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
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
  max-width: 200px;
}

.task-size {
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

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
  background: #fafafa;
  border-radius: 8px;
}

/* 过渡动画 */
.task-enter-active,
.task-leave-active {
  transition: all 0.3s ease;
}

.task-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.task-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.task-move {
  transition: transform 0.3s ease;
}

@media (max-width: 768px) {
  .control-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .control-buttons {
    justify-content: center;
  }

  .task-name {
    max-width: 120px;
  }
}
</style>
