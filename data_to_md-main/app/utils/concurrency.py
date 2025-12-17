"""
动态并发管理器
根据系统资源和任务类型动态调整并发数
借鉴 VERT 项目的 PQueue 动态并发机制
"""
import os
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class SystemResources:
    """系统资源信息"""
    cpu_count: int
    memory_available_gb: float
    memory_total_gb: float
    memory_percent: float


class DynamicConcurrencyManager:
    """
    动态并发管理器
    
    根据以下因素动态调整并发数：
    - CPU 核心数
    - 可用内存
    - 任务类型（I/O 密集型 vs CPU 密集型）
    - 历史性能指标
    """
    
    def __init__(
        self,
        min_concurrent: int = 2,
        max_concurrent: int = 20,
        memory_per_task_mb: float = 200
    ):
        """
        初始化动态并发管理器
        
        Args:
            min_concurrent: 最小并发数
            max_concurrent: 最大并发数
            memory_per_task_mb: 每个任务预估内存占用（MB）
        """
        self.min_concurrent = min_concurrent
        self.max_concurrent = max_concurrent
        self.memory_per_task_mb = memory_per_task_mb
        
        # 缓存系统资源信息
        self._cached_resources: Optional[SystemResources] = None
        self._cache_time: float = 0
        self._cache_ttl: float = 5.0  # 缓存 5 秒
        
        logger.info(
            f"DynamicConcurrencyManager initialized: "
            f"min={min_concurrent}, max={max_concurrent}, "
            f"memory_per_task={memory_per_task_mb}MB"
        )
    
    def get_system_resources(self) -> SystemResources:
        """获取系统资源信息"""
        import time
        
        current_time = time.time()
        if (
            self._cached_resources is not None
            and current_time - self._cache_time < self._cache_ttl
        ):
            return self._cached_resources
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            self._cached_resources = SystemResources(
                cpu_count=os.cpu_count() or 4,
                memory_available_gb=memory.available / (1024 ** 3),
                memory_total_gb=memory.total / (1024 ** 3),
                memory_percent=memory.percent
            )
        except ImportError:
            # psutil 未安装，使用默认值
            logger.warning("psutil not installed, using default resource values")
            self._cached_resources = SystemResources(
                cpu_count=os.cpu_count() or 4,
                memory_available_gb=8.0,
                memory_total_gb=16.0,
                memory_percent=50.0
            )
        
        self._cache_time = current_time
        return self._cached_resources
    
    def get_optimal_concurrency(
        self,
        task_type: str = "io_bound",
        adjustment: int = 0
    ) -> int:
        """
        根据系统资源和任务类型计算最优并发数
        
        Args:
            task_type: 任务类型
                - "io_bound": I/O 密集型（如 API 调用）
                - "cpu_bound": CPU 密集型（如 PDF 渲染）
                - "mixed": 混合型
            adjustment: 外部调整值（来自性能管理器的建议）
            
        Returns:
            int: 最优并发数
        """
        resources = self.get_system_resources()
        cpu_count = resources.cpu_count
        memory_available_gb = resources.memory_available_gb
        
        # 根据任务类型计算基础并发数
        if task_type == "io_bound":
            # I/O 密集型：并发数 = CPU 核心数 * 2-4
            # 因为大部分时间在等待 I/O，可以有更多并发
            base_concurrent = cpu_count * 3
        elif task_type == "cpu_bound":
            # CPU 密集型：并发数 = CPU 核心数
            # 超过核心数反而会增加上下文切换开销
            base_concurrent = cpu_count
        else:  # mixed
            base_concurrent = cpu_count * 2
        
        # 内存限制：每个任务约需指定内存
        memory_limit = int(
            (memory_available_gb * 1024) / self.memory_per_task_mb
        )
        
        # 取最小值作为实际并发数
        optimal = min(base_concurrent, memory_limit)
        
        # 应用外部调整
        optimal += adjustment
        
        # 限制在配置范围内
        result = max(self.min_concurrent, min(optimal, self.max_concurrent))
        
        logger.debug(
            f"Calculated concurrency: base={base_concurrent}, "
            f"memory_limit={memory_limit}, adjustment={adjustment}, "
            f"result={result}"
        )
        
        return result
    
    def create_semaphore(
        self,
        task_type: str = "io_bound",
        adjustment: int = 0
    ) -> asyncio.Semaphore:
        """
        创建动态信号量
        
        Args:
            task_type: 任务类型
            adjustment: 并发数调整值
            
        Returns:
            asyncio.Semaphore: 信号量对象
        """
        concurrency = self.get_optimal_concurrency(task_type, adjustment)
        logger.info(f"Creating semaphore with concurrency={concurrency}")
        return asyncio.Semaphore(concurrency)


class WorkerPool:
    """
    Worker 池管理器
    
    提供进程池和线程池，用于执行不同类型的任务：
    - ProcessPoolExecutor: CPU 密集型任务（PDF 渲染、图像处理）
    - ThreadPoolExecutor: I/O 密集型任务（文件读写）
    """
    
    _instance: Optional["WorkerPool"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        max_process_workers: Optional[int] = None,
        max_thread_workers: Optional[int] = None
    ):
        """
        初始化 Worker 池
        
        Args:
            max_process_workers: 进程池最大 worker 数
            max_thread_workers: 线程池最大 worker 数
        """
        if hasattr(self, "_initialized") and self._initialized:
            return
        
        cpu_count = os.cpu_count() or 4
        self.max_process_workers = max_process_workers or cpu_count
        self.max_thread_workers = max_thread_workers or (cpu_count * 2)
        
        self._process_pool: Optional[ProcessPoolExecutor] = None
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self._initialized = True
        
        logger.info(
            f"WorkerPool initialized: "
            f"process_workers={self.max_process_workers}, "
            f"thread_workers={self.max_thread_workers}"
        )
    
    @property
    def process_pool(self) -> ProcessPoolExecutor:
        """获取进程池（延迟创建）"""
        if self._process_pool is None:
            self._process_pool = ProcessPoolExecutor(
                max_workers=self.max_process_workers
            )
        return self._process_pool
    
    @property
    def thread_pool(self) -> ThreadPoolExecutor:
        """获取线程池（延迟创建）"""
        if self._thread_pool is None:
            self._thread_pool = ThreadPoolExecutor(
                max_workers=self.max_thread_workers
            )
        return self._thread_pool
    
    async def run_in_process(self, func, *args):
        """
        在进程池中执行函数（用于 CPU 密集型任务）
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            
        Returns:
            函数执行结果
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.process_pool, func, *args)
    
    async def run_in_thread(self, func, *args):
        """
        在线程池中执行函数（用于 I/O 密集型任务）
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            
        Returns:
            函数执行结果
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args)
    
    def shutdown(self, wait: bool = True):
        """关闭 Worker 池"""
        if self._process_pool:
            self._process_pool.shutdown(wait=wait)
            self._process_pool = None
        if self._thread_pool:
            self._thread_pool.shutdown(wait=wait)
            self._thread_pool = None
        logger.info("WorkerPool shutdown complete")


# 全局实例
concurrency_manager = DynamicConcurrencyManager()
worker_pool = WorkerPool()
