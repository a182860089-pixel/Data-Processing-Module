"""批量任务模型定义"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.enums import BatchStatus


class BatchTask(BaseModel):
    """批量任务模型

    用于跟踪一次批量转换请求及其包含的子任务。
    """

    batch_id: str = Field(..., description="批次 ID")
    batch_name: Optional[str] = Field(None, description="批次名称")
    status: BatchStatus = Field(default=BatchStatus.COMPLETED, description="批次状态")
    task_ids: List[str] = Field(default_factory=list, description="子任务 ID 列表")
    total_files: int = Field(default=0, description="文件总数")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="批次元数据")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="子任务摘要列表")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
