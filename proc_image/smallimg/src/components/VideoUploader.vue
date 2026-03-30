<script setup lang="ts">
import { ref } from 'vue';

interface VideoConversionOptions {
  output_type: 'markdown' | 'pdf';
  keyframe_interval: number;
  max_frames: number;
  frame_quality: number;
  include_metadata: boolean;
  include_frames: boolean;
  frame_mode: 'interval' | 'scene';
  enable_asr: boolean;
  enable_subtitle_extraction: boolean;
  enable_video_summary: boolean;
  subtitle_priority: 'subtitle_first' | 'asr_first' | 'both';
}

interface ConversionResult {
  id: string;
  file: File;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  result?: {
    task_id: string;
    markdown_content?: string;
    pdf_content?: Blob;
    metadata: Record<string, any>;
  };
  error?: string;
  statusMessage?: string;
}

const emit = defineEmits<{
  error: [message: string];
}>();

const videos = ref<ConversionResult[]>([]);
const isDragging = ref(false);
const outputType = ref<'markdown' | 'pdf'>('markdown');
const keyframeInterval = ref(5);
const maxFrames = ref(50);
const frameQuality = ref(85);
const includeMetadata = ref(true);
const includeFrames = ref(false);
const frameMode = ref<'interval' | 'scene'>('scene');
const enableAsr = ref(true);
const enableSubtitleExtraction = ref(true);
const enableVideoSummary = ref(true);
const subtitlePriority = ref<'subtitle_first' | 'asr_first' | 'both'>('asr_first');
const isConverting = ref(false);
const apiBaseUrl = ref('http://localhost:8000');
const maxParallelTasks = 2;

const handleDragOver = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = true;
};

const handleDragLeave = () => {
  isDragging.value = false;
};

const handleDrop = (e: DragEvent) => {
  e.preventDefault();
  isDragging.value = false;
  
  const files = e.dataTransfer?.files;
  if (files) {
    handleFiles(Array.from(files));
  }
};

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement;
  if (input.files) {
    handleFiles(Array.from(input.files));
  }
  input.value = '';
};

const handleFiles = (files: File[]) => {
  const videoFiles = files.filter(file => 
    file.type.startsWith('video/') || 
    /\.(mp4|avi|mov|wmv|mkv|flv)$/i.test(file.name)
  );

  if (videoFiles.length === 0) {
    emit('error', '请选择有效的视频文件');
    return;
  }

  if (videoFiles.length + videos.value.length > 5) {
    emit('error', '最多只能同时转换5个视频');
    return;
  }

  for (const file of videoFiles) {
    if (file.size > 500 * 1024 * 1024) {
      emit('error', `${file.name} 超过500MB限制`);
      continue;
    }

    const video: ConversionResult = {
      id: Math.random().toString(36).substr(2, 9),
      file,
      status: 'pending',
      progress: 0,
    };

    videos.value.push(video);
  }
};

const convertVideo = async (video: ConversionResult) => {
  const formData = new FormData();
  formData.append('file', video.file);
  
  const options: VideoConversionOptions = {
    output_type: outputType.value,
    keyframe_interval: keyframeInterval.value,
    max_frames: maxFrames.value,
    frame_quality: frameQuality.value,
    include_metadata: includeMetadata.value,
    include_frames: includeFrames.value,
    frame_mode: frameMode.value,
    enable_asr: enableAsr.value,
    enable_subtitle_extraction: enableSubtitleExtraction.value,
    enable_video_summary: enableVideoSummary.value,
    subtitle_priority: subtitlePriority.value,
  };

  formData.append('options', JSON.stringify(options));

  try {
    video.status = 'processing';
    video.progress = 5;
    video.statusMessage = '提交任务中';

    const xhr = new XMLHttpRequest();

    // 监听上传进度
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          video.progress = Math.min(20, 5 + (e.loaded / e.total) * 15);
        }
      });

    // 发送请求
      const response = await new Promise<{
        success: boolean;
        task_id: string;
        markdown_content?: string;
        file_type: string;
        metadata: Record<string, any>;
        status_url?: string;
      }>((resolve, reject) => {
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status === 200 || xhr.status === 201) {
            resolve(data);
          } else {
            reject(new Error(data.detail || xhr.statusText));
          }
        } catch (e) {
          reject(new Error('响应解析失败'));
        }
      };

      xhr.onerror = () => reject(new Error('网络错误'));
      xhr.ontimeout = () => reject(new Error('请求超时'));

      const endpoint = outputType.value === 'pdf'
        ? `${apiBaseUrl.value}/api/v1/convert/async`
        : `${apiBaseUrl.value}/api/v1/convert/markdown/async`;

      xhr.open('POST', endpoint);
      xhr.send(formData);
    });

    video.progress = 25;
    video.statusMessage = '任务已提交，等待处理';

    const taskId = response.task_id;
    if (!taskId) {
      throw new Error('未返回任务ID');
    }

    const taskResult = await pollTaskResult(taskId, video);

    const actualOutputType = taskResult.file_type || taskResult.metadata?.output_type || 'markdown';

    if (actualOutputType === 'pdf') {
      const downloadResponse = await fetch(
        `${apiBaseUrl.value}/api/v1/download/${taskId}`
      );
      if (!downloadResponse.ok) {
        throw new Error('PDF 结果下载失败');
      }
      const pdfBlob = await downloadResponse.blob();
      video.result = {
        task_id: taskId,
        pdf_content: pdfBlob,
        metadata: taskResult.metadata || {},
      };
    } else {
      video.result = {
        task_id: taskId,
        markdown_content: taskResult.markdown_content || '',
        metadata: taskResult.metadata || {},
      };
    }

    video.progress = 100;
    video.status = 'completed';
    video.statusMessage = '转换完成';
  } catch (error) {
    video.status = 'failed';
    video.error = error instanceof Error ? error.message : '转换失败';
    video.statusMessage = '转换失败';
  }
};

const startAllConversions = async () => {
  isConverting.value = true;

  const pendingVideos = videos.value.filter(video => video.status === 'pending');
  const queue = [...pendingVideos];

  const workers = Array.from({ length: Math.min(maxParallelTasks, queue.length) }, async () => {
    while (queue.length > 0) {
      const nextVideo = queue.shift();
      if (!nextVideo) {
        return;
      }
      await convertVideo(nextVideo);
    }
  });

  if (workers.length > 0) {
    await Promise.allSettled(workers);
  }

  isConverting.value = false;
};

const pollTaskResult = async (taskId: string, video: ConversionResult) => {
  const maxPolls = 900;

  for (let i = 0; i < maxPolls; i++) {
    await new Promise(resolve => setTimeout(resolve, 1000));

    const statusResponse = await fetch(`${apiBaseUrl.value}/api/v1/status/${taskId}`);
    if (!statusResponse.ok) {
      continue;
    }

    const statusData = await statusResponse.json();
    if (typeof statusData.progress?.percentage === 'number') {
      video.progress = Math.max(25, Math.min(99, statusData.progress.percentage));
    }
    if (statusData.message) {
      video.statusMessage = statusData.message;
    }

    if (statusData.status === 'completed') {
      return {
        file_type: statusData.result?.metadata?.output_type || outputType.value,
        markdown_content: statusData.result?.markdown_content || '',
        download_url: statusData.result?.download_url || `/api/v1/download/${taskId}`,
        metadata: statusData.result?.metadata || {},
      };
    }

    if (statusData.status === 'failed') {
      throw new Error(
        statusData.error?.details || statusData.error?.message || '任务执行失败'
      );
    }
  }

  throw new Error('任务轮询超时');
};

const downloadMarkdown = (video: ConversionResult) => {
  if (!video.result?.markdown_content) return;

  const element = document.createElement('a');
  const file = new Blob([video.result.markdown_content], { type: 'text/markdown' });
  element.href = URL.createObjectURL(file);
  element.download = `${video.file.name.split('.')[0]}.md`;
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
  URL.revokeObjectURL(element.href);
};

const downloadPDF = (video: ConversionResult) => {
  if (!video.result?.pdf_content) return;

  const element = document.createElement('a');
  element.href = URL.createObjectURL(video.result.pdf_content);
  element.download = `${video.file.name.split('.')[0]}.pdf`;
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
  URL.revokeObjectURL(element.href);
};

const removeVideo = (id: string) => {
  const index = videos.value.findIndex(v => v.id === id);
  if (index !== -1) {
    videos.value.splice(index, 1);
  }
};

const clearAll = () => {
  videos.value = [];
};
</script>

<template>
  <div class="video-uploader">
    <!-- 上传区域 -->
    <div
      class="upload-zone"
      :class="{ dragging: isDragging }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="upload-content">
        <div class="upload-icon">🎬</div>
        <h3>上传视频文件</h3>
        <p class="supported">默认提取音频/字幕文本生成 Markdown，支持: MP4, AVI, MOV, WMV, MKV, FLV (最大 500MB)</p>
        <input
          type="file"
          multiple
          accept="video/*"
          style="display: none"
          @change="handleFileSelect"
          ref="fileInput"
        />
        <button class="btn-primary" @click="$refs.fileInput?.click()">
          选择文件
        </button>
        <p class="drag-hint">或拖放视频到此处</p>
      </div>
    </div>

    <!-- 转换选项 -->
    <div class="options-panel">
      <div class="option-row">
        <div class="option-item">
          <label>输出格式</label>
          <div class="radio-group">
            <label>
              <input type="radio" v-model="outputType" value="markdown" />
              Markdown
            </label>
            <label>
              <input type="radio" v-model="outputType" value="pdf" />
              PDF
            </label>
          </div>
        </div>

        <div class="option-item">
          <label>关键帧间隔 (秒)</label>
          <input
            type="range"
            v-model.number="keyframeInterval"
            min="1"
            max="30"
          />
          <span class="value-display">{{ keyframeInterval }}秒</span>
        </div>

        <div class="option-item">
          <label>最大帧数</label>
          <input
            type="range"
            v-model.number="maxFrames"
            min="5"
            max="200"
          />
          <span class="value-display">{{ maxFrames }}</span>
        </div>

        <div class="option-item">
          <label>抽帧模式</label>
          <div class="radio-group">
            <label>
              <input type="radio" v-model="frameMode" value="scene" />
              场景检测
            </label>
            <label>
              <input type="radio" v-model="frameMode" value="interval" />
              固定间隔
            </label>
          </div>
        </div>

        <div class="option-item">
          <label>帧质量</label>
          <input
            type="range"
            v-model.number="frameQuality"
            min="50"
            max="100"
          />
          <span class="value-display">{{ frameQuality }}%</span>
        </div>
      </div>

      <div class="checkbox-group">
        <label>
          <input type="checkbox" v-model="includeMetadata" />
          包含元数据
        </label>
            <label>
              <input type="checkbox" v-model="includeFrames" />
              内嵌关键帧图片（会让 Markdown 很长）
            </label>
      </div>

      <div class="api-config">
        <label>API 地址</label>
        <input type="text" v-model="apiBaseUrl" class="api-input" />
      </div>
    </div>

    <!-- 转换列表 -->
    <div v-if="videos.length > 0" class="conversion-list">
      <div class="list-header">
        <h4>转换队列 ({{ videos.length }})</h4>
        <div class="list-actions">
          <button
            class="btn-primary"
            @click="startAllConversions"
            :disabled="isConverting || videos.every(v => v.status !== 'pending')"
          >
            {{ isConverting ? '转换中...' : '开始转换' }}
          </button>
          <button class="btn-secondary" @click="clearAll">清空</button>
        </div>
      </div>

      <div v-for="video in videos" :key="video.id" class="video-item">
        <div class="item-header">
          <span class="file-name">{{ video.file.name }}</span>
          <span class="status-badge" :class="video.status">
            {{ getStatusText(video.status) }}
          </span>
          <button
            v-if="video.status !== 'processing'"
            class="btn-remove"
            @click="removeVideo(video.id)"
          >
            ✕
          </button>
        </div>

        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: video.progress + '%' }"></div>
        </div>

        <div class="item-info">
          <span>{{ (video.file.size / 1024 / 1024).toFixed(2) }} MB</span>
          <span>{{ video.progress }}%</span>
        </div>

        <div v-if="video.statusMessage" class="status-message">
          {{ video.statusMessage }}
        </div>

        <div v-if="video.result" class="item-actions">
          <button
            v-if="video.result.markdown_content"
            class="btn-small"
            @click="downloadMarkdown(video)"
          >
            📥 下载 Markdown
          </button>
          <button
            v-if="video.result.pdf_content"
            class="btn-small"
            @click="downloadPDF(video)"
          >
            📥 下载 PDF
          </button>
        </div>

        <div v-if="video.error" class="error-message">
          ❌ {{ video.error }}
        </div>

        <div v-if="video.result?.metadata" class="metadata-preview">
          <details>
            <summary>查看元数据</summary>
            <table>
              <tr v-for="(value, key) in video.result.metadata" :key="key">
                <td class="key">{{ key }}</td>
                <td class="value">{{ formatValue(value) }}</td>
              </tr>
            </table>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
function getStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '转换中',
    completed: '已完成',
    failed: '失败',
  };
  return map[status] || status;
}

function formatValue(value: any): string {
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}
</script>

<style scoped>
.video-uploader {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.upload-zone {
  padding: 40px 20px;
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  text-align: center;
  transition: all 0.3s ease;
  background: #f9fafb;
  cursor: pointer;
}

.upload-zone.dragging {
  border-color: #667eea;
  background: #eef2ff;
}

.upload-content {
  pointer-events: none;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.upload-zone h3 {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: #111827;
}

.supported {
  margin: 0 0 16px 0;
  font-size: 13px;
  color: #6b7280;
}

.drag-hint {
  margin: 12px 0 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.btn-primary,
.btn-secondary,
.btn-small,
.btn-remove {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: #667eea;
  color: white;
  pointer-events: auto;
}

.btn-primary:hover:not(:disabled) {
  background: #5568d3;
  transform: translateY(-1px);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e5e7eb;
  color: #111827;
}

.btn-secondary:hover {
  background: #d1d5db;
}

.btn-small {
  padding: 6px 12px;
  font-size: 12px;
  background: #f0f4ff;
  color: #667eea;
}

.btn-small:hover {
  background: #e5ebff;
}

.btn-remove {
  padding: 4px 8px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 12px;
}

.btn-remove:hover {
  background: #fca5a5;
}

.options-panel {
  background: white;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}

.option-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.option-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-item label {
  font-weight: 500;
  font-size: 14px;
  color: #374151;
}

.option-item input[type='range'] {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: #e5e7eb;
  outline: none;
  -webkit-appearance: none;
}

.option-item input[type='range']::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #667eea;
  cursor: pointer;
}

.value-display {
  font-size: 12px;
  color: #6b7280;
}

.radio-group,
.checkbox-group {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.radio-group label,
.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  cursor: pointer;
}

.api-config {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.api-config label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  font-size: 14px;
}

.api-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.conversion-list {
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.list-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-header h4 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.list-actions {
  display: flex;
  gap: 8px;
}

.video-item {
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.video-item:last-child {
  border-bottom: none;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.file-name {
  flex: 1;
  font-weight: 500;
  color: #111827;
  word-break: break-all;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.pending {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.processing {
  background: #dbeafe;
  color: #0c4a6e;
  animation: pulse 1s infinite;
}

.status-badge.completed {
  background: #dcfce7;
  color: #166534;
}

.status-badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.3s ease;
}

.item-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.status-message {
  margin-bottom: 12px;
  font-size: 12px;
  color: #4b5563;
}

.item-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.error-message {
  padding: 8px 12px;
  background: #fee2e2;
  border-left: 3px solid #b91c1c;
  border-radius: 4px;
  color: #7f1d1d;
  font-size: 12px;
  margin-bottom: 12px;
}

.metadata-preview {
  margin-top: 12px;
}

.metadata-preview details {
  cursor: pointer;
}

.metadata-preview summary {
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 4px;
  font-size: 12px;
  color: #667eea;
  user-select: none;
}

.metadata-preview table {
  width: 100%;
  margin-top: 8px;
  border-collapse: collapse;
  font-size: 12px;
}

.metadata-preview tr {
  border-bottom: 1px solid #e5e7eb;
}

.metadata-preview td {
  padding: 6px;
}

.metadata-preview .key {
  font-weight: 500;
  width: 120px;
  color: #374151;
}

.metadata-preview .value {
  color: #6b7280;
  word-break: break-all;
  white-space: pre-wrap;
}
</style>

