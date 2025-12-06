"""
PDF分析器
分析PDF文档类型和结构
"""
import logging
import os
import fitz  # PyMuPDF
from app.core.base.analyzer import BaseAnalyzer
from app.models.file_info import PDFInfo, PageInfo
from app.models.enums import PDFType
from app.config import get_settings

logger = logging.getLogger(__name__)


class PDFAnalyzer(BaseAnalyzer):
    """PDF分析器"""
    
    def __init__(self):
        """初始化分析器"""
        self.settings = get_settings()
        self.text_threshold = self.settings.pdf_text_threshold
    
    def analyze(self, file_path: str) -> PDFInfo:
        """
        分析PDF文档
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            PDFInfo: PDF文件信息
        """
        try:
            # 打开PDF文档
            doc = fitz.open(file_path)
            
            # 获取基本信息
            total_pages = len(doc)
            file_size = os.path.getsize(file_path)
            
            # 分析每一页
            pages_info = []
            for page_num in range(total_pages):
                page = doc[page_num]
                page_info = self.get_page_info(page, page_num + 1)
                pages_info.append(page_info)
            
            # 检测PDF类型
            pdf_type = self.detect_pdf_type(pages_info)
            
            # 获取元数据
            metadata = self._extract_metadata(doc)
            
            # 关闭文档
            doc.close()
            
            # 构建PDFInfo
            pdf_info = PDFInfo(
                file_path=file_path,
                file_size=file_size,
                total_pages=total_pages,
                pdf_type=pdf_type,
                pages=pages_info,
                metadata=metadata
            )
            
            logger.info(
                f"PDF analyzed: {total_pages} pages, type={pdf_type}, "
                f"size={file_size} bytes"
            )
            
            return pdf_info
            
        except Exception as e:
            logger.error(f"Failed to analyze PDF: {str(e)}")
            raise
    
    def get_page_info(self, page: fitz.Page, page_number: int) -> PageInfo:
        """
        获取单页信息

        Args:
            page: PyMuPDF页面对象
            page_number: 页码（从1开始）

        Returns:
            PageInfo: 页面信息
        """
        # 提取文本层内容
        text = page.get_text()
        text_length = len(text.strip())
        has_text = text_length >= self.text_threshold

        # 获取页面图像列表
        image_list = page.get_images()
        image_count = len(image_list)

        # ================================
        # 表格处理策略说明
        # ================================
        # 目标：准确识别并保留PDF中的表格结构
        # 
        # 当前策略：
        # 1. 纯图片页面：全部使用OCR识别（包括表格）
        # 2. 带图表的文本页：也走OCR流程（保留视觉结构）
        # 3. 纯文本页：直接提取文本层
        # 
        # 好用场景：
        # - 简单表格（行列整齐）：OCR能识别为Markdown表格
        # - 文本+表格混排：保留完整的视觉布局
        # 
        # 已知问题：
        # - 复杂表格（合并单元格、嵌套表格）：OCR可能识别不准
        # - 表格边框不清晰：可能被识别为普通文本
        # - 表格内的数字格式：可能丢失对齐
        # 
        # 后续优化方向（阶段4+）：
        # - 引入MinerU引擎，专门优化表格识别
        # - 表格区域单独处理，与文本区域分离
        # ================================
        
        # 检测表格
        has_tables = False
        try:
            tables = page.find_tables()
            has_tables = len(tables.tables) > 0
            if has_tables:
                logger.debug(f"Page {page_number}: Found {len(tables.tables)} table(s)")
        except Exception as e:
            logger.warning(f"Failed to detect tables on page {page_number}: {str(e)}")

        # 综合判断是否有"图表"（图像 或 表格）
        # 如果有图像或表格，就需要用OCR处理整页以保留视觉结构
        has_images = (image_count > 0) or has_tables

        return PageInfo(
            page_number=page_number,
            has_text=has_text,
            text_length=text_length,
            has_images=has_images,
            image_count=image_count
        )
    
    def detect_pdf_type(self, pages_info: list[PageInfo]) -> PDFType:
        """
        检测PDF类型
        
        Args:
            pages_info: 页面信息列表
            
        Returns:
            PDFType: PDF类型
        """
        if not pages_info:
            return PDFType.UNKNOWN
        
        # 统计有文本和有图像的页面数
        text_pages = sum(1 for p in pages_info if p.has_text)
        image_pages = sum(1 for p in pages_info if p.has_images)
        total_pages = len(pages_info)
        
        # 判断逻辑
        if text_pages == 0:
            # 所有页面都没有文本层 → 纯图片PDF
            return PDFType.IMAGE
        elif image_pages == 0:
            # 所有页面都没有图像 → 纯文本PDF
            return PDFType.TEXT
        else:
            # 既有文本又有图像 → 图文混排PDF
            return PDFType.MIXED
    
    def _extract_metadata(self, doc: fitz.Document) -> dict:
        """
        提取PDF元数据
        
        Args:
            doc: PyMuPDF文档对象
            
        Returns:
            dict: 元数据字典
        """
        metadata = {}
        
        try:
            # 获取PDF元数据
            pdf_metadata = doc.metadata
            if pdf_metadata:
                metadata['title'] = pdf_metadata.get('title', '')
                metadata['author'] = pdf_metadata.get('author', '')
                metadata['subject'] = pdf_metadata.get('subject', '')
                metadata['creator'] = pdf_metadata.get('creator', '')
                metadata['producer'] = pdf_metadata.get('producer', '')
                metadata['creation_date'] = pdf_metadata.get('creationDate', '')
                metadata['mod_date'] = pdf_metadata.get('modDate', '')
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {str(e)}")
        
        return metadata

