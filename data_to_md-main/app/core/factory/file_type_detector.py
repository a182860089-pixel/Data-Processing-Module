"""
文件类型检测器
检测文件类型
"""
import logging
from pathlib import Path
from typing import Optional
from app.models.enums import FileType

logger = logging.getLogger(__name__)


class FileTypeDetector:
    """文件类型检测器"""
    
    # 文件头签名映射
    MAGIC_NUMBERS = {
        # 文档格式
        b'%PDF': FileType.PDF,
        b'PK\x03\x04': None,  # ZIP格式（Office 文档 / 其他），需进一步判断
        # 图片格式
        b'\xff\xd8\xff': FileType.JPG,  # JPEG
        b'\x89PNG': FileType.PNG,        # PNG
        b'GIF8': FileType.GIF,           # GIF
        b'II\x2a\x00': FileType.TIFF,   # TIFF (little-endian)
        b'MM\x00\x2a': FileType.TIFF,   # TIFF (big-endian)
        b'BM': FileType.BMP,             # BMP
        b'RIFF': None,                  # RIFF格式（WebP 等）
        # 视频格式
        b'\x00\x00\x00\x18ftypmp42': FileType.MP4,  # MP4
        b'\x00\x00\x00\x20ftypisom': FileType.MP4,  # MP4 (ISO)
    }
    
    # 扩展名映射
    EXTENSION_MAP = {
        # PDF
        '.pdf': FileType.PDF,
        # Office 文档
        '.docx': FileType.DOCX,
        '.doc': FileType.DOC,
        '.pptx': FileType.PPTX,
        '.ppt': FileType.PPT,
        '.xlsx': FileType.XLSX,
        '.xls': FileType.XLS,
        # 图片
        '.jpg': FileType.JPG,
        '.jpeg': FileType.JPEG,
        '.png': FileType.PNG,
        '.gif': FileType.GIF,
        '.tiff': FileType.TIFF,
        '.tif': FileType.TIFF,
        '.bmp': FileType.BMP,
        '.webp': FileType.WEBP,
        '.heic': FileType.HEIC,
        # 视频
        '.mp4': FileType.MP4,
        '.avi': FileType.AVI,
        '.mov': FileType.MOV,
        '.wmv': FileType.WMV,
    }
    
    def detect(self, file_path: str) -> FileType:
        """
        检测文件类型
        
        检测策略（优先级从高到低）：
        1. 文件头检测（Magic Number）- 最准确
        2. 文件扩展名检测 - 最不可靠
        
        Args:
            file_path: 文件路径
            
        Returns:
            FileType: 文件类型
        """
        # 1. 读取文件头
        magic_number = self._read_magic_number(file_path)
        file_type = self._detect_by_magic(magic_number, file_path)
        if file_type:
            logger.info(f"File type detected by magic number: {file_type}")
            return file_type
        
        # 2. 扩展名检测
        extension = Path(file_path).suffix.lower()
        file_type = self._detect_by_extension(extension)
        if file_type:
            logger.info(f"File type detected by extension: {file_type}")
            return file_type
        
        logger.warning(f"Unknown file type: {file_path}")
        return FileType.UNKNOWN
    
    def _read_magic_number(self, file_path: str, size: int = 8) -> bytes:
        """
        读取文件头
        
        Args:
            file_path: 文件路径
            size: 读取字节数
            
        Returns:
            bytes: 文件头字节
        """
        try:
            with open(file_path, 'rb') as f:
                return f.read(size)
        except Exception as e:
            logger.error(f"Failed to read magic number: {str(e)}")
            return b''
    
    def _detect_by_magic(
        self,
        magic: bytes,
        file_path: str
    ) -> Optional[FileType]:
        """
        根据文件头判断类型
        
        Args:
            magic: 文件头字节
            file_path: 文件路径
            
        Returns:
            Optional[FileType]: 文件类型
        """
        for signature, file_type in self.MAGIC_NUMBERS.items():
            if magic.startswith(signature):
                # 如果是ZIP格式，需进一步判断 (Office 文档)
                if file_type is None and signature == b'PK\x03\x04':
                    return self._detect_office_type(file_path)
                # 如果是RIFF格式，需进一步判断 (WebP 等)
                elif file_type is None and signature == b'RIFF':
                    return self._detect_riff_type(file_path)
                return file_type
        
        return None
    
    def _detect_office_type(self, file_path: str) -> Optional[FileType]:
        """
        检测Office文档类型（PPTX/DOCX/XLSX等）
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[FileType]: 文件类型
        """
        # 根据扩展名判断
        extension = Path(file_path).suffix.lower()
        office_extensions = ['.pptx', '.docx', '.xlsx', '.ppt', '.doc', '.xls']
        if extension in office_extensions:
            return self.EXTENSION_MAP.get(extension)
        
        return None
    
    def _detect_riff_type(self, file_path: str) -> Optional[FileType]:
        """
        检测RIFF格式的子类型（例如 WebP）
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[FileType]: 文件类型
        """
        try:
            with open(file_path, 'rb') as f:
                # RIFF 文件结构: "RIFF" + 大小 + 类型
                f.read(4)  # 跳过 "RIFF"
                f.read(4)  # 跳过文件大小
                format_type = f.read(4)
                if format_type == b'WEBP':
                    return FileType.WEBP
        except Exception:
            pass
        
        return None
    
    def _detect_by_extension(self, extension: str) -> Optional[FileType]:
        """
        根据扩展名判断类型
        
        Args:
            extension: 文件扩展名
            
        Returns:
            Optional[FileType]: 文件类型
        """
        return self.EXTENSION_MAP.get(extension.lower())

