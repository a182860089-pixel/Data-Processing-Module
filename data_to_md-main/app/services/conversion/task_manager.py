"""
任务管理器
管理转换任务的生命周期
"""
import uuid
import logging
from typing import Dict, Optional
from datetime import datetime
from app.models.task import Task
from app.models.enums import TaskStatus
from app.exceptions.service_exceptions import TaskNotFoundException

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        """初始化管理器"""
        # 简单的内存存储（生产环境应使用数据库或Redis）
        self._tasks: Dict[str, Task] = {}
    
    def create_task(
        self,
        filename: str,
        file_path: str,
        file_type: str
    ) -> Task:
        """
        创建新任务
        
        Args:
            filename: 文件名
            file_path: 文件路径
            file_type: 文件类型
            
        Returns:
            Task: 任务对象
        """
        task_id = self._generate_task_id()
        
        task = Task(
            task_id=task_id,
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            status=TaskStatus.PENDING,
            progress=0,
            current_page=0,
            total_pages=0
        )
        
        self._tasks[task_id] = task
        logger.info(f"Task created: {task_id}")
        
        return task
    
    def get_task(self, task_id: str) -> Task:
        """
        获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Task: 任务对象
            
        Raises:
            TaskNotFoundException: 任务不存在
        """
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundException(
                message=f"任务不存在: {task_id}"
            )
        return task
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str = None
    ):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            message: 状态消息
        """
        task = self.get_task(task_id)
        task.status = status
        task.updated_at = datetime.now()
        
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        
        logger.info(f"Task {task_id} status updated: {status}")
    
    def update_task_progress(
        self,
        task_id: str,
        current_page: int,
        total_pages: int
    ):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            current_page: 当前页
            total_pages: 总页数
        """
        task = self.get_task(task_id)
        task.update_progress(current_page, total_pages)
        
        logger.debug(f"Task {task_id} progress: {current_page}/{total_pages}")
    
    def complete_task(
        self,
        task_id: str,
        result_path: str,
        markdown_content: str,
        metadata: dict
    ):
        """
        标记任务为完成
        
        Args:
            task_id: 任务ID
            result_path: 结果文件路径
            markdown_content: Markdown内容
            metadata: 元数据
        """
        task = self.get_task(task_id)
        task.mark_completed(result_path, markdown_content, metadata)
        
        logger.info(f"Task {task_id} completed")
    
    def fail_task(
        self,
        task_id: str,
        error_message: str
    ):
        """
        标记任务为失败
        
        Args:
            task_id: 任务ID
            error_message: 错误信息
        """
        task = self.get_task(task_id)
        task.mark_failed(error_message)
        
        logger.error(f"Task {task_id} failed: {error_message}")
    
    def delete_task(self, task_id: str):
        """
        删除任务
        
        Args:
            task_id: 任务ID
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Task {task_id} deleted")
    
    def list_tasks(self) -> list[Task]:
        """
        列出所有任务
        
        Returns:
            list[Task]: 任务列表
        """
        return list(self._tasks.values())
    
    def _generate_task_id(self) -> str:
        """
        生成任务ID
        
        Returns:
            str: 任务ID
        """
        return f"task_{uuid.uuid4().hex[:12]}"

