import { ref, computed } from 'vue'

export interface PollTask {
  id: string
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  pollCount: number
  startTime: number
  endTime?: number
  result?: any
  error?: string
}

export interface PollMetrics {
  totalPolls: number
  successPolls: number
  failedPolls: number
  avgPollInterval: number
  totalDuration: number
}

export function useAsyncPolling() {
  const tasks = ref<PollTask[]>([])
  const metrics = ref<PollMetrics>({
    totalPolls: 0,
    successPolls: 0,
    failedPolls: 0,
    avgPollInterval: 0,
    totalDuration: 0,
  })

  const pollIntervals = ref<number[]>([])
  const pollTimers = new Map<string, number>()

  const generateTaskId = () =>
    `task-${Date.now()}-${Math.random().toString(36).slice(2)}`

  const createTask = (name: string): PollTask => ({
    id: generateTaskId(),
    name,
    status: 'pending',
    progress: 0,
    pollCount: 0,
    startTime: Date.now(),
  })

  /**
   * 启动轮询任务
   * @param task 任务对象
   * @param pollFn 轮询函数，返回当前进度 (0-100)
   * @param interval 轮询间隔（毫秒）
   * @param timeout 任务超时时间（毫秒）
   */
  const startPolling = (
    task: PollTask,
    pollFn: () => Promise<number>,
    interval: number = 1000,
    timeout: number = 30000
  ) => {
    task.status = 'processing'
    task.startTime = Date.now()
    const timeoutTimer = setTimeout(() => {
      stopPolling(task.id)
      task.status = 'failed'
      task.error = '轮询超时'
      metrics.value.failedPolls++
    }, timeout)

    const pollTimer = window.setInterval(async () => {
      const pollStartTime = Date.now()
      try {
        const progress = await pollFn()
        task.progress = Math.floor(Math.min(progress, 100))
        task.pollCount++
        metrics.value.totalPolls++

        if (progress >= 100) {
          task.status = 'completed'
          task.endTime = Date.now()
          metrics.value.successPolls++
          metrics.value.totalDuration = Math.max(
            metrics.value.totalDuration,
            task.endTime - task.startTime
          )
          stopPolling(task.id)
          clearTimeout(timeoutTimer)
        } else {
          metrics.value.successPolls++
        }

        const pollDuration = Date.now() - pollStartTime
        pollIntervals.value.push(pollDuration)

        if (pollIntervals.value.length > 0) {
          metrics.value.avgPollInterval = Math.round(
            pollIntervals.value.reduce((a, b) => a + b, 0) /
              pollIntervals.value.length
          )
        }
      } catch (e) {
        task.status = 'failed'
        task.error = e instanceof Error ? e.message : '轮询出错'
        metrics.value.failedPolls++
        stopPolling(task.id)
        clearTimeout(timeoutTimer)
      }
    }, interval)

    pollTimers.set(task.id, pollTimer)
  }

  const stopPolling = (taskId: string) => {
    const timerId = pollTimers.get(taskId)
    if (timerId !== undefined) {
      clearInterval(timerId)
      pollTimers.delete(taskId)
    }
  }

  const stopAllPolling = () => {
    pollTimers.forEach(timerId => clearInterval(timerId))
    pollTimers.clear()
  }

  const resetMetrics = () => {
    pollIntervals.value = []
    metrics.value = {
      totalPolls: 0,
      successPolls: 0,
      failedPolls: 0,
      avgPollInterval: 0,
      totalDuration: 0,
    }
  }

  const cleanup = () => {
    stopAllPolling()
  }

  const activeTaskCount = computed(() =>
    tasks.value.filter(t => t.status === 'processing').length
  )

  const completedTaskCount = computed(() =>
    tasks.value.filter(t => t.status === 'completed').length
  )

  const failedTaskCount = computed(() =>
    tasks.value.filter(t => t.status === 'failed').length
  )

  return {
    tasks,
    metrics,
    activeTaskCount,
    completedTaskCount,
    failedTaskCount,
    createTask,
    startPolling,
    stopPolling,
    stopAllPolling,
    resetMetrics,
    cleanup,
  }
}
