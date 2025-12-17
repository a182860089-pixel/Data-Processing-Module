"""
优先级任务队列
根据文件大小和类型智能排序任务
借鉴 VERT 项目的 byNative 排序机制
"""
import heapq
import asyncio
import logging
import time
from enum import IntEnum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """任务优先级"""
    URGENT = 1      # 紧急：小文件、纯文本 PDF
    HIGH = 2        # 高：中等大小、已缓存
    NORMAL = 3      # 普通：标准任务
    LOW = 4         # 低：大文件、复杂文档
    BACKGROUND = 5  # 后台：批量任务


@dataclass(order=True)
class PriorityTask:
    """优先级任务包装"""
    priority: int
    sequence: int  # 保证相同优先级的 FIFO 顺序
    task: Any = field(compare=False)
    created_at: float = field(default_factory=time.time, compare=False)


class PriorityTaskQueue:
    """
    优先级任务队列
    
    特点：
    - 根据文件特征自动估算优先级
    - 支持手动指定优先级
    - 线程安全
    - 支持异步操作
    """
    
    # 文件大小阈值（字节）
    SMALL_FILE_THRESHOLD = 1 * 1024 * 1024      # 1 MB
    MEDIUM_FILE_THRESHOLD = 10 * 1024 * 1024    # 10 MB
    LARGE_FILE_THRESHOLD = 50 * 1024 * 1024     # 50 MB
    
    def __init__(self, max_size: int = 1000):
        """
        初始化优先级队列
        
        Args:
            max_size: 队列最大容量
        """
        self._queue: List[PriorityTask] = []
        self._counter = 0
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        self._max_size = max_size
        
        logger.info(f"PriorityTaskQueue initialized with max_size={max_size}")
    
    def estimate_priority(
        self,
        file_size: int,
        file_type: str = "unknown",
        pdf_type: str = "unknown",
        is_cached: bool = False
    ) -> TaskPriority:
        """
        根据文件特征估算任务优先级
        
        Args:
            file_size: 文件大小（字节）
            file_type: 文件类型（pdf, image, office, video）
            pdf_type: PDF 类型（text, image, mixed）
            is_cached: 是否已有缓存
            
        Returns:
            TaskPriority: 估算的优先级
        """
        # 已缓存的任务优先级提高
        if is_cached:
            return TaskPriority.HIGH
        
        # 根据文件大小初步判断
        if file_size < self.SMALL_FILE_THRESHOLD:
            base_priority = TaskPriority.URGENT
        elif file_size < self.MEDIUM_FILE_THRESHOLD:
            base_priority = TaskPriority.HIGH
        elif file_size < self.LARGE_FILE_THRESHOLD:
            base_priority = TaskPriority.NORMAL
        else:
            base_priority = TaskPriority.LOW
        
        # 根据 PDF 类型调整
        if pdf_type == "text":
            # 纯文本 PDF 处理最快，提升优先级
            base_priority = TaskPriority(max(1, base_priority - 1))
        elif pdf_type == "image":
            # 纯图片 PDF 需要 OCR，降低优先级
            base_priority = TaskPriority(min(5, base_priority + 1))
        
        # 根据文件类型调整
        if file_type == "video":
            # 视频处理最慢
            base_priority = TaskPriority.LOW
        elif file_type == "office":
            # Office 文档需要转换
            base_priority = TaskPriority(min(5, base_priority))
        
        logger.debug(
            f"Estimated priority: {base_priority.name} "
            f"(size={file_size}, type={file_type}, pdf_type={pdf_type})"
        )
        
        return base_priority
    
    async def push(
        self,
        task: Dict[str, Any],
        priority: Optional[TaskPriority] = None
    ) -> bool:
        """
        将任务加入队列
        
        Args:
            task: 任务数据（必须包含 task_id）
            priority: 优先级（可选，默认自动估算）
            
        Returns:
            bool: 是否成功加入队列
        """
        async with self._lock:
            if len(self._queue) >= self._max_size:
                logger.warning("Queue is full, rejecting task")
                return False
            
            # 自动估算优先级
            if priority is None:
                priority = self.estimate_priority(
                    file_size=task.get('file_size', 0),
                    file_type=task.get('file_type', 'unknown'),
                    pdf_type=task.get('pdf_type', 'unknown'),
                    is_cached=task.get('is_cached', False)
                )
            
            # 创建优先级任务
            priority_task = PriorityTask(
                priority=priority.value,
                sequence=self._counter,
                task=task
            )
            self._counter += 1
            
            heapq.heappush(self._queue, priority_task)
            
            logger.debug(
                f"Task {task.get('task_id')} added with priority {priority.name}"
            )
            
            return True
    
    async def pop(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        从队列取出最高优先级任务
        
        Args:
            timeout: 超时时间（秒），None 表示不等待
            
        Returns:
            Optional[Dict]: 任务数据，队列为空时返回 None
        """
        async with self._lock:
            if self._queue:
                priority_task = heapq.heappop(self._queue)
                wait_time = time.time() - priority_task.created_at
                logger.debug(
                    f"Task popped: priority={priority_task.priority}, "
                    f"wait_time={wait_time:.2f}s"
                )
                return priority_task.task
            return None
    
    async def peek(self) -> Optional[Dict[str, Any]]:
        """查看队首任务但不移除"""
        async with self._lock:
            if self._queue:
                return self._queue[0].task
            return None
    
    def size(self) -> int:
        """获取队列大小"""
        return len(self._queue)
    
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return len(self._queue) == 0
    
    def is_full(self) -> bool:
        """检查队列是否已满"""
        return len(self._queue) >= self._max_size
    
    async def clear(self):
        """清空队列"""
        async with self._lock:
            self._queue.clear()
            self._counter = 0
            logger.info("Queue cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        if not self._queue:
            return {
                "size": 0,
                "priority_distribution": {}
            }
        
        # 统计各优先级任务数量
        priority_counts = {}
        for task in self._queue:
            priority_name = TaskPriority(task.priority).name
            priority_counts[priority_name] = priority_counts.get(priority_name, 0) + 1
        
        return {
            "size": len(self._queue),
            "max_size": self._max_size,
            "priority_distribution": priority_counts,
            "oldest_task_wait_time": time.time() - self._queue[0].created_at if self._queue else 0
        }


class BatchTaskScheduler:
    """
    批量任务调度器
    
    将批量任务拆分为单个任务，根据优先级调度执行
    """
    
    def __init__(
        self,
        task_queue: PriorityTaskQueue,
        max_concurrent: int = 5
    ):
        """
        初始化调度器
        
        Args:
            task_queue: 优先级任务队列
            max_concurrent: 最大并发任务数
        """
        self.queue = task_queue
        self.max_concurrent = max_concurrent
        self._running = False
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def schedule_batch(
        self,
        tasks: List[Dict[str, Any]],
        batch_priority: TaskPriority = TaskPriority.BACKGROUND
    ) -> List[str]:
        """
        调度批量任务
        
        Args:
            tasks: 任务列表
            batch_priority: 批量任务的基础优先级
            
        Returns:
            List[str]: 成功加入队列的任务 ID 列表
        """
        scheduled_ids = []
        
        # 按估算的处理时间排序（短任务优先）
        sorted_tasks = sorted(
            tasks,
            key=lambda t: t.get('file_size', 0)
        )
        
        for task in sorted_tasks:
            # 对于批量任务，使用较低的优先级但保持相对顺序
            priority = max(
                batch_priority,
                self.queue.estimate_priority(
                    file_size=task.get('file_size', 0),
                    file_type=task.get('file_type', 'unknown'),
                    pdf_type=task.get('pdf_type', 'unknown')
                )
            )
            
            if await self.queue.push(task, priority):
                scheduled_ids.append(task.get('task_id'))
        
        logger.info(
            f"Scheduled {len(scheduled_ids)} tasks from batch "
            f"with base priority {batch_priority.name}"
        )
        
        return scheduled_ids
    
    async def process_queue(
        self,
        processor: Callable[[Dict[str, Any]], Any],
        result_callback: Optional[Callable[[str, Any], None]] = None
    ):
        """
        持续处理队列中的任务
        
        Args:
            processor: 任务处理函数
            result_callback: 结果回调函数
        """
        self._running = True
        
        while self._running:
            task = await self.queue.pop()
            
            if task is None:
                # 队列为空，等待一段时间
                await asyncio.sleep(0.1)
                continue
            
            # 使用信号量限制并发
            async with self._semaphore:
                task_id = task.get('task_id')
                try:
                    result = await processor(task)
                    if result_callback:
                        result_callback(task_id, result)
                except Exception as e:
                    logger.error(f"Error processing task {task_id}: {e}")
                    if result_callback:
                        result_callback(task_id, e)
    
    def stop(self):
        """停止调度器"""
        self._running = False


# 全局实例
priority_queue = PriorityTaskQueue()
