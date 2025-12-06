"""
文件信息模型
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.enums import PDFType


class PageInfo(BaseModel):
    """页面信息"""
    page_number: int = Field(..., description="页码")
    has_text: bool = Field(..., description="是否有文本层")
    text_length: int = Field(..., description="文本字符数")
    has_images: bool = Field(..., description="是否有图像")
    image_count: int = Field(..., description="图像数量")


class PDFInfo(BaseModel):
    """PDF文件信息"""
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(..., description="文件大小（字节）")
    total_pages: int = Field(..., description="总页数")
    pdf_type: PDFType = Field(..., description="PDF类型")
    pages: List[PageInfo] = Field(default_factory=list, description="页面信息列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="其他元数据")
    
    def get_ocr_pages(self) -> List[int]:
        """获取需要OCR的页面列表"""
        if self.pdf_type == PDFType.IMAGE:
            return list(range(1, self.total_pages + 1))
        elif self.pdf_type == PDFType.MIXED:
            return [p.page_number for p in self.pages if p.has_images]
        else:
            return []
    
    def get_text_pages(self) -> List[int]:
        """获取可以直接提取文本的页面列表"""
        if self.pdf_type == PDFType.TEXT:
            return list(range(1, self.total_pages + 1))
        elif self.pdf_type == PDFType.MIXED:
            return [p.page_number for p in self.pages if not p.has_images and p.has_text]
        else:
            return []

