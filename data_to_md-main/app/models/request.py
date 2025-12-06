"""
请求模型定义
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator


class ConvertOptions(BaseModel):
    """转换选项
    
    输出模式说明：
    - 模式A（带页码+元数据）: show_page_number=True, include_metadata=True
    - 模式B（纯内容阅读模式）: show_page_number=False, include_metadata=False
    - 兼容模式: no_pagination_and_metadata=True 等同于模式B
    """
    dpi: int = Field(default=144, ge=72, le=300, description="图像渲染DPI（仅PDF有效）")
    show_page_number: bool = Field(default=True, description="是否在Markdown中显示页码标记")
    include_metadata: bool = Field(default=True, description="是否在Markdown开头包含文档元数据")
    no_pagination_and_metadata: bool = Field(
        default=False, 
        description="【兼容参数】是否取消分页和元数据(去掉页面标记、分隔符和元数据)。设为True等同于show_page_number=False且include_metadata=False"
    )
    async_mode: bool = Field(default=True, alias="async", description="是否异步处理")
    max_pages: int = Field(default=100, ge=1, le=1000, description="最大处理页数（仅PDF有效）")
    ocr_engine: Literal["deepseek", "mineru", "auto"] = Field(
        default="auto",
        description="OCR 引擎选择：deepseek / mineru / auto（默认 auto：优先 DeepSeek，失败回退 MinerU）"
    )

    class Config:
        populate_by_name = True


class ConvertRequest(BaseModel):
    """转换请求"""
    options: Optional[ConvertOptions] = Field(default_factory=ConvertOptions)
    
    class Config:
        json_schema_extra = {
            "example": {
                "options": {
                    "dpi": 144,
                    "include_metadata": True,
                    "no_pagination_and_metadata": False,
                    "async": True,
                    "max_pages": 100,
                    "ocr_engine": "auto"
                }
            }
        }


class ImageCompressOptions(BaseModel):
    """
    图片压缩选项
    
    控制WebP压缩的质量、尺寸等参数
    """
    quality: int = Field(
        default=90, 
        ge=0, 
        le=100, 
        description="WebP压缩质量（0-100，越高质量越好但文件更大）"
    )
    max_width: int = Field(
        default=1920, 
        ge=100, 
        le=10000, 
        description="最大宽度（像素）"
    )
    max_height: int = Field(
        default=1080, 
        ge=100, 
        le=10000, 
        description="最大高度（像素）"
    )
    target_size_kb: Optional[int] = Field(
        default=None, 
        ge=10, 
        le=10000, 
        description="目标文件大小（KB，可选）"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "quality": 90,
                "max_width": 1920,
                "max_height": 1080,
                "target_size_kb": 250
            }
        }

