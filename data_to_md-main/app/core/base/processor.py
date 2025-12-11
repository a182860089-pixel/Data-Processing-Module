"""
抽象处理器基类
用于处理文件内容
"""
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
from app.core.base.analyzer import FileInfo


@dataclass
class ContentChunk:
    """内容片段"""
    content: str
    page_number: int
    chunk_type: str  # 'ocr', 'text', 'mixed'
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseProcessor(ABC):
    """
    抽象处理器基类
    用于处理文件内容
    """
    
    @abstractmethod
    async def process(self, file_path: str, file_info: FileInfo) -> List[ContentChunk]:
        """
        处理文件内容
        
        Args:
            file_path: 文件路径
            file_info: 文件信息
            
        Returns:
            List[ContentChunk]: 内容片段列表
        """
        pass

