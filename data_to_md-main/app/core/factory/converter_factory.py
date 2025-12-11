"""
转换器工厂
根据文件类型创建对应的转换器实例
"""
import logging
from typing import Dict, Type
from app.core.base.converter import BaseConverter
from app.core.converters.pdf.pdf_converter import PDFConverter
from app.core.converters.office.office_converter import OfficeConverter
from app.core.converters.image.image_to_pdf_converter import ImageToPDFConverter
from app.core.converters.video.video_converter import VideoConverter
from app.models.enums import FileType
from app.exceptions.converter_exceptions import UnsupportedFileTypeException

logger = logging.getLogger(__name__)


class ConverterFactory:
    """转换器工厂"""
    
    # 转换器注册表
    _converters: Dict[FileType, Type[BaseConverter]] = {
        # PDF
        FileType.PDF: PDFConverter,
        # Office 文档
        FileType.DOCX: OfficeConverter,
        FileType.DOC: OfficeConverter,
        FileType.PPTX: OfficeConverter,
        FileType.PPT: OfficeConverter,
        FileType.XLSX: OfficeConverter,
        FileType.XLS: OfficeConverter,
        # 图片
        FileType.JPG: ImageToPDFConverter,
        FileType.JPEG: ImageToPDFConverter,
        FileType.PNG: ImageToPDFConverter,
        FileType.GIF: ImageToPDFConverter,
        FileType.TIFF: ImageToPDFConverter,
        FileType.BMP: ImageToPDFConverter,
        FileType.WEBP: ImageToPDFConverter,
        FileType.HEIC: ImageToPDFConverter,
        # 视频
        FileType.MP4: VideoConverter,
        FileType.AVI: VideoConverter,
        FileType.MOV: VideoConverter,
        FileType.WMV: VideoConverter,
    }
    
    @classmethod
    def create_converter(cls, file_type: FileType) -> BaseConverter:
        """
        创建转换器实例
        
        Args:
            file_type: 文件类型
            
        Returns:
            BaseConverter: 转换器实例
            
        Raises:
            UnsupportedFileTypeException: 不支持的文件类型
        """
        converter_class = cls._converters.get(file_type)
        
        if not converter_class:
            supported_types = ', '.join([ft.value for ft in cls._converters.keys()])
            raise UnsupportedFileTypeException(
                message=f"不支持的文件类型: {file_type.value}",
                details=f"当前支持的文件类型: {supported_types}"
            )
        
        logger.info(f"Creating converter for file type: {file_type.value}")
        return converter_class()
    
    @classmethod
    def register_converter(
        cls,
        file_type: FileType,
        converter_class: Type[BaseConverter]
    ):
        """
        注册新的转换器
        用于扩展支持新的文件类型
        
        Args:
            file_type: 文件类型
            converter_class: 转换器类
        """
        cls._converters[file_type] = converter_class
        logger.info(f"Registered converter for file type: {file_type.value}")
    
    @classmethod
    def get_supported_types(cls) -> list[FileType]:
        """
        获取所有支持的文件类型
        
        Returns:
            list[FileType]: 支持的文件类型列表
        """
        return list(cls._converters.keys())
    
    @classmethod
    def is_supported(cls, file_type: FileType) -> bool:
        """
        检查是否支持指定文件类型
        
        Args:
            file_type: 文件类型
            
        Returns:
            bool: 是否支持
        """
        return file_type in cls._converters

