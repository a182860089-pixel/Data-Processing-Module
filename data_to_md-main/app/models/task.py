"""
任务模型定义
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import TaskStatus


class Task(BaseModel):
    """任务模型"""
    task_id: str = Field(..., description="任务ID")
    filename: str = Field(..., description="原始文件名")
    file_path: str = Field(..., description="文件路径")
    file_type: str = Field(..., description="文件类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    current_page: int = Field(default=0, description="当前处理页")
    total_pages: int = Field(default=0, description="总页数")
    result_path: Optional[str] = Field(None, description="结果文件路径")
    markdown_content: Optional[str] = Field(None, description="Markdown内容")
    error_message: Optional[str] = Field(None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def update_progress(self, current_page: int, total_pages: int):
        """更新进度"""
        self.current_page = current_page
        self.total_pages = total_pages
        if total_pages > 0:
            self.progress = int((current_page / total_pages) * 100)
        self.updated_at = datetime.now()
    
    def mark_completed(self, result_path: str, markdown_content: str, metadata: Dict[str, Any]):
        """标记为完成"""
        self.status = TaskStatus.COMPLETED
        self.result_path = result_path
        self.markdown_content = markdown_content
        self.metadata.update(metadata)
        self.progress = 100
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
    
    def mark_failed(self, error_message: str):
        """标记为失败"""
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.now()

