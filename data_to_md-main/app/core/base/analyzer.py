"""
抽象分析器基类
用于分析文件内容和结构
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class FileInfo:
    """文件信息"""
    file_type: str
    file_size: int
    total_pages: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseAnalyzer(ABC):
    """
    抽象分析器基类
    用于分析文件内容和结构
    """
    
    @abstractmethod
    def analyze(self, file_path: str) -> FileInfo:
        """
        分析文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            FileInfo: 文件元信息（类型、页数、内容结构等）
        """
        pass

