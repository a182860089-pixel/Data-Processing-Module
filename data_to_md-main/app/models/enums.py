"""
枚举类型定义
"""
from enum import Enum


class FileType(str, Enum):
    """文件类型"""
    PDF = "pdf"
    PPTX = "pptx"
    PPT = "ppt"
    DOCX = "docx"
    DOC = "doc"
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    UNKNOWN = "unknown"


class PDFType(str, Enum):
    """PDF类型"""
    IMAGE = "image"  # 纯图片PDF
    MIXED = "mixed"  # 图文混排PDF
    TEXT = "text"    # 纯文本PDF


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChunkType(str, Enum):
    """内容片段类型"""
    OCR = "ocr"
    TEXT = "text"
    MIXED = "mixed"

