"""
PDF转换器
实现PDF到Markdown的转换
"""
import logging
from typing import Dict, Any, List
from app.core.base.converter import BaseConverter, ConversionResult
from app.core.base.processor import BaseProcessor
from app.core.converters.pdf.pdf_analyzer import PDFAnalyzer
from app.core.converters.pdf.image_pdf_processor import ImagePDFProcessor
from app.core.converters.pdf.mixed_pdf_processor import MixedPDFProcessor
from app.core.common.markdown_generator import MarkdownGenerator
from app.models.enums import PDFType
from app.exceptions.converter_exceptions import ConversionFailedException

logger = logging.getLogger(__name__)


class PDFConverter(BaseConverter):
    """PDF转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.analyzer = PDFAnalyzer()
    
    async def convert(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """
        转换PDF为Markdown
        
        Args:
            file_path: PDF文件路径
            options: 转换选项
            
        Returns:
            ConversionResult: 转换结果
        """
        logger.info(f"Starting PDF conversion: {file_path}")
        
        try:
            # 1. 分析PDF
            pdf_info = self.analyzer.analyze(file_path)
            logger.info(f"PDF analyzed: type={pdf_info.pdf_type}, pages={pdf_info.total_pages}")
            
            # 2. 选择处理器（带 OCR 引擎配置）
            ocr_engine = options.get('ocr_engine', 'auto') if options else 'auto'
            processor = self._select_processor(pdf_info.pdf_type, ocr_engine=ocr_engine)
            logger.info(f"Selected processor: {processor.__class__.__name__} (ocr_engine={ocr_engine})")
            
            # 3. 处理内容
            content_chunks = await processor.process(file_path, pdf_info)
            logger.info(f"Content processed: {len(content_chunks)} chunks")
            
            # 4. 生成Markdown
            show_page_number = options.get('show_page_number', True)
            include_metadata = options.get('include_metadata', True)
            no_pagination_and_metadata = options.get('no_pagination_and_metadata', False)
            
            markdown_generator = MarkdownGenerator(
                show_page_number=show_page_number,
                include_metadata=include_metadata,
                no_pagination_and_metadata=no_pagination_and_metadata
            )
            markdown = markdown_generator.generate(content_chunks, pdf_info)
            logger.info(
                f"Markdown generated: {len(markdown)} characters "
                f"(mode: page_num={show_page_number}, metadata={include_metadata})"
            )
            
            # 5. 构建结果
            result = ConversionResult(
                markdown=markdown,
                metadata={
                    'total_pages': pdf_info.total_pages,
                    'pdf_type': pdf_info.pdf_type,
                    'file_size': pdf_info.file_size,
                    'ocr_pages': len([c for c in content_chunks if c.chunk_type == 'ocr']),
                    'text_pages': len([c for c in content_chunks if c.chunk_type == 'text']),
                },
                status='success'
            )
            
            logger.info("PDF conversion completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise ConversionFailedException(
                message="PDF转换失败",
                details=str(e)
            )
    
    def _select_processor(self, pdf_type: PDFType, ocr_engine: str = "auto") -> BaseProcessor:
        """
        根据PDF类型选择处理器
        
        Args:
            pdf_type: PDF类型
            
        Returns:
            BaseProcessor: 处理器实例
        """
        if pdf_type == PDFType.IMAGE:
            return ImagePDFProcessor(ocr_engine=ocr_engine)
        elif pdf_type == PDFType.MIXED:
            return MixedPDFProcessor(ocr_engine=ocr_engine)
        elif pdf_type == PDFType.TEXT:
            # 纯文本PDF也使用混排处理器（会自动提取文本）
            return MixedPDFProcessor(ocr_engine=ocr_engine)
        else:
            raise ConversionFailedException(
                message=f"不支持的PDF类型: {pdf_type}"
            )
    
    def validate(self, file_path: str) -> bool:
        """
        验证是否为有效的PDF文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否有效
        """
        try:
            import fitz
            doc = fitz.open(file_path)
            doc.close()
            return True
        except Exception as e:
            logger.error(f"PDF validation failed: {str(e)}")
            return False
    
    def get_supported_extensions(self) -> List[str]:
        """
        返回支持的文件扩展名列表
        
        Returns:
            List[str]: 支持的扩展名
        """
        return ['.pdf', '.PDF']

