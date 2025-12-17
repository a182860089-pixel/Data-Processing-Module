"""
优化的批量任务管理器
整合动态并发、流式处理、优先级队列和缓存机制
"""
import os
import uuid
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from app.models.batch import BatchTask
from app.models.enums import BatchStatus
from app.services.conversion.conversion_service import ConversionService
from app.utils.concurrency import concurrency_manager, DynamicConcurrencyManager
from app.utils.priority_queue import PriorityTaskQueue, TaskPriority
from app.utils.performance import performance_manager, PerformanceTimer
from app.utils.cache import get_conversion_cache
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FileTask:
    """文件任务"""
    task_id: str
    file_path: str
    filename: str
    file_size: int
    options: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL


class OptimizedBatchManager:
    """
    优化的批量任务管理器
    
    特点：
    - 动态并发控制：根据系统资源自动调整
    - 智能优先级：小文件/简单文件优先处理
    - 结果缓存：避免重复处理相同文件
    - 性能监控：实时收集指标并自适应调整
    - 流式处理：分批处理减少内存压力
    """
    
    def __init__(
        self,
        max_concurrent_files: int = None,
        batch_size: int = 5
    ):
        """
        初始化优化批量管理器
        
        Args:
            max_concurrent_files: 最大并发文件数（None 时动态计算）
            batch_size: 每批处理的文件数
        """
        self.settings = get_settings()
        self.conversion_service = ConversionService()
        self.priority_queue = PriorityTaskQueue()
        self.batch_size = batch_size
        
        # 动态并发管理
        self.concurrency_manager = concurrency_manager
        self.max_concurrent = max_concurrent_files or \
            self.concurrency_manager.get_optimal_concurrency("io_bound")
        
        # 批次存储
        self._batches: Dict[str, BatchTask] = {}
        self._batch_results: Dict[str, Dict[str, Any]] = {}
        
        logger.info(
            f"OptimizedBatchManager initialized: "
            f"max_concurrent={self.max_concurrent}, batch_size={batch_size}"
        )
    
    async def process_batch(
        self,
        files: List[Dict[str, Any]],
        options: Dict[str, Any],
        batch_name: Optional[str] = None
    ) -> BatchTask:
        """
        处理批量文件转换
        
        Args:
            files: 文件列表 [{"path": str, "filename": str}, ...]
            options: 转换选项
            batch_name: 批次名称
            
        Returns:
            BatchTask: 批次任务信息
        """
        batch_id = self._generate_batch_id()
        
        # 创建批次
        batch = BatchTask(
            batch_id=batch_id,
            batch_name=batch_name,
            status=BatchStatus.PROCESSING,
            task_ids=[],
            total_files=len(files),
            created_at=datetime.utcnow(),
            metadata={"options": options},
            tasks=[]
        )
        self._batches[batch_id] = batch
        self._batch_results[batch_id] = {}
        
        logger.info(f"Starting batch {batch_id} with {len(files)} files")
        
        try:
            # 1. 预分析文件，创建任务并排序
            file_tasks = await self._analyze_and_prioritize(files, options)
            batch.task_ids = [t.task_id for t in file_tasks]
            
            # 2. 检查缓存
            cache = get_conversion_cache()
            cached_results = []
            tasks_to_process = []
            
            for task in file_tasks:
                cached = await cache.get(task.file_path, task.options)
                if cached:
                    logger.info(f"Cache hit for {task.filename}")
                    cached_results.append({
                        "task_id": task.task_id,
                        "filename": task.filename,
                        "status": "completed",
                        "from_cache": True,
                        "result": cached
                    })
                else:
                    tasks_to_process.append(task)
            
            # 3. 动态获取并发数
            adjustment = performance_manager.suggest_concurrency_adjustment()
            optimal_concurrent = self.concurrency_manager.get_optimal_concurrency(
                "io_bound", adjustment
            )
            semaphore = asyncio.Semaphore(optimal_concurrent)
            
            logger.info(
                f"Processing {len(tasks_to_process)} files with "
                f"concurrency={optimal_concurrent}"
            )
            
            # 4. 分批并发处理
            processed_results = await self._process_files_batched(
                tasks_to_process,
                semaphore,
                batch_id,
                options
            )
            
            # 5. 合并结果
            all_results = cached_results + processed_results
            
            # 6. 更新批次状态
            self._update_batch_status(batch, all_results)
            
            return batch
            
        except Exception as e:
            logger.error(f"Batch {batch_id} failed: {e}")
            batch.status = BatchStatus.FAILED
            batch.metadata["error"] = str(e)
            raise
    
    async def _analyze_and_prioritize(
        self,
        files: List[Dict[str, Any]],
        options: Dict[str, Any]
    ) -> List[FileTask]:
        """分析文件并按优先级排序"""
        tasks = []
        
        for file_info in files:
            file_path = file_info.get("path")
            filename = file_info.get("filename", os.path.basename(file_path))
            
            # 获取文件大小
            try:
                file_size = os.path.getsize(file_path)
            except Exception:
                file_size = 0
            
            # 检测文件类型
            file_type = self._detect_file_type(filename)
            
            # 估算优先级
            priority = self.priority_queue.estimate_priority(
                file_size=file_size,
                file_type=file_type
            )
            
            task = FileTask(
                task_id=self._generate_task_id(),
                file_path=file_path,
                filename=filename,
                file_size=file_size,
                options=options,
                priority=priority
            )
            tasks.append(task)
        
        # 按优先级排序（小优先级值优先）
        tasks.sort(key=lambda t: (t.priority.value, t.file_size))
        
        logger.debug(f"Prioritized {len(tasks)} tasks")
        return tasks
    
    async def _process_files_batched(
        self,
        tasks: List[FileTask],
        semaphore: asyncio.Semaphore,
        batch_id: str,
        options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """分批处理文件"""
        results = []
        total = len(tasks)
        
        for i in range(0, total, self.batch_size):
            batch_tasks = tasks[i:i + self.batch_size]
            
            logger.debug(
                f"Processing batch {i // self.batch_size + 1}: "
                f"files {i + 1}-{min(i + self.batch_size, total)}"
            )
            
            # 创建并发任务
            coros = [
                self._process_single_file(task, semaphore, batch_id)
                for task in batch_tasks
            ]
            
            # 并发执行
            batch_results = await asyncio.gather(*coros, return_exceptions=True)
            
            # 收集结果
            for task, result in zip(batch_tasks, batch_results):
                if isinstance(result, Exception):
                    results.append({
                        "task_id": task.task_id,
                        "filename": task.filename,
                        "status": "failed",
                        "error": str(result)
                    })
                else:
                    results.append(result)
            
            # 更新批次进度
            completed = len(results)
            self._batches[batch_id].metadata["progress"] = int(completed / total * 100)
        
        return results
    
    async def _process_single_file(
        self,
        task: FileTask,
        semaphore: asyncio.Semaphore,
        batch_id: str
    ) -> Dict[str, Any]:
        """处理单个文件"""
        async with semaphore:
            # 记录性能指标
            performance_manager.start_task(task.task_id, task.file_size)
            
            try:
                async with PerformanceTimer("file_conversion"):
                    result = await self.conversion_service.convert(
                        task.file_path,
                        task.filename,
                        task.options
                    )
                
                # 缓存结果
                cache = get_conversion_cache()
                await cache.set(
                    task.file_path,
                    task.options,
                    result.get("markdown_content", ""),
                    result.get("metadata", {})
                )
                
                performance_manager.end_task(
                    task.task_id,
                    success=True,
                    pages_processed=result.get("metadata", {}).get("total_pages", 0)
                )
                
                return {
                    "task_id": task.task_id,
                    "filename": task.filename,
                    "status": "completed",
                    "result": result
                }
                
            except Exception as e:
                performance_manager.end_task(
                    task.task_id,
                    success=False,
                    error_message=str(e)
                )
                logger.error(f"Failed to process {task.filename}: {e}")
                raise
    
    def _update_batch_status(
        self,
        batch: BatchTask,
        results: List[Dict[str, Any]]
    ):
        """更新批次状态"""
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        total = len(results)
        
        if completed == total:
            batch.status = BatchStatus.COMPLETED
        elif failed == total:
            batch.status = BatchStatus.FAILED
        elif failed > 0:
            batch.status = BatchStatus.PARTIAL_FAILED
        else:
            batch.status = BatchStatus.COMPLETED
        
        batch.completed_at = datetime.utcnow()
        batch.tasks = results
        batch.metadata.update({
            "total_files": total,
            "completed_files": completed,
            "failed_files": failed,
            "progress_percentage": 100,
            "cached_files": sum(1 for r in results if r.get("from_cache"))
        })
        
        logger.info(
            f"Batch {batch.batch_id} completed: "
            f"{completed}/{total} succeeded, {failed} failed"
        )
    
    def _detect_file_type(self, filename: str) -> str:
        """检测文件类型"""
        ext = os.path.splitext(filename)[1].lower()
        
        if ext == ".pdf":
            return "pdf"
        elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            return "image"
        elif ext in [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]:
            return "office"
        elif ext in [".mp4", ".avi", ".mov", ".mkv"]:
            return "video"
        else:
            return "unknown"
    
    def _generate_batch_id(self) -> str:
        return f"batch_{uuid.uuid4().hex[:12]}"
    
    def _generate_task_id(self) -> str:
        return f"task_{uuid.uuid4().hex[:12]}"
    
    def get_batch(self, batch_id: str) -> BatchTask:
        """获取批次信息"""
        batch = self._batches.get(batch_id)
        if not batch:
            raise KeyError(f"Batch not found: {batch_id}")
        return batch
    
    def list_batches(self) -> List[BatchTask]:
        """列出所有批次"""
        return list(self._batches.values())
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            "performance": performance_manager.get_report(),
            "cache": get_conversion_cache().get_stats(),
            "queue": self.priority_queue.get_stats()
        }


# 全局实例
optimized_batch_manager = OptimizedBatchManager()
