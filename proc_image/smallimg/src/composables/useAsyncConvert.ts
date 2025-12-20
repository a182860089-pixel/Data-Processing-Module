import { ref } from 'vue'

export interface ConvertTask {
  taskId: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  message?: string
  result?: ConvertResult
  error?: string
}

export interface ConvertResult {
  markdownContent: string
  downloadUrl: string
  metadata: {
    pagesProcessed: number
    ocrPages: number
    textPages: number
    processingTime: number
    fileSize: number
    outputType: string
  }
}

export interface UseAsyncConvertOptions {
  /** API 基础 URL */
  baseUrl?: string
  /** 轮询间隔（毫秒），默认 1000ms */
  pollInterval?: number
  /** 最大轮询次数，默认 600（10分钟） */
  maxPolls?: number
  /** 初始延迟轮询（毫秒），避免立即轮询 */
  initialDelay?: number
}

/**
 * 异步文件转换 composable
 * 使用后端异步 API + 轮询机制，支持实时进度显示
 */
export function useAsyncConvert(options: UseAsyncConvertOptions = {}) {
  const {
    baseUrl = import.meta.env.VITE_PDF_API_BASE_URL ||
              import.meta.env.VITE_IMAGE_API_BASE_URL ||
              'http://localhost:8000',
    pollInterval = 1000,
    maxPolls = 600,
    initialDelay = 500,
  } = options

  const isConverting = ref(false)
  const currentTask = ref<ConvertTask | null>(null)
  const pollTimer = ref<number | null>(null)
  const pollCount = ref(0)

  /**
   * 提交文件进行异步转换
   */
  const submitConvert = async (
    file: File,
    convertOptions: Record<string, any> = {},
    onProgress?: (progress: number, message?: string) => void
  ): Promise<ConvertResult> => {
    isConverting.value = true
    pollCount.value = 0

    try {
      // 1. 提交到异步 API
      onProgress?.(5, '正在上传文件...')

      const formData = new FormData()
      formData.append('file', file)
      formData.append('options', JSON.stringify(convertOptions))

      const submitResp = await fetch(`${baseUrl}/api/v1/convert/async`, {
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

      onProgress?.(10, '任务已提交，正在处理...')

      currentTask.value = {
        taskId,
        status: 'processing',
        progress: 10,
      }

      // 2. 初始延迟后开始轮询
      await new Promise(resolve => setTimeout(resolve, initialDelay))

      // 3. 轮询任务状态
      const result = await pollTaskStatus(taskId, onProgress)
      
      onProgress?.(100, '转换完成')
      
      return result
    } catch (error) {
      currentTask.value = {
        taskId: currentTask.value?.taskId || '',
        status: 'failed',
        progress: 0,
        error: error instanceof Error ? error.message : '转换失败',
      }
      throw error
    } finally {
      isConverting.value = false
      stopPolling()
    }
  }

  /**
   * 轮询任务状态直到完成
   */
  const pollTaskStatus = (
    taskId: string,
    onProgress?: (progress: number, message?: string) => void
  ): Promise<ConvertResult> => {
    return new Promise((resolve, reject) => {
      const doPoll = async () => {
        pollCount.value++

        if (pollCount.value > maxPolls) {
          reject(new Error('轮询超时，任务可能仍在后台处理'))
          return
        }

        try {
          const resp = await fetch(`${baseUrl}/api/v1/status/${taskId}`)
          
          if (!resp.ok) {
            // 网络错误时继续重试
            schedulePoll()
            return
          }

          const data = await resp.json()
          const status = data.status

          // 更新进度
          if (data.progress?.percentage !== undefined) {
            const progress = Math.min(95, 10 + data.progress.percentage * 0.85)
            onProgress?.(progress, `处理中 (${data.progress.current_page || 0}/${data.progress.total_pages || '?'} 页)`)
            
            if (currentTask.value) {
              currentTask.value.progress = progress
            }
          }

          if (status === 'completed') {
            // 任务完成
            const result: ConvertResult = {
              markdownContent: data.result?.markdown_content || '',
              downloadUrl: data.result?.download_url || `/api/v1/download/${taskId}`,
              metadata: {
                pagesProcessed: data.result?.metadata?.pages_processed || 0,
                ocrPages: data.result?.metadata?.ocr_pages || 0,
                textPages: data.result?.metadata?.text_pages || 0,
                processingTime: data.result?.metadata?.processing_time || 0,
                fileSize: data.result?.metadata?.file_size || 0,
                outputType: data.result?.metadata?.output_type || 'markdown',
              },
            }

            if (currentTask.value) {
              currentTask.value.status = 'completed'
              currentTask.value.progress = 100
              currentTask.value.result = result
            }

            resolve(result)
            return
          }

          if (status === 'failed') {
            const errorMsg = data.error?.message || data.error?.details || '转换失败'
            reject(new Error(errorMsg))
            return
          }

          // 继续轮询
          schedulePoll()
        } catch (error) {
          // 网络错误时继续重试
          console.warn('轮询请求失败，将重试...', error)
          schedulePoll()
        }
      }

      const schedulePoll = () => {
        pollTimer.value = window.setTimeout(doPoll, pollInterval)
      }

      // 开始首次轮询
      doPoll()
    })
  }

  /**
   * 停止轮询
   */
  const stopPolling = () => {
    if (pollTimer.value !== null) {
      clearTimeout(pollTimer.value)
      pollTimer.value = null
    }
  }

  /**
   * 取消当前转换
   */
  const cancelConvert = () => {
    stopPolling()
    isConverting.value = false
    currentTask.value = null
  }

  return {
    isConverting,
    currentTask,
    pollCount,
    submitConvert,
    cancelConvert,
  }
}
