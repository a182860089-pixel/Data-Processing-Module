<script setup lang="ts">
import { ref, reactive, computed, onUnmounted } from 'vue'

interface FileTask {
  id: string
  name: string
  type: 'pdf' | 'image'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  pollCount: number
  startTime: number
  endTime?: number
  result?: any
  error?: string
  fileSize: number
}

interface BatchMetrics {
  totalTasks: number
  completedTasks: number
  failedTasks: number
  totalPolls: number
  successPolls: number
  failedPolls: number
  avgPollInterval: number
  totalDuration: number
}

const API_BASE_URL =
  (import.meta as any).env?.VITE_PDF_API_BASE_URL ||
  (import.meta as any).env?.VITE_IMAGE_API_BASE_URL ||
  'http://localhost:8000'

const tasks = reactive<FileTask[]>([])
const metrics = reactive<BatchMetrics>({
  totalTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
  totalPolls: 0,
  successPolls: 0,
  failedPolls: 0,
  avgPollInterval: 0,
  totalDuration: 0,
})

const pollIntervals = reactive<number[]>([])
const pollTimers = new Map<string, number>()

const selectedFiles = ref<FileList | null>(null)
const isProcessing = ref(false)

const generateTaskId = () => `task-${Date.now()}-${Math.random().toString(36).slice(2)}`

const createFileTask = (file: File): FileTask => {
  return {
    id: generateTaskId(),
    name: file.name,
    type: file.type.includes('pdf') ? 'pdf' : 'image',
    status: 'pending',
    progress: 0,
    pollCount: 0,
    startTime: Date.now(),
    fileSize: file.size,
  }
}

// 上传文件
const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  selectedFiles.value = input.files
}

// 开始处理文件
const startProcessing = async () => {
  if (!selectedFiles.value || selectedFiles.value.length === 0) {
    alert('请先选择文件')
    return
  }

  isProcessing.value = true
  tasks.length = 0
  pollIntervals.length = 0
  metrics.totalTasks = selectedFiles.value.length
  metrics.completedTasks = 0
  metrics.failedTasks = 0
  metrics.totalPolls = 0
  metrics.successPolls = 0
  metrics.failedPolls = 0

  const newTasks: FileTask[] = []
  for (let i = 0; i < selectedFiles.value.length; i++) {
    const file = selectedFiles.value[i]
    const task = createFileTask(file)
    newTasks.push(task)
    tasks.push(task)
  }

  // 并发处理多个文件（最多3个）
  const concurrency = 3
  for (let i = 0; i < newTasks.length; i += concurrency) {
    const batch = newTasks.slice(i, i + concurrency)
    await Promise.all(batch.map(task => processFileWithPolling(task)))
  }

  isProcessing.value = false
}

// 处理单个文件并轮询
const processFileWithPolling = async (task: FileTask) => {
  task.status = 'processing'
  task.startTime = Date.now()

  const file = Array.from(selectedFiles.value!).find(f => f.name === task.name)
  if (!file) return

  try {
    // 上传文件
    const formData = new FormData()
    formData.append('file', file)

    // PDF：走后端异步接口 + /status 轮询
    // Image：/image/compress 是同步接口，直接返回 download_url，不需要轮询
    const uploadResp = await fetch(
      task.type === 'pdf'
        ? `${API_BASE_URL}/api/v1/convert/async`
        : `${API_BASE_URL}/api/v1/image/compress`,
      {
        method: 'POST',
        body: formData,
      }
    )

    if (!uploadResp.ok) {
      throw new Error(`上传失败: ${uploadResp.status}`)
    }

    const uploadData = await uploadResp.json()

    if (task.type === 'pdf') {
      const taskId = uploadData.task_id || uploadData.taskId || uploadData.id
      if (!taskId) throw new Error('后端未返回 task_id')

      // 开始轮询
      startPollingTask(task, taskId)
      return
    }

    // image：同步完成
    task.status = 'completed'
    task.progress = 100
    task.result = uploadData
    task.endTime = Date.now()

    metrics.completedTasks++
    metrics.totalDuration = Math.max(
      metrics.totalDuration,
      (task.endTime ?? Date.now()) - task.startTime
    )
  } catch (error) {
    task.status = 'failed'
    task.error = error instanceof Error ? error.message : '处理失败'
    task.endTime = Date.now()
    metrics.failedTasks++
  }
}

// 轮询任务状态
const startPollingTask = (task: FileTask, taskId: string) => {
  const pollInterval = 1000 // 每秒轮询

  const timerId = window.setInterval(async () => {
    const pollStartTime = Date.now()

    try {
      // 查询任务状态
      const statusResp = await fetch(
        task.type === 'pdf'
          ? `${API_BASE_URL}/api/v1/status/${taskId}`
          : `${API_BASE_URL}/api/v1/image/status/${taskId}`
      )

      if (!statusResp.ok) {
        throw new Error(`查询失败: ${statusResp.status}`)
      }

      const statusData = await statusResp.json()
      task.progress = Math.min(statusData.progress || 0, 100)
      task.pollCount++
      metrics.totalPolls++
      metrics.successPolls++

      const pollDuration = Date.now() - pollStartTime
      pollIntervals.push(pollDuration)

      if (pollIntervals.length > 0) {
        metrics.avgPollInterval = Math.round(
          pollIntervals.reduce((a, b) => a + b, 0) / pollIntervals.length
        )
      }

      // 任务完成
      if (statusData.status === 'completed' || task.progress === 100) {
        task.status = 'completed'
        task.result = statusData.result || statusData.data
        task.endTime = Date.now()
        metrics.completedTasks++
        metrics.totalDuration = Math.max(
          metrics.totalDuration,
          task.endTime - task.startTime
        )
        clearInterval(timerId)
        pollTimers.delete(task.id)
      } else if (statusData.status === 'failed') {
        task.status = 'failed'
        task.error = statusData.error || '处理失败'
        task.endTime = Date.now()
        metrics.failedTasks++
        metrics.totalDuration = Math.max(
          metrics.totalDuration,
          task.endTime - task.startTime
        )
        clearInterval(timerId)
        pollTimers.delete(task.id)
      }
    } catch (error) {
      metrics.failedPolls++
      // 继续轮询，不中断
    }
  }, pollInterval)

  pollTimers.set(task.id, timerId)
}

// 停止所有处理
const stopAllProcessing = () => {
  pollTimers.forEach(timerId => clearInterval(timerId))
  pollTimers.clear()
  isProcessing.value = false
}

// 重置
const resetAll = () => {
  tasks.length = 0
  pollIntervals.length = 0
  metrics.totalTasks = 0
  metrics.completedTasks = 0
  metrics.failedTasks = 0
  metrics.totalPolls = 0
  metrics.successPolls = 0
  metrics.failedPolls = 0
  metrics.avgPollInterval = 0
  metrics.totalDuration = 0
  selectedFiles.value = null
  isProcessing.value = false
}

// 获取状态颜色
const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: '#999999',
    processing: '#1890ff',
    completed: '#52c41a',
    failed: '#ff4d4f',
  }
  return colors[status] || '#999999'
}

// 获取状态图标
const getStatusIcon = (status: string) => {
  const icons: Record<string, string> = {
    pending: '⏳',
    processing: '⚙️',
    completed: '✅',
    failed: '❌',
  }
  return icons[status] || '❓'
}

// 获取文件类型图标
const getFileTypeIcon = (type: string) => {
  return type === 'pdf' ? '📄' : '🖼️'
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

// 计算任务耗时
const getTaskDuration = (task: FileTask) => {
  const endTime = task.endTime || Date.now()
  return Math.round((endTime - task.startTime) / 1000)
}

const activeTaskCount = computed(() => tasks.filter(t => t.status === 'processing').length)

// 清理
onUnmounted(() => {
  pollTimers.forEach(timerId => clearInterval(timerId))
  pollTimers.clear()
})
</script>

<template>
  <div class="batch-processor">
    <h2>📦 批量文件处理</h2>
    <p class="description">支持批量上传 PDF 和图片，实时查看处理进度</p>

    <!-- 控制面板 -->
    <div class="control-panel">
      <div class="file-input-wrapper">
        <label for="file-input" class="file-input-label">
          📁 选择文件 (PDF/图片)
        </label>
        <input
          id="file-input"
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.gif,.bmp,.webp"
          @change="handleFileSelect"
          :disabled="isProcessing"
          class="file-input"
        />
        <span v-if="selectedFiles" class="file-count">
          已选择 {{ selectedFiles.length }} 个文件
        </span>
      </div>

      <div class="button-group">
        <button
          class="btn btn-primary"
          @click="startProcessing"
          :disabled="!selectedFiles || selectedFiles.length === 0 || isProcessing"
        >
          🚀 开始处理
        </button>
        <button
          class="btn btn-danger"
          @click="stopAllProcessing"
          :disabled="!isProcessing"
        >
          ⏹️ 停止处理
        </button>
        <button
          class="btn btn-secondary"
          @click="resetAll"
        >
          🔄 重置
        </button>
      </div>
    </div>

    <!-- 指标面板 -->
    <div class="metrics-panel">
      <div class="metric-card">
        <div class="metric-label">总任务数</div>
        <div class="metric-value">{{ metrics.totalTasks }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">已完成</div>
        <div class="metric-value success">{{ metrics.completedTasks }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">失败</div>
        <div class="metric-value danger">{{ metrics.failedTasks }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">总轮询次数</div>
        <div class="metric-value">{{ metrics.totalPolls }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">成功轮询</div>
        <div class="metric-value success">{{ metrics.successPolls }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">失败轮询</div>
        <div class="metric-value danger">{{ metrics.failedPolls }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">平均轮询间隔</div>
        <div class="metric-value">{{ metrics.avgPollInterval }}ms</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">总耗时</div>
        <div class="metric-value">{{ metrics.totalDuration }}ms</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">活跃任务</div>
        <div class="metric-value active">{{ activeTaskCount }}/{{ metrics.totalTasks }}</div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="tasks-container">
      <h3>📋 处理任务</h3>

      <div v-if="tasks.length === 0" class="empty-state">
        <p>暂无任务，请选择文件并点击「开始处理」</p>
      </div>

      <div v-for="task in tasks" :key="task.id" class="task-card">
        <div class="task-header">
          <div class="task-title">
            <span class="file-type-icon">{{ getFileTypeIcon(task.type) }}</span>
            <span class="status-icon" :style="{ color: getStatusColor(task.status) }">
              {{ getStatusIcon(task.status) }}
            </span>
            <span class="task-name">{{ task.name }}</span>
            <span class="status-badge" :style="{ backgroundColor: getStatusColor(task.status) }">
              {{ task.status }}
            </span>
          </div>

          <div class="task-meta">
            <span class="meta-item">大小: {{ formatFileSize(task.fileSize) }}</span>
            <span class="meta-item">轮询: {{ task.pollCount }}</span>
            <span class="meta-item">耗时: {{ getTaskDuration(task) }}s</span>
          </div>
        </div>

        <!-- 进度条 -->
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: task.progress + '%', backgroundColor: getStatusColor(task.status) }">
              <span v-if="task.progress > 10" class="progress-text">{{ task.progress }}%</span>
            </div>
          </div>
        </div>

        <!-- 结果/错误 -->
        <div v-if="task.result" class="result-message success">✅ 处理成功</div>
        <div v-if="task.error" class="result-message error">❌ {{ task.error }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.batch-processor {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-top: 20px;
}

h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #333;
}

.description {
  margin: 0 0 20px 0;
  font-size: 14px;
  color: #999;
}

h3 {
  margin: 20px 0 12px 0;
  font-size: 16px;
  color: #555;
  border-bottom: 2px solid #f0f0f0;
  padding-bottom: 8px;
}

/* 控制面板 */
.control-panel {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.file-input-wrapper {
  flex: 1;
  min-width: 250px;
  position: relative;
}

.file-input {
  display: none;
}

.file-input-label {
  display: inline-block;
  padding: 10px 16px;
  background: #1890ff;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  font-size: 14px;
  transition: background 0.2s;
}

.file-input-label:hover {
  background: #0050b3;
}

.file-input:disabled + .file-input-label {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-count {
  margin-left: 12px;
  font-size: 13px;
  color: #666;
}

.button-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #1890ff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0050b3;
}

.btn-secondary {
  background: #f0f0f0;
  color: #333;
}

.btn-secondary:hover:not(:disabled) {
  background: #e0e0e0;
}

.btn-danger {
  background: #ff4d4f;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #d9001b;
}

/* 指标面板 */
.metrics-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.metric-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #1890ff;
  font-family: monospace;
}

.metric-value.success {
  color: #52c41a;
}

.metric-value.danger {
  color: #ff4d4f;
}

.metric-value.active {
  color: #faad14;
}

/* 任务列表 */
.tasks-container {
  margin-bottom: 24px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
  background: #fafafa;
  border-radius: 8px;
}

.task-card {
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.2s;
}

.task-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 12px;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.file-type-icon {
  font-size: 16px;
}

.status-icon {
  font-size: 18px;
}

.task-name {
  font-weight: 600;
  color: #333;
  word-break: break-all;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  color: white;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.task-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
}

.meta-item {
  color: #666;
  font-family: monospace;
}

/* 进度条 */
.progress-section {
  margin: 12px 0;
}

.progress-bar {
  height: 24px;
  background: #f0f0f0;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}

.progress-fill {
  height: 100%;
  transition: width 0.2s linear;
  display: flex;
  align-items: center;
  justify-content: center;
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
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* 结果消息 */
.result-message {
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  margin: 8px 0;
}

.result-message.success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #52c41a;
}

.result-message.error {
  background: #fff1f0;
  border: 1px solid #ffccc7;
  color: #ff4d4f;
}

@media (max-width: 768px) {
  .control-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .file-input-wrapper {
    min-width: unset;
  }

  .button-group {
    flex-direction: column;
  }

  .button-group .btn {
    width: 100%;
  }

  .metrics-panel {
    grid-template-columns: repeat(2, 1fr);
  }

  .task-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .task-meta {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
