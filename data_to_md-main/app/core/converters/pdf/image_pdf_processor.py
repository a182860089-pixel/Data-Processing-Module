"""
纯图片PDF处理器
处理纯图片PDF（所有页面OCR）
"""
import logging
import asyncio
import fitz  # PyMuPDF
from typing import List
from app.core.base.processor import BaseProcessor, ContentChunk
from app.models.file_info import PDFInfo
from app.models.enums import ChunkType
from app.core.common.image_processor import ImageProcessor
from app.services.external.deepseek_client import DeepSeekClient
from app.services.external.mineru_client import MinerUClient
from app.config import get_settings

logger = logging.getLogger(__name__)


class ImagePDFProcessor(BaseProcessor):
    """纯图片PDF处理器"""
    
    def __init__(self, ocr_engine: str = "auto"):
        """初始化处理器

        Args:
            ocr_engine: OCR 引擎选择："deepseek" / "mineru" / "auto"。
        """
        self.settings = get_settings()
        self.image_processor = ImageProcessor()
        self.deepseek_client = DeepSeekClient()
        self.mineru_client = MinerUClient()
        self.ocr_engine = ocr_engine
        self.dpi = self.settings.pdf_render_dpi
        self.max_concurrent = self.settings.max_concurrent_api_calls
    
    async def process(
        self,
        file_path: str,
        file_info: PDFInfo
    ) -> List[ContentChunk]:
        """
        处理纯图片PDF
        
        Args:
            file_path: PDF文件路径
            file_info: PDF文件信息
            
        Returns:
            List[ContentChunk]: 内容片段列表
        """
        logger.info(f"Processing image PDF: {file_path}, {file_info.total_pages} pages")
        
        try:
            # 打开PDF文档
            doc = fitz.open(file_path)
            
            # 创建信号量限制并发
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            # 创建所有页面的处理任务
            tasks = []
            for page_num in range(file_info.total_pages):
                task = self._process_page_with_semaphore(
                    doc,
                    page_num,
                    semaphore
                )
                tasks.append(task)
            
            # 并发执行所有任务
            content_chunks = await asyncio.gather(*tasks)
            
            # 关闭文档
            doc.close()
            
            logger.info(f"Image PDF processed: {len(content_chunks)} pages")
            
            return content_chunks
            
        except Exception as e:
            logger.error(f"Failed to process image PDF: {str(e)}")
            raise
    
    async def _process_page_with_semaphore(
        self,
        doc: fitz.Document,
        page_num: int,
        semaphore: asyncio.Semaphore
    ) -> ContentChunk:
        """
        使用信号量限制并发处理页面
        
        Args:
            doc: PDF文档对象
            page_num: 页码（从0开始）
            semaphore: 信号量
            
        Returns:
            ContentChunk: 内容片段
        """
        async with semaphore:
            return await self._process_page(doc, page_num)
    
    async def _process_page(
        self,
        doc: fitz.Document,
        page_num: int
    ) -> ContentChunk:
        """
        处理单个页面
        
        Args:
            doc: PDF文档对象
            page_num: 页码（从0开始）
            
        Returns:
            ContentChunk: 内容片段
        """
        page_number = page_num + 1
        logger.info(f"Processing page {page_number} with OCR")
        
        try:
            # 获取页面
            page = doc[page_num]
            
            # 渲染页面为Base64
            base64_image = self.image_processor.render_page_to_base64(
                page,
                dpi=self.dpi,
                optimize=True
            )

            # 调用 OCR 引擎
            markdown_content, engine_used = await self._run_ocr(base64_image)
            
            # 创建内容片段
            chunk = ContentChunk(
                content=markdown_content,
                page_number=page_number,
                chunk_type=ChunkType.OCR,
                metadata={
                    'dpi': self.dpi,
                    'method': f'{engine_used}_ocr',
                    'ocr_engine': engine_used
                }
            )
            
            logger.info(f"Page {page_number} processed successfully")
            
            return chunk
            
        except Exception as e:
            logger.error(f"Failed to process page {page_number}: {str(e)}")
            # 返回错误信息作为内容
            return ContentChunk(
                content=f"[Error processing page {page_number}: {str(e)}]",
                page_number=page_number,
                chunk_type=ChunkType.OCR,
                metadata={'error': str(e), 'ocr_engine': self.ocr_engine}
            )
 
    async def _run_ocr(self, base64_image: str) -> tuple[str, str]:
        """根据配置的引擎执行 OCR。

        Returns:
            (markdown, engine_used)
        """
        engine = (self.ocr_engine or "auto").lower()

        # 明确指定 DeepSeek
        if engine == "deepseek":
            markdown = await self.deepseek_client.ocr_image(base64_image)
            return markdown, "deepseek"

        # 明确指定 MinerU
        if engine == "mineru":
            markdown = await self.mineru_client.ocr_image(base64_image)
            return markdown, "mineru"

        # auto 模式：先 DeepSeek，失败则回退 MinerU
        try:
            markdown = await self.deepseek_client.ocr_image(base64_image)
            return markdown, "deepseek"
        except Exception as e:
            logger.warning(f"DeepSeek OCR failed, fallback to MinerU: {str(e)}")
            markdown = await self.mineru_client.ocr_image(base64_image)
            return markdown, "mineru"
 
