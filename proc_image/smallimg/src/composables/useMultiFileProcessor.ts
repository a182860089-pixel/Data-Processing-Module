import { ref, computed, reactive } from 'vue'

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface FileTask<T = any> {
  id: string
  file: File
  name: string
  size: number
  status: TaskStatus
  progress: number
  startTime: number
  endTime?: number
  result?: T
  error?: string
}

export interface ProcessorMetrics {
  totalTasks: number
  completedTasks: number
  failedTasks: number
  totalDuration: number
}

export interface UseMultiFileProcessorOptions {
  /** 最大并发数 */
  concurrency?: number
  /** 自动开始处理 */
  autoStart?: boolean
}

/**
 * 通用的多文件异步处理 composable
 * @param processFn 处理单个文件的函数，返回 Promise
 * @param options 配置选项
 */
export function useMultiFileProcessor<T = any>(
  processFn: (file: File, onProgress?: (progress: number) => void) => Promise<T>,
  options: UseMultiFileProcessorOptions = {}
) {
  const { concurrency = 3, autoStart = false } = options

  const tasks = ref<FileTask<T>[]>([])
  const isProcessing = ref(false)
  const abortController = ref<AbortController | null>(null)

  const metrics = reactive<ProcessorMetrics>({
    totalTasks: 0,
    completedTasks: 0,
    failedTasks: 0,
    totalDuration: 0,
  })

  const generateTaskId = () =>
    `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

  // 计算属性
  const pendingTasks = computed(() =>
    tasks.value.filter((t) => t.status === 'pending')
  )
  const processingTasks = computed(() =>
    tasks.value.filter((t) => t.status === 'processing')
  )
  const completedTasks = computed(() =>
    tasks.value.filter((t) => t.status === 'completed')
  )
  const failedTasks = computed(() =>
    tasks.value.filter((t) => t.status === 'failed')
  )
  const overallProgress = computed(() => {
    if (tasks.value.length === 0) return 0
    const total = tasks.value.reduce((sum, t) => sum + t.progress, 0)
    return Math.round(total / tasks.value.length)
  })

  /**
   * 添加文件到任务列表
   */
  const addFiles = (files: File[]): FileTask<T>[] => {
    const newTasks: FileTask<T>[] = files.map((file) => ({
      id: generateTaskId(),
      file,
      name: file.name,
      size: file.size,
      status: 'pending' as TaskStatus,
      progress: 0,
      startTime: 0,
    }))

    tasks.value.push(...newTasks)
    metrics.totalTasks = tasks.value.length

    if (autoStart && !isProcessing.value) {
      startProcessing()
    }

    return newTasks
  }

  /**
   * 移除任务
   */
  const removeTask = (taskId: string) => {
    const index = tasks.value.findIndex((t) => t.id === taskId)
    if (index !== -1) {
      const task = tasks.value[index]
      // 只能移除 pending 或已完成/失败的任务
      if (task.status !== 'processing') {
        tasks.value.splice(index, 1)
        metrics.totalTasks = tasks.value.length
        updateMetrics()
      }
    }
  }

  /**
   * 清空所有任务
   */
  const clearTasks = () => {
    if (isProcessing.value) {
      stopProcessing()
    }
    tasks.value = []
    resetMetrics()
  }

  /**
   * 处理单个任务
   */
  const processTask = async (task: FileTask<T>): Promise<void> => {
    task.status = 'processing'
    task.startTime = Date.now()
    task.progress = 0

    try {
      const result = await processFn(task.file, (progress) => {
        task.progress = Math.min(99, Math.max(0, Math.floor(progress)))
      })

      task.result = result
      task.status = 'completed'
      task.progress = 100
      task.endTime = Date.now()
      metrics.completedTasks++
    } catch (error) {
      task.status = 'failed'
      task.error = error instanceof Error ? error.message : '处理失败'
      task.endTime = Date.now()
      task.progress = 0
      metrics.failedTasks++
    }

    // 更新总耗时
    if (task.endTime && task.startTime) {
      metrics.totalDuration = Math.max(
        metrics.totalDuration,
        task.endTime - task.startTime
      )
    }
  }

  /**
   * 开始处理所有待处理任务
   */
  const startProcessing = async () => {
    if (isProcessing.value) return
    if (pendingTasks.value.length === 0) return

    isProcessing.value = true
    abortController.value = new AbortController()

    // 使用并发控制处理任务
    const pending = [...pendingTasks.value]
    const executing: Promise<void>[] = []

    for (const task of pending) {
      if (abortController.value?.signal.aborted) break

      const promise = processTask(task).then(() => {
        executing.splice(executing.indexOf(promise), 1)
      })
      executing.push(promise)

      if (executing.length >= concurrency) {
        await Promise.race(executing)
      }
    }

    // 等待所有正在执行的任务完成
    await Promise.all(executing)

    isProcessing.value = false
    abortController.value = null
  }

  /**
   * 停止处理
   */
  const stopProcessing = () => {
    if (abortController.value) {
      abortController.value.abort()
    }
    isProcessing.value = false
  }

  /**
   * 重试失败的任务
   */
  const retryFailed = async () => {
    const failed = failedTasks.value
    failed.forEach((task) => {
      task.status = 'pending'
      task.progress = 0
      task.error = undefined
    })
    metrics.failedTasks = 0
    await startProcessing()
  }

  /**
   * 重置指标
   */
  const resetMetrics = () => {
    metrics.totalTasks = 0
    metrics.completedTasks = 0
    metrics.failedTasks = 0
    metrics.totalDuration = 0
  }

  /**
   * 更新指标
   */
  const updateMetrics = () => {
    metrics.totalTasks = tasks.value.length
    metrics.completedTasks = completedTasks.value.length
    metrics.failedTasks = failedTasks.value.length
  }

  /**
   * 格式化文件大小
   */
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
  }

  /**
   * 获取任务耗时（秒）
   */
  const getTaskDuration = (task: FileTask<T>): number => {
    if (!task.startTime) return 0
    const endTime = task.endTime || Date.now()
    return Math.round((endTime - task.startTime) / 1000)
  }

  return {
    // 状态
    tasks,
    isProcessing,
    metrics,

    // 计算属性
    pendingTasks,
    processingTasks,
    completedTasks,
    failedTasks,
    overallProgress,

    // 方法
    addFiles,
    removeTask,
    clearTasks,
    startProcessing,
    stopProcessing,
    retryFailed,
    resetMetrics,

    // 工具函数
    formatFileSize,
    getTaskDuration,
  }
}
