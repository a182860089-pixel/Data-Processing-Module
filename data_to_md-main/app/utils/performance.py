"""
性能监控与自适应调整
收集性能指标，根据运行状况动态调整并发数
"""
import time
import logging
from collections import deque
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    avg_processing_time: float = 0.0      # 平均处理时间（秒）
    avg_api_latency: float = 0.0          # 平均 API 延迟（秒）
    throughput: float = 0.0               # 吞吐量（任务/分钟）
    error_rate: float = 0.0               # 错误率
    current_concurrency: int = 0          # 当前并发数
    queue_size: int = 0                   # 队列大小
    memory_usage_mb: float = 0.0          # 内存使用（MB）


@dataclass
class TaskMetrics:
    """单个任务的性能指标"""
    task_id: str
    start_time: float
    end_time: Optional[float] = None
    api_latency: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    file_size: int = 0
    pages_processed: int = 0


class AdaptivePerformanceManager:
    """
    自适应性能管理器
    
    功能：
    - 收集任务性能指标
    - 计算统计数据
    - 根据性能自动建议并发数调整
    - 提供性能报告
    """
    
    # 自适应调整阈值
    ERROR_RATE_HIGH = 0.10      # 错误率 > 10% 时降低并发
    ERROR_RATE_LOW = 0.02       # 错误率 < 2% 时可增加并发
    LATENCY_HIGH = 5.0          # API 延迟 > 5s 时降低并发
    LATENCY_LOW = 1.0           # API 延迟 < 1s 时可增加并发
    
    def __init__(
        self,
        window_size: int = 100,
        adjustment_interval: int = 60
    ):
        """
        初始化性能管理器
        
        Args:
            window_size: 滑动窗口大小（保留最近 N 个任务的数据）
            adjustment_interval: 调整间隔（秒）
        """
        self.window_size = window_size
        self.adjustment_interval = adjustment_interval
        
        # 滑动窗口存储
        self._processing_times: deque = deque(maxlen=window_size)
        self._api_latencies: deque = deque(maxlen=window_size)
        self._errors: deque = deque(maxlen=window_size)
        self._file_sizes: deque = deque(maxlen=window_size)
        
        # 统计信息
        self._start_time = time.time()
        self._total_processed = 0
        self._total_errors = 0
        self._current_concurrency = 0
        
        # 上次调整时间
        self._last_adjustment_time = time.time()
        self._last_adjustment = 0
        
        # 活跃任务追踪
        self._active_tasks: Dict[str, TaskMetrics] = {}
        
        logger.info(
            f"AdaptivePerformanceManager initialized: "
            f"window_size={window_size}, adjustment_interval={adjustment_interval}s"
        )
    
    def start_task(
        self,
        task_id: str,
        file_size: int = 0
    ) -> TaskMetrics:
        """
        记录任务开始
        
        Args:
            task_id: 任务 ID
            file_size: 文件大小（字节）
            
        Returns:
            TaskMetrics: 任务指标对象
        """
        metrics = TaskMetrics(
            task_id=task_id,
            start_time=time.time(),
            file_size=file_size
        )
        self._active_tasks[task_id] = metrics
        self._current_concurrency = len(self._active_tasks)
        
        logger.debug(f"Task started: {task_id}, active={self._current_concurrency}")
        return metrics
    
    def record_api_call(
        self,
        task_id: str,
        latency: float
    ):
        """
        记录 API 调用延迟
        
        Args:
            task_id: 任务 ID
            latency: API 延迟（秒）
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id].api_latency += latency
        self._api_latencies.append(latency)
    
    def end_task(
        self,
        task_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
        pages_processed: int = 0
    ):
        """
        记录任务结束
        
        Args:
            task_id: 任务 ID
            success: 是否成功
            error_message: 错误信息
            pages_processed: 处理的页数
        """
        if task_id not in self._active_tasks:
            logger.warning(f"Unknown task ended: {task_id}")
            return
        
        metrics = self._active_tasks.pop(task_id)
        metrics.end_time = time.time()
        metrics.success = success
        metrics.error_message = error_message
        metrics.pages_processed = pages_processed
        
        # 记录处理时间
        processing_time = metrics.end_time - metrics.start_time
        self._processing_times.append(processing_time)
        self._file_sizes.append(metrics.file_size)
        
        # 记录成功/失败
        self._errors.append(0 if success else 1)
        self._total_processed += 1
        if not success:
            self._total_errors += 1
        
        self._current_concurrency = len(self._active_tasks)
        
        logger.debug(
            f"Task ended: {task_id}, success={success}, "
            f"time={processing_time:.2f}s, pages={pages_processed}"
        )
    
    def get_metrics(self) -> PerformanceMetrics:
        """
        获取当前性能指标
        
        Returns:
            PerformanceMetrics: 性能指标对象
        """
        elapsed = time.time() - self._start_time
        
        # 计算平均值
        avg_processing = (
            sum(self._processing_times) / len(self._processing_times)
            if self._processing_times else 0
        )
        avg_latency = (
            sum(self._api_latencies) / len(self._api_latencies)
            if self._api_latencies else 0
        )
        error_rate = (
            sum(self._errors) / len(self._errors)
            if self._errors else 0
        )
        throughput = (
            self._total_processed / (elapsed / 60)
            if elapsed > 0 else 0
        )
        
        # 获取内存使用
        memory_mb = 0
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
        except Exception:
            pass
        
        return PerformanceMetrics(
            avg_processing_time=round(avg_processing, 2),
            avg_api_latency=round(avg_latency, 2),
            throughput=round(throughput, 2),
            error_rate=round(error_rate, 4),
            current_concurrency=self._current_concurrency,
            memory_usage_mb=round(memory_mb, 1)
        )
    
    def suggest_concurrency_adjustment(self) -> int:
        """
        根据性能指标建议并发数调整
        
        Returns:
            int: 建议的调整值（正数增加，负数减少，0不变）
        """
        # 检查调整间隔
        if time.time() - self._last_adjustment_time < self.adjustment_interval:
            return 0
        
        metrics = self.get_metrics()
        adjustment = 0
        reason = ""
        
        # 根据错误率调整
        if metrics.error_rate > self.ERROR_RATE_HIGH:
            adjustment = -2
            reason = f"high error rate ({metrics.error_rate:.1%})"
        elif metrics.error_rate > self.ERROR_RATE_LOW * 2:
            adjustment = -1
            reason = f"moderate error rate ({metrics.error_rate:.1%})"
        
        # 根据 API 延迟调整（如果错误率正常）
        if adjustment == 0:
            if metrics.avg_api_latency > self.LATENCY_HIGH:
                adjustment = -1
                reason = f"high API latency ({metrics.avg_api_latency:.1f}s)"
            elif (
                metrics.avg_api_latency < self.LATENCY_LOW
                and metrics.error_rate < self.ERROR_RATE_LOW
            ):
                adjustment = 1
                reason = f"low latency ({metrics.avg_api_latency:.1f}s) and error rate"
        
        if adjustment != 0:
            self._last_adjustment_time = time.time()
            self._last_adjustment = adjustment
            logger.info(
                f"Concurrency adjustment suggested: {adjustment:+d} ({reason})"
            )
        
        return adjustment
    
    def get_report(self) -> Dict[str, Any]:
        """
        生成性能报告
        
        Returns:
            Dict: 性能报告
        """
        metrics = self.get_metrics()
        elapsed = time.time() - self._start_time
        
        # 计算处理速度
        avg_speed = 0
        if self._processing_times and self._file_sizes:
            total_size = sum(self._file_sizes)
            total_time = sum(self._processing_times)
            if total_time > 0:
                avg_speed = total_size / total_time / (1024 * 1024)  # MB/s
        
        return {
            "summary": {
                "total_processed": self._total_processed,
                "total_errors": self._total_errors,
                "success_rate": round(
                    (1 - self._total_errors / self._total_processed) * 100
                    if self._total_processed > 0 else 100,
                    2
                ),
                "uptime_seconds": round(elapsed, 1),
                "avg_processing_speed_mbps": round(avg_speed, 2)
            },
            "current_metrics": {
                "avg_processing_time": metrics.avg_processing_time,
                "avg_api_latency": metrics.avg_api_latency,
                "throughput_per_minute": metrics.throughput,
                "error_rate_percent": round(metrics.error_rate * 100, 2),
                "current_concurrency": metrics.current_concurrency,
                "memory_usage_mb": metrics.memory_usage_mb
            },
            "active_tasks": len(self._active_tasks),
            "last_adjustment": self._last_adjustment,
            "window_size": self.window_size
        }
    
    def reset(self):
        """重置所有统计数据"""
        self._processing_times.clear()
        self._api_latencies.clear()
        self._errors.clear()
        self._file_sizes.clear()
        self._start_time = time.time()
        self._total_processed = 0
        self._total_errors = 0
        self._active_tasks.clear()
        self._last_adjustment_time = time.time()
        self._last_adjustment = 0
        
        logger.info("Performance manager reset")


class PerformanceTimer:
    """
    性能计时器上下文管理器
    
    用于方便地记录代码块执行时间
    """
    
    def __init__(
        self,
        name: str,
        callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        初始化计时器
        
        Args:
            name: 计时器名称
            callback: 完成时的回调函数
        """
        self.name = name
        self.callback = callback
        self.start_time: float = 0
        self.elapsed: float = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        if self.callback:
            self.callback(self.name, self.elapsed)
        logger.debug(f"Timer [{self.name}]: {self.elapsed:.3f}s")
        return False
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        if self.callback:
            self.callback(self.name, self.elapsed)
        logger.debug(f"Timer [{self.name}]: {self.elapsed:.3f}s")
        return False


# 全局性能管理器实例
performance_manager = AdaptivePerformanceManager()
