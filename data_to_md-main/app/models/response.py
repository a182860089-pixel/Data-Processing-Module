"""
响应模型定义

统一的响应格式说明：
- success: 请求是否成功（bool）
- data: 响应数据（dict，可选）
- message: 提示信息（string）
- error: 错误信息（dict，可选）
"""
from typing import Optional, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field
from app.models.enums import TaskStatus

# 泛型类型变量
T = TypeVar('T')


class ErrorResponse(BaseModel):
    """错误响应"""
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误信息")
    details: Optional[str] = Field(None, description="详细信息")


class DetectedInfo(BaseModel):
    """文件检测信息"""
    total_pages: Optional[int] = Field(None, description="总页数")
    pdf_type: Optional[str] = Field(None, description="PDF类型")
    file_size: int = Field(..., description="文件大小（字节）")


class ConversionMetadata(BaseModel):
    """转换元数据"""
    pages_processed: int = Field(default=0, description="处理的页数")
    ocr_pages: Optional[int] = Field(None, description="OCR处理的页数")
    text_pages: Optional[int] = Field(None, description="文本提取的页数")
    processing_time: float = Field(default=0, description="处理时间（秒）")
    file_size: int = Field(default=0, description="输出文件大小（字节）")
    output_type: Optional[str] = Field(default="markdown", description="输出类型: markdown/pdf")


class TaskProgress(BaseModel):
    """任务进度"""
    current_page: int = Field(..., description="当前页")
    total_pages: int = Field(..., description="总页数")
    percentage: int = Field(..., description="完成百分比")


class ConversionResult(BaseModel):
    """转换结果"""
    markdown_content: Optional[str] = Field(None, description="Markdown内容")
    download_url: str = Field(..., description="下载链接")
    metadata: ConversionMetadata = Field(..., description="转换元数据")


class ConvertResponse(BaseModel):
    """转换响应（异步模式）"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    message: str = Field(..., description="提示信息")
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小")
    detected_info: Optional[DetectedInfo] = Field(None, description="检测信息")
    estimated_time: Optional[int] = Field(None, description="预计处理时间（秒）")
    status_url: str = Field(..., description="状态查询URL")


class ConvertSyncResponse(BaseModel):
    """转换响应（同步模式）"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    message: str = Field(..., description="提示信息")
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="输出类型: markdown/pdf")
    markdown_content: Optional[str] = Field(default="", description="Markdown内容（仅markdown输出时有内容）")
    download_url: str = Field(..., description="下载链接")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="转换元数据")


class StatusResponse(BaseModel):
    """状态查询响应"""
    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: Optional[TaskProgress] = Field(None, description="任务进度")
    message: Optional[str] = Field(None, description="提示信息")
    result: Optional[ConversionResult] = Field(None, description="转换结果")
    error: Optional[ErrorResponse] = Field(None, description="错误信息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    timestamp: str = Field(..., description="时间戳")
    version: str = Field(..., description="版本号")
    services: Dict[str, str] = Field(..., description="服务状态")
    metrics: Optional[Dict[str, Any]] = Field(None, description="指标")


class BaseResponse(BaseModel, Generic[T]):
    """
    统一的基础响应模型（泛型）
    
    符合RESTful最佳实践的响应格式：
    - success: 请求是否成功
    - data: 响应数据（泛型）
    - message: 提示信息
    - error: 错误信息（仅失败时）
    """
    success: bool = Field(..., description="请求是否成功")
    data: Optional[T] = Field(None, description="响应数据")
    message: str = Field(..., description="提示信息")
    error: Optional[ErrorResponse] = Field(None, description="错误信息")


class ImageCompressMetadata(BaseModel):
    """图片压缩元数据"""
    original_size: int = Field(..., description="原始文件大小（字节）")
    output_size: int = Field(..., description="输出文件大小（字节）")
    compression_ratio: float = Field(..., description="压缩率（%）")
    original_dimensions: str = Field(..., description="原始尺寸")
    output_dimensions: str = Field(..., description="输出尺寸")
    quality: int = Field(..., description="压缩质量")


class ImageCompressResponse(BaseModel):
    """图片压缩响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
    filename: str = Field(..., description="原始文件名")
    output_filename: str = Field(..., description="输出文件名")
    download_url: str = Field(..., description="下载链接")
    metadata: ImageCompressMetadata = Field(..., description="压缩元数据")

