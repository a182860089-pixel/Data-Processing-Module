<script setup lang="ts">
import { ref, reactive, computed } from "vue";

const API_BASE_URL =
  import.meta.env.VITE_PDF_API_BASE_URL ||
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  "http://localhost:8000";

interface CrawlTask {
  id: string;
  url: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  startTime: number;
  endTime?: number;
  result?: {
    title: string;
    content: string;
  };
  error?: string;
}

const urlInput = ref("");
const extractImages = ref(false);
const tasks = ref<CrawlTask[]>([]);
const isProcessing = ref(false);

const metrics = reactive({
  totalTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
});

const generateTaskId = () =>
  `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const isValidWechatUrl = (input: string): boolean => {
  return /^https?:\/\/mp\.weixin\.qq\.com\/s[/?]/.test(input.trim());
};

// 添加URL到任务列表
const addUrl = () => {
  const url = urlInput.value.trim();
  if (!url) return;

  if (!isValidWechatUrl(url)) {
    return;
  }

  // 检查是否已存在
  if (tasks.value.some(t => t.url === url)) {
    urlInput.value = "";
    return;
  }

  const task: CrawlTask = {
    id: generateTaskId(),
    url,
    status: 'pending',
    progress: 0,
    startTime: 0,
  };

  tasks.value.push(task);
  metrics.totalTasks++;
  urlInput.value = "";
};

// 批量添加URL（从文本区域）
const batchUrls = ref("");
const showBatchInput = ref(false);

const addBatchUrls = () => {
  const lines = batchUrls.value.split('\n').map(l => l.trim()).filter(l => l);
  let addedCount = 0;

  lines.forEach(url => {
    if (isValidWechatUrl(url) && !tasks.value.some(t => t.url === url)) {
      const task: CrawlTask = {
        id: generateTaskId(),
        url,
        status: 'pending',
        progress: 0,
        startTime: 0,
      };
      tasks.value.push(task);
      metrics.totalTasks++;
      addedCount++;
    }
  });

  batchUrls.value = "";
  showBatchInput.value = false;
};

// 爬取单个任务
const crawlTask = async (task: CrawlTask) => {
  task.status = 'processing';
  task.startTime = Date.now();
  task.progress = 20;

  try {
    const resp = await fetch(`${API_BASE_URL}/api/v1/crawl/wechat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: task.url,
        extract_images: extractImages.value,
        timeout: 60,
      }),
    });

    task.progress = 70;

    if (!resp.ok) {
      let detail = "";
      try {
        const data = await resp.json();
        detail = data?.detail?.message || data?.detail || JSON.stringify(data);
      } catch {
        detail = resp.statusText;
      }
      throw new Error(`爬取失败 (${resp.status}): ${detail}`);
    }

    const data = await resp.json();
    if (!data.success) {
      throw new Error(data.message || "爬取失败");
    }

    task.progress = 100;
    task.status = 'completed';
    task.endTime = Date.now();
    task.result = {
      title: data.data?.title || "未知标题",
      content: data.data?.content || "",
    };
    metrics.completedTasks++;
  } catch (e) {
    task.status = 'failed';
    task.error = e instanceof Error ? e.message : "爬取失败";
    task.endTime = Date.now();
    task.progress = 0;
    metrics.failedTasks++;
  }
};

// 开始处理所有待处理任务
const startProcessing = async () => {
  if (isProcessing.value) return;
  isProcessing.value = true;

  // 顺序处理，避免被封IP
  while (true) {
    const pendingTask = tasks.value.find(t => t.status === 'pending');
    if (!pendingTask) break;
    await crawlTask(pendingTask);
    // 每个任务之间间隔1秒
    await new Promise(resolve => setTimeout(resolve, 1000));
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
const retryFailed = () => {
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

// 复制内容
const handleCopy = async (task: CrawlTask) => {
  if (!task.result?.content) return;
  try {
    await navigator.clipboard.writeText(task.result.content);
  } catch {}
};

// 下载单个结果
const handleDownload = (task: CrawlTask) => {
  if (!task.result?.content) return;
  const title = task.result.title || "article";
  const safeName = title.replace(/[\\/:*?"<>|]/g, "_").substring(0, 50);
  const blob = new Blob([task.result.content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${safeName}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const getTaskDuration = (task: CrawlTask) => {
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
    processing: '爬取中',
    completed: '已完成',
    failed: '失败',
  };
  return texts[status] || status;
};

// 预览的任务
const previewTask = ref<CrawlTask | null>(null);

const showPreview = (task: CrawlTask) => {
  previewTask.value = task;
};

const closePreview = () => {
  previewTask.value = null;
};
</script>

<template>
  <div class="wechat-crawler">
    <div class="card">
      <h2 class="card-title">🔗 微信文章爬取</h2>
      <p class="card-subtitle">支持批量输入微信公众号文章链接，异步爬取并转换为 Markdown</p>

      <!-- 输入区域 -->
      <div class="input-section">
        <div class="form-row">
          <input
            v-model="urlInput"
            type="text"
            class="url-input"
            placeholder="https://mp.weixin.qq.com/s/..."
            @keyup.enter="addUrl"
          />
          <button class="btn btn-primary" @click="addUrl" :disabled="!urlInput.trim()">
            + 添加
          </button>
          <button 
            class="btn btn-secondary" 
            @click="showBatchInput = !showBatchInput"
          >
            📋 批量添加
          </button>
        </div>

        <!-- 批量输入区域 -->
        <div v-if="showBatchInput" class="batch-input">
          <textarea
            v-model="batchUrls"
            class="batch-textarea"
            placeholder="每行一个链接..."
            rows="4"
          ></textarea>
          <div class="batch-actions">
            <button class="btn btn-sm btn-primary" @click="addBatchUrls">确认添加</button>
            <button class="btn btn-sm btn-secondary" @click="showBatchInput = false">取消</button>
          </div>
        </div>

        <div class="options-row">
          <label class="checkbox-label">
            <input type="checkbox" v-model="extractImages" />
            提取图片链接
          </label>
        </div>
      </div>

      <!-- 任务列表 -->
      <div v-if="tasks.length > 0" class="tasks-section">
        <div class="tasks-header">
          <h3>📋 爬取任务</h3>
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
              v-if="!isProcessing"
              class="btn btn-sm btn-primary"
              :disabled="tasks.filter(t => t.status === 'pending').length === 0"
              @click="startProcessing"
            >
              🚀 开始爬取
            </button>
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
                <span class="task-url" :title="task.url">
                  {{ task.result?.title || task.url.substring(0, 50) + '...' }}
                </span>
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
                  class="btn-icon btn-preview"
                  title="预览"
                  @click="showPreview(task)"
                >
                  👁️
                </button>
                <button
                  v-if="task.status === 'completed' && task.result"
                  class="btn-icon btn-download"
                  title="下载"
                  @click="handleDownload(task)"
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

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <p>请输入微信公众号文章链接，点击“添加”后开始爬取</p>
      </div>
    </div>

    <!-- 预览模态框 -->
    <Teleport to="body">
      <div v-if="previewTask" class="modal-overlay" @click.self="closePreview">
        <div class="modal-content">
          <div class="modal-header">
            <h3>{{ previewTask.result?.title || '文章预览' }}</h3>
            <button class="btn-close" @click="closePreview">✕</button>
          </div>
          <div class="modal-body">
            <textarea
              class="markdown-view"
              readonly
              :value="previewTask.result?.content || ''"
            ></textarea>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="handleCopy(previewTask)">📋 复制</button>
            <button class="btn btn-secondary" @click="handleDownload(previewTask)">⬇️ 下载</button>
            <button class="btn btn-primary" @click="closePreview">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.wechat-crawler {
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

.input-section {
  margin-bottom: 16px;
}

.form-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.url-input {
  flex: 1;
  min-width: 200px;
  padding: 10px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.url-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.batch-input {
  margin-top: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}

.batch-textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  resize: vertical;
}

.batch-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: flex-end;
}

.options-row {
  margin-top: 12px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
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
  max-height: 400px;
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

.task-url {
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
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

.btn-preview {
  background: #f0f7ff;
  color: #1890ff;
}

.btn-preview:hover {
  background: #d6e8ff;
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
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  animation: shimmer 2s infinite;
}

.progress-text {
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.2);
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
  margin-top: 16px;
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  background: #f3f4f6;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.btn-close:hover {
  background: #e5e7eb;
}

.modal-body {
  flex: 1;
  padding: 16px 20px;
  overflow: hidden;
}

.markdown-view {
  width: 100%;
  height: 400px;
  resize: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
    align-items: stretch;
  }

  .tasks-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .task-url {
    max-width: 150px;
  }

  .modal-content {
    width: 95%;
    max-height: 90vh;
  }
}
</style>
