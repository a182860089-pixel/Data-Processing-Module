"""
枚举类型定义
"""
from enum import Enum


class FileType(str, Enum):
    """文件类型"""
    # PDF
    PDF = "pdf"
    # Office 文档
    DOCX = "docx"
    DOC = "doc"
    PPTX = "pptx"
    PPT = "ppt"
    XLSX = "xlsx"
    XLS = "xls"
    # 图片
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    TIFF = "tiff"
    BMP = "bmp"
    WEBP = "webp"
    HEIC = "heic"
    # 视频
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WMV = "wmv"
    # 未知
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


class BatchStatus(str, Enum):
    """批次状态"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class ChunkType(str, Enum):
    """内容片段类型"""
    OCR = "ocr"
    TEXT = "text"
    MIXED = "mixed"

