"""批量任务管理器

基于内存的简单实现，用于管理批量转换批次信息。
后续如果接入 Celery/数据库，可以替换为持久化实现。
"""
from __future__ import annotations

import uuid
import logging
from typing import Dict, List, Any
from datetime import datetime

from app.models.batch import BatchTask
from app.models.enums import BatchStatus

logger = logging.getLogger(__name__)


class BatchManager:
    """批量任务管理器（内存版）"""

    def __init__(self) -> None:
        # 简单内存存储，生产环境应使用数据库或 Redis
        self._batches: Dict[str, BatchTask] = {}

    def create_batch(
        self,
        batch_name: str | None,
        task_summaries: List[Dict[str, Any]],
    ) -> BatchTask:
        """创建一个新的批量任务。

        当前实现为同步转换：当创建批次时，所有子任务已经完成，
        因此批次状态直接为 COMPLETED。
        """
        batch_id = self._generate_batch_id()

        batch = BatchTask(
            batch_id=batch_id,
            batch_name=batch_name,
            status=BatchStatus.COMPLETED,
            task_ids=[t["task_id"] for t in task_summaries],
            total_files=len(task_summaries),
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            metadata={},
            tasks=task_summaries,
        )

        # 计算整体进度和统计信息
        self._update_batch_aggregates(batch)

        self._batches[batch_id] = batch
        logger.info("Batch created: %s with %d tasks", batch_id, len(task_summaries))
        return batch

    def get_batch(self, batch_id: str) -> BatchTask:
        """获取批量任务信息。"""
        batch = self._batches.get(batch_id)
        if not batch:
            raise KeyError(f"Batch not found: {batch_id}")
        return batch

    def list_batches(self) -> List[BatchTask]:
        """列出所有批量任务。"""
        return list(self._batches.values())

    def _generate_batch_id(self) -> str:
        return f"batch_{uuid.uuid4().hex[:12]}"

    def _update_batch_aggregates(self, batch: BatchTask) -> None:
        """根据子任务计算批次聚合信息。"""
        total = batch.total_files or len(batch.tasks)
        completed = sum(1 for t in batch.tasks if t.get("status") == "completed")
        failed = sum(1 for t in batch.tasks if t.get("status") == "failed")

        if total > 0:
            progress_percentage = int(completed / total * 100)
        else:
            progress_percentage = 0

        if completed == total and total > 0:
            status = BatchStatus.COMPLETED
        elif failed == total and total > 0:
            status = BatchStatus.FAILED
        elif failed > 0 and completed > 0:
            status = BatchStatus.PARTIAL_FAILED
        elif completed > 0:
            status = BatchStatus.PROCESSING
        else:
            status = BatchStatus.QUEUED

        batch.status = status
        batch.metadata.update(
            {
                "total_files": total,
                "completed_files": completed,
                "failed_files": failed,
                "progress_percentage": progress_percentage,
            }
        )
