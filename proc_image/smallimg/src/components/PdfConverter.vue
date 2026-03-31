<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMultiFileProcessor, type FileTask } from '@/composables/useMultiFileProcessor'
import MultiFileTaskList from './MultiFileTaskList.vue'
import { renderMarkdownPreview } from '@/utils/markdown-preview'

const API_BASE_URL =
  import.meta.env.VITE_PDF_API_BASE_URL ||
  import.meta.env.VITE_IMAGE_API_BASE_URL ||
  'http://localhost:8000'

interface ConvertResult {
  taskId: string
  markdown: string
  downloadUrl: string
  processingTime: number
  outputType?: string
  isEmpty?: boolean
}

const resolveConversionResult = (data: Record<string, any>, taskId: string, startTime: number): ConvertResult => {
  const resolvedTaskId = data.task_id || taskId
  const resolvedMarkdown = data.markdown_content || data.result?.markdown_content || ''
  const resolvedDownloadUrl =
    data.download_url ||
    data.result?.download_url ||
    (resolvedTaskId ? `/api/v1/download/${resolvedTaskId}` : '')
  const resolvedOutputType =
    data.file_type ||
    data.result?.metadata?.output_type ||
    data.metadata?.output_type ||
    'markdown'

  return {
    taskId: resolvedTaskId,
    markdown: resolvedMarkdown,
    downloadUrl: resolvedDownloadUrl.startsWith('http')
      ? resolvedDownloadUrl
      : `${API_BASE_URL}${resolvedDownloadUrl}`,
    processingTime: (Date.now() - startTime) / 1000,
    outputType: resolvedOutputType,
    isEmpty: !resolvedMarkdown.trim(),
  }
}

const emit = defineEmits<{
  error: [message: string]
}>()

const mode = ref<'reader' | 'debug'>('reader')
const previewMode = ref<'formatted' | 'source'>('formatted')
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const isValidFile = (filename: string): boolean => {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const validExt = [
    'pdf',
    'docx',
    'doc',
    'pptx',
    'ppt',
    'xlsx',
    'xls',
    'jpg',
    'jpeg',
    'png',
    'gif',
    'bmp',
    'tiff',
    'webp',
  ]
  return validExt.includes(ext)
}

const detectFileType = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const typeMap: Record<string, string> = {
    pdf: 'PDF',
    docx: 'Word',
    doc: 'Word',
    pptx: 'PowerPoint',
    ppt: 'PowerPoint',
    xlsx: 'Excel',
    xls: 'Excel',
    jpg: 'Image',
    jpeg: 'Image',
    png: 'Image',
    gif: 'Image',
    bmp: 'Image',
    tiff: 'Image',
    webp: 'Image',
  }
  return typeMap[ext] || 'Unknown'
}

const buildOptions = (fileType: string) => {
  if (fileType === 'PDF') {
    if (mode.value === 'reader') {
      return { include_metadata: false, no_pagination_and_metadata: true }
    }
    return { include_metadata: true, no_pagination_and_metadata: false }
  }

  if (['Word', 'PowerPoint', 'Excel'].includes(fileType)) {
    return { keep_layout: true, office_dpi: 96, dpi: 144 }
  }

  if (fileType === 'Image') {
    return { page_size: 'A4', fit_mode: 'fit', dpi: 144 }
  }

  return {}
}

const convertFile = async (
  file: File,
  onProgress?: (progress: number) => void
): Promise<ConvertResult> => {
  const startTime = Date.now()
  const fileType = detectFileType(file.name)
  const convertOptions = buildOptions(fileType)

  onProgress?.(5)

  const formData = new FormData()
  formData.append('file', file)
  formData.append('options', JSON.stringify(convertOptions))

  const submitResp = await fetch(`${API_BASE_URL}/api/v1/convert/async`, {
    method: 'POST',
    body: formData,
  })

  if (!submitResp.ok) {
    const errData = await submitResp.json().catch(() => ({}))
    throw new Error(errData?.detail?.message || errData?.detail || `提交失败 (${submitResp.status})`)
  }

  const submitData = await submitResp.json()
  const taskId = submitData.task_id

  if (!taskId) {
    throw new Error('未获取到任务ID')
  }

  onProgress?.(12)

  let pollCount = 0
  while (pollCount < 600) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    pollCount++

    const statusResp = await fetch(`${API_BASE_URL}/api/v1/status/${taskId}`)
    if (!statusResp.ok) continue

    const statusData = await statusResp.json()
    const status = statusData.status

    if (statusData.progress?.percentage !== undefined) {
      const progress = Math.min(95, 12 + statusData.progress.percentage * 0.83)
      onProgress?.(progress)
    }

    if (status === 'completed') {
      onProgress?.(100)
      return resolveConversionResult(statusData, taskId, startTime)
    }

    if (status === 'failed') {
      throw new Error(statusData.error?.message || statusData.error?.details || '转换失败')
    }
  }

  throw new Error('轮询超时，任务可能仍在后台处理')
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
} = useMultiFileProcessor<ConvertResult>(convertFile, { concurrency: 2 })

const completedTasks = computed(() => tasks.value.filter((task) => task.status === 'completed' && task.result))

const handleFiles = (files: File[]) => {
  const validFiles: File[] = []
  const errors: string[] = []

  files.forEach((file) => {
    if (!isValidFile(file.name)) {
      errors.push(`${file.name}: 不支持的文件格式`)
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

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    handleFiles(Array.from(target.files))
    target.value = ''
  }
}

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

const handleClick = () => {
  fileInput.value?.click()
}

const handleCopy = async (task: FileTask<ConvertResult>) => {
  if (!task.result?.markdown) return
  try {
    await navigator.clipboard.writeText(task.result.markdown)
  } catch {
    emit('error', '复制失败')
  }
}

const handleDownload = (task: FileTask<ConvertResult>) => {
  if (!task.result?.downloadUrl) return
  const link = document.createElement('a')
  link.href = task.result.downloadUrl
  link.target = '_blank'
  link.click()
}

</script>

<template>
  <div class="dual-stage pdf-converter">
    <aside class="control-column">
      <div class="panel-card intro-card">
        <p class="panel-caption">第一步：解析策略</p>
        <h2>阅读优先或结构优先</h2>
        <p class="panel-copy">
          左侧负责定义文档转换模式并上传文件。右侧只负责实时反馈、Markdown 预览和结果操作。
        </p>
      </div>

      <div
        class="upload-zone compact-upload"
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
          accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.webp"
          multiple
          class="hidden-input"
          @change="handleFileSelect"
        />

        <div class="upload-content compact-copy">
          <div class="upload-icon-circle">◇</div>
          <h3>上传待转换文档</h3>
          <p>支持 PDF、Word、PPT、Excel 与图片文件</p>
        </div>
      </div>

      <label class="mode-card" :class="{ active: mode === 'reader' }">
        <input v-model="mode" type="radio" value="reader" />
        <div>
          <strong>阅读模式</strong>
          <p>纯净内容，去除页眉页脚与干扰信息。</p>
        </div>
      </label>

      <label class="mode-card" :class="{ active: mode === 'debug' }">
        <input v-model="mode" type="radio" value="debug" />
        <div>
          <strong>调试模式</strong>
          <p>保留分页、图像和元数据，适合核对结构与开发联调。</p>
        </div>
      </label>

      <button
        class="launch-button"
        :class="{ disabled: tasks.filter((task) => task.status === 'pending').length === 0 || isProcessing }"
        :disabled="tasks.filter((task) => task.status === 'pending').length === 0 || isProcessing"
        @click="startProcessing"
      >
        开始转换 Markdown
      </button>
    </aside>

    <section class="preview-column">
      <div class="preview-header">
        <div class="preview-title">
          <span>实时任务看板</span>
          <b>{{ tasks.length }}</b>
        </div>
        <button class="ghost-button" @click="clearTasks" :disabled="isProcessing || tasks.length === 0">
          清空队列
        </button>
      </div>

      <div v-if="tasks.length === 0" class="empty-preview">
        <div class="empty-mark">✦</div>
        <h3>等待文档进入任务区</h3>
        <p>右侧负责文档解析进度、Markdown 预览和下载结果。</p>
      </div>

      <div v-else class="result-stack">
        <div v-if="completedTasks.length > 0" class="preview-cards">
          <article v-for="task in completedTasks" :key="task.id" class="preview-card">
            <div>
              <p class="panel-caption">完成结果</p>
              <h3>{{ task.name }}</h3>
              <div class="reader-panel">
                <div class="reader-toolbar">
                  <h4 class="reader-title">正文预览</h4>
                  <div class="reader-actions">
                    <div class="reader-switcher">
                      <button class="reader-switch" :class="{ active: previewMode === 'formatted' }" @click="previewMode = 'formatted'">阅读视图</button>
                      <button class="reader-switch" :class="{ active: previewMode === 'source' }" @click="previewMode = 'source'">源码视图</button>
                    </div>
                  </div>
                </div>
                <template v-if="task.result?.markdown?.trim()">
                  <div v-if="previewMode === 'formatted'" class="reader-content reader-markdown" v-html="renderMarkdownPreview(task.result?.markdown || '')"></div>
                  <textarea v-else class="reader-source" readonly :value="task.result?.markdown || ''"></textarea>
                </template>
                <div v-else class="empty-markdown-state">
                  <strong>任务已完成，但未返回可预览的 Markdown 内容</strong>
                  <p>
                    下载结果仍可使用。这通常表示后端返回了空的 `markdown_content`，或者本次响应里只有下载链接，没有可直接预览的正文内容。
                  </p>
                </div>
              </div>
            </div>
            <div class="card-actions">
              <button class="ghost-button" :disabled="!task.result?.markdown?.trim()" @click="handleCopy(task)">复制</button>
              <button class="launch-button compact" @click="handleDownload(task)">下载</button>
            </div>
          </article>
        </div>

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
    </section>

  </div>
</template>

<style scoped>
.dual-stage {
  display: grid;
  grid-template-columns: minmax(320px, 360px) minmax(0, 1fr);
  gap: 18px;
  min-height: calc(100vh - 140px);
  align-items: start;
}

.control-column {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 0;
}

.panel-card,
.mode-card,
.preview-column,
.preview-card {
  border-radius: 30px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 22px 48px rgba(97, 107, 143, 0.08);
}

.panel-card,
.mode-card,
.preview-card {
  padding: 24px;
}

.panel-caption {
  margin: 0 0 12px;
  color: #8e99b1;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.intro-card h2,
.upload-content h3,
.empty-preview h3,
.preview-card h3 {
  margin: 0 0 10px;
  color: #15203a;
  font-size: 28px;
  line-height: 1.12;
}

.panel-copy,
.mode-card p,
.upload-content p,
.empty-preview p,
.preview-card p {
  margin: 0;
  color: #8390ab;
  font-size: 14px;
  line-height: 1.8;
}

.mode-card {
  display: flex;
  gap: 12px;
  cursor: pointer;
}

.mode-card input {
  margin-top: 4px;
  accent-color: #4f67f8;
}

.mode-card strong {
  display: block;
  margin-bottom: 6px;
  color: #15203a;
  font-size: 18px;
}

.mode-card.active {
  border-color: #4f67f8;
  background: #f7f9ff;
}

.launch-button {
  min-height: 62px;
  border: none;
  border-radius: 24px;
  background: linear-gradient(135deg, #13203c 0%, #0f1730 100%);
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  box-shadow: 0 20px 40px rgba(16, 25, 52, 0.2);
  cursor: pointer;
}

.launch-button.compact {
  min-height: 44px;
  padding: 0 18px;
  font-size: 14px;
}

.launch-button.disabled {
  background: linear-gradient(180deg, #eff3ff 0%, #e8eefc 100%);
  color: #c2cada;
  box-shadow: none;
}

.preview-column {
  display: flex;
  flex-direction: column;
  padding: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.8), rgba(250, 251, 255, 0.88));
  min-width: 0;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.preview-title {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #12203a;
  font-size: 16px;
  font-weight: 800;
}

.preview-title b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 26px;
  padding: 0 8px;
  border-radius: 10px;
  background: #101934;
  color: #fff;
  font-size: 12px;
}

.ghost-button {
  min-height: 44px;
  padding: 0 16px;
  border: none;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  color: #8390ab;
  font-weight: 800;
  cursor: pointer;
}

.upload-zone {
  position: relative;
  border: 1px dashed #d6def2;
  border-radius: 30px;
  padding: 56px 24px;
  text-align: center;
  cursor: pointer;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(246, 249, 255, 0.8));
  transition: all 0.25s ease;
}

.compact-upload {
  padding: 28px 18px;
  margin-bottom: 0;
}

.compact-copy h3 {
  font-size: 18px;
}

.upload-zone.dragging,
.upload-zone:hover {
  border-color: #93a4ff;
  background: #f3f6ff;
}

.hidden-input {
  display: none;
}

.upload-icon-circle {
  width: 78px;
  height: 78px;
  margin: 0 auto 18px;
  border-radius: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #eef2ff 0%, #f7f9ff 100%);
  color: #4f67f8;
  font-size: 36px;
  font-weight: 800;
}

.empty-preview,
.preview-cards {
  margin-top: 18px;
}

.empty-preview {
  padding: 34px;
  border-radius: 28px;
  border: 1px solid rgba(223, 228, 242, 0.85);
  background: rgba(255, 255, 255, 0.76);
  text-align: center;
}

.empty-mark {
  margin-bottom: 16px;
  color: #bac4d8;
  font-size: 40px;
}

.preview-cards {
  display: grid;
  gap: 14px;
}

.card-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.result-stack {
  margin-top: 18px;
}

.inline-preview {
  margin-top: 16px;
}

.preview-switcher {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.switch-chip {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  background: #fff;
  color: #8390ab;
  font-weight: 700;
  cursor: pointer;
}

.switch-chip.active {
  background: #101934;
  color: #fff;
  border-color: #101934;
}

.inline-markdown {
  width: 100%;
  min-height: 320px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  border-radius: 18px;
  padding: 16px;
  resize: vertical;
  background: #fbfcff;
  color: #1f2b49;
  line-height: 1.7;
}

.rendered-preview {
  min-height: 320px;
  max-height: 520px;
  overflow: auto;
  border: 1px solid rgba(221, 228, 242, 0.92);
  border-radius: 18px;
  padding: 22px;
  background: #fbfcff;
}

.markdown-reading {
  color: #1f2b49;
  line-height: 1.85;
}

.markdown-reading :deep(h1),
.markdown-reading :deep(h2),
.markdown-reading :deep(h3) {
  color: #13203c;
  margin: 0 0 16px;
}

.markdown-reading :deep(p) {
  margin: 0 0 16px;
}

.markdown-reading :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #eef2ff;
  color: #4f67f8;
}

.empty-markdown-state {
  min-height: 320px;
  padding: 24px;
  border: 1px dashed rgba(221, 228, 242, 0.92);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(251, 252, 255, 0.96), rgba(246, 249, 255, 0.92));
  color: #52607a;
}

.empty-markdown-state strong {
  display: block;
  margin-bottom: 10px;
  color: #15203a;
  font-size: 16px;
}

.empty-markdown-state p {
  margin: 0;
  line-height: 1.8;
}

@media (max-width: 1180px) {
  .dual-stage {
    grid-template-columns: 1fr;
  }

  .control-column {
    position: static;
  }
}
</style>
