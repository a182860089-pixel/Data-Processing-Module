<script setup lang="ts">
import { ref, reactive, computed, onUnmounted } from 'vue'

interface Task {
  id: string
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  pollCount: number
  startTime: number
  endTime?: number
  result?: string
  error?: string
}

interface PollMetrics {
  totalPolls: number
  successPolls: number
  failedPolls: number
  avgPollInterval: number
  totalDuration: number
}

const tasks = reactive<Task[]>([])
const metrics = reactive<PollMetrics>({
  totalPolls: 0,
  successPolls: 0,
  failedPolls: 0,
  avgPollInterval: 0,
  totalDuration: 0,
})

const pollIntervals = reactive<number[]>([])
const autoMode = ref(false)
const pollInterval = ref(1000) // 轮询间隔（毫秒）
const simulationDuration = ref(5000) // 模拟任务时长
const taskCount = ref(3)

let pollTimers = new Map<string, number>()

// 生成任务 ID
const generateTaskId = () => `task-${Date.now()}-${Math.random().toString(36).slice(2)}`

// 创建新任务
const createTask = (name: string): Task => {
  return {
    id: generateTaskId(),
    name,
    status: 'pending',
    progress: 0,
    pollCount: 0,
    startTime: Date.now(),
  }
}

// 模拟轮询获取任务状态
const simulatePollStatus = async (task: Task): Promise<void> => {
  const elapsedTime = Date.now() - task.startTime
  const progress = Math.min((elapsedTime / simulationDuration.value) * 100, 100)

  task.progress = Math.floor(progress)
  task.pollCount++
  metrics.totalPolls++

  // 根据进度更新状态
  if (progress < 100) {
    task.status = 'processing'
    metrics.successPolls++
  } else {
    task.status = 'completed'
    task.result = `✓ 任务完成，处理进度：${task.progress}%`
    task.endTime = Date.now()
    metrics.successPolls++
    
    // 清除轮询定时器
    if (pollTimers.has(task.id)) {
      clearInterval(pollTimers.get(task.id)!)
      pollTimers.delete(task.id)
    }
  }
}

// 模拟任务失败
const failTask = (task: Task, reason: string) => {
  task.status = 'failed'
  task.error = reason
  task.endTime = Date.now()
  metrics.failedPolls++
  
  if (pollTimers.has(task.id)) {
    clearInterval(pollTimers.get(task.id)!)
    pollTimers.delete(task.id)
  }
}

// 开始轮询单个任务
const startPollingTask = (task: Task) => {
  task.status = 'processing'
  task.startTime = Date.now()
  
  const timerId = window.setInterval(async () => {
    const pollStartTime = Date.now()
    
    try {
      await simulatePollStatus(task)
      
      const pollDuration = Date.now() - pollStartTime
      pollIntervals.push(pollDuration)
      
      // 更新平均轮询间隔
      if (pollIntervals.length > 0) {
        metrics.avgPollInterval = Math.round(
          pollIntervals.reduce((a, b) => a + b, 0) / pollIntervals.length
        )
      }
      
      // 任务完成，停止轮询
      if (task.status === 'completed' || task.status === 'failed') {
        task.endTime = Date.now()
        metrics.totalDuration = Math.max(
          metrics.totalDuration,
          task.endTime - task.startTime
        )
        clearInterval(timerId)
        pollTimers.delete(task.id)
      }
    } catch (e) {
      failTask(task, e instanceof Error ? e.message : '轮询出错')
    }
  }, pollInterval.value)
  
  pollTimers.set(task.id, timerId)
}

// 批量创建和轮询任务
const startBatchTasks = async () => {
  tasks.length = 0
  pollIntervals.length = 0
  metrics.totalPolls = 0
  metrics.successPolls = 0
  metrics.failedPolls = 0
  metrics.totalDuration = 0
  
  const newTasks = Array.from({ length: taskCount.value }, (_, i) =>
    createTask(`任务 ${i + 1}`)
  )
  
  tasks.push(...newTasks)
  
  // 依次启动轮询
  for (const task of newTasks) {
    startPollingTask(task)
    if (!autoMode.value) {
      await new Promise(resolve => setTimeout(resolve, 300))
    }
  }
}

// 停止所有轮询
const stopAllPolling = () => {
  pollTimers.forEach(timerId => clearInterval(timerId))
  pollTimers.clear()
  tasks.forEach(task => {
    if (task.status === 'processing') {
      task.status = 'pending'
      task.progress = 0
      task.pollCount = 0
    }
  })
}

// 手动轮询一次
const manualPoll = (task: Task) => {
  if (task.status === 'pending') {
    startPollingTask(task)
  } else if (task.status === 'processing') {
    simulatePollStatus(task)
  }
}

// 重置任务
const resetTask = (taskId: string) => {
  const idx = tasks.findIndex(t => t.id === taskId)
  if (idx !== -1) {
    const task = tasks[idx]
    if (pollTimers.has(task.id)) {
      clearInterval(pollTimers.get(task.id)!)
      pollTimers.delete(task.id)
    }
    tasks.splice(idx, 1)
  }
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

// 计算任务总耗时
const getTaskDuration = (task: Task) => {
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
  <div class="async-polling-test">
    <h2>🔄 异步轮询测试工具</h2>
    
    <!-- 控制面板 -->
    <div class="control-panel">
      <div class="config-group">
        <div class="config-item">
          <label>轮询间隔 (ms):</label>
          <input v-model.number="pollInterval" type="number" min="100" max="5000" step="100" />
        </div>
        
        <div class="config-item">
          <label>模拟时长 (ms):</label>
          <input v-model.number="simulationDuration" type="number" min="1000" max="30000" step="1000" />
        </div>
        
        <div class="config-item">
          <label>任务数量:</label>
          <input v-model.number="taskCount" type="number" min="1" max="10" step="1" />
        </div>
        
        <div class="config-item checkbox">
          <input v-model="autoMode" type="checkbox" />
          <label>自动模式</label>
        </div>
      </div>
      
      <div class="button-group">
        <button class="btn btn-primary" @click="startBatchTasks" :disabled="activeTaskCount > 0">
          🚀 启动轮询测试
        </button>
        <button class="btn btn-danger" @click="stopAllPolling" :disabled="activeTaskCount === 0">
          ⏹️ 停止所有轮询
        </button>
      </div>
    </div>
    
    <!-- 指标面板 -->
    <div class="metrics-panel">
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
        <div class="metric-value active">{{ activeTaskCount }}/{{ taskCount }}</div>
      </div>
    </div>
    
    <!-- 任务列表 -->
    <div class="tasks-container">
      <h3>📋 任务列表</h3>
      
      <div v-if="tasks.length === 0" class="empty-state">
        <p>暂无任务，点击"启动轮询测试"开始</p>
      </div>
      
      <div v-for="task in tasks" :key="task.id" class="task-card">
        <div class="task-header">
          <div class="task-title">
            <span class="status-icon" :style="{ color: getStatusColor(task.status) }">
              {{ getStatusIcon(task.status) }}
            </span>
            <span class="task-name">{{ task.name }}</span>
            <span class="status-badge" :style="{ backgroundColor: getStatusColor(task.status) }">
              {{ task.status }}
            </span>
          </div>
          
          <div class="task-meta">
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
        
        <!-- 结果/错误信息 -->
        <div v-if="task.result" class="result-message success">{{ task.result }}</div>
        <div v-if="task.error" class="result-message error">❌ {{ task.error }}</div>
        
        <!-- 操作按钮 -->
        <div class="task-actions">
          <button 
            v-if="task.status === 'pending' || task.status === 'processing'"
            class="btn btn-small btn-secondary"
            @click="manualPoll(task)"
            :disabled="task.status === 'completed' || task.status === 'failed'"
          >
            🔄 手动轮询
          </button>
          
          <button 
            class="btn btn-small btn-danger"
            @click="resetTask(task.id)"
          >
            ♻️ 重置
          </button>
        </div>
      </div>
    </div>
    
    <!-- 详细日志 -->
    <div class="logs-section">
      <h3>📊 轮询详情</h3>
      <div class="logs-content">
        <div v-if="tasks.length === 0" class="log-empty">
          尚未有轮询活动
        </div>
        <template v-else>
          <div v-for="task in tasks" :key="`log-${task.id}`" class="log-item">
            <span class="log-time">[{{ task.name }}]</span>
            <span class="log-text">状态: {{ task.status }} | 进度: {{ task.progress }}% | 轮询: {{ task.pollCount }}次</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.async-polling-test {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-top: 20px;
}

h2 {
  margin: 0 0 20px 0;
  font-size: 24px;
  color: #333;
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
}

.config-group {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-item label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.config-item input {
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  font-family: monospace;
}

.config-item.checkbox {
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.config-item.checkbox input {
  width: 16px;
  height: 16px;
  margin: 0;
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

.btn-small {
  padding: 4px 12px;
  font-size: 12px;
}

/* 指标面板 */
.metrics-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
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

.status-icon {
  font-size: 18px;
}

.task-name {
  font-weight: 600;
  color: #333;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  color: white;
  font-size: 11px;
  font-weight: 600;
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

/* 任务操作 */
.task-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

/* 日志部分 */
.logs-section {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.logs-content {
  font-family: monospace;
  font-size: 11px;
}

.log-empty {
  color: #999;
  text-align: center;
  padding: 20px;
}

.log-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #e8e8e8;
}

.log-time {
  color: #999;
  min-width: 100px;
}

.log-text {
  color: #333;
  flex: 1;
}

@media (max-width: 768px) {
  .config-group {
    grid-template-columns: repeat(2, 1fr);
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
