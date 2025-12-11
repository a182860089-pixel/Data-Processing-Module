"""
抽象转换器基类
所有文件类型转换器必须继承此类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ConversionResult:
    """转换结果"""
    markdown: str = None  # PDF → Markdown 时使用
    pdf_content: bytes = None  # Office/图片 → PDF 时使用
    metadata: Dict[str, Any] = None
    status: str = "pending"
    error: str = None
    output_type: str = "markdown"  # 'markdown' 或 'pdf'


class BaseConverter(ABC):
    """
    抽象转换器基类
    所有文件类型转换器必须继承此类并实现convert方法
    """
    
    @abstractmethod
    async def convert(self, file_path: str, options: Dict[str, Any]) -> ConversionResult:
        """
        转换文件为Markdown
        
        Args:
            file_path: 文件路径
            options: 转换选项（DPI、质量等）
            
        Returns:
            ConversionResult: 包含markdown内容、元数据、状态
        """
        pass
    
    @abstractmethod
    def validate(self, file_path: str) -> bool:
        """
        验证文件是否可以被此转换器处理
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否可以处理
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        返回支持的文件扩展名列表
        
        Returns:
            List[str]: 支持的扩展名列表（如 ['.pdf', '.PDF']）
        """
        pass

