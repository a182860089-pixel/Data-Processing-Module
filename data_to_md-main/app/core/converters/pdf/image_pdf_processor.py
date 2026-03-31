"""
纯图片PDF处理器
处理纯图片PDF（所有页面OCR）

优化特性：
- 动态并发控制：根据系统资源自动调整
- 分批流式处理：减少内存压力
- 性能监控：实时收集处理指标
"""
import logging
import asyncio
import gc
import fitz  # PyMuPDF
from typing import List
from app.core.base.processor import BaseProcessor, ContentChunk
from app.models.file_info import PDFInfo
from app.models.enums import ChunkType
from app.core.common.image_processor import ImageProcessor
from app.core.converters.pdf.ocr_router import OCRRouter
from app.services.external.mineru_client import MinerUClient
from app.exceptions.service_exceptions import MinerUAPIException
from app.config import get_settings
from app.utils.concurrency import concurrency_manager
from app.utils.performance import performance_manager

logger = logging.getLogger(__name__)


class ImagePDFProcessor(BaseProcessor):
    """
    纯图片PDF处理器
    
    优化特性：
    - 动态并发控制：根据系统 CPU/内存自动调整并发数
    - 分批流式处理：每批 5 页，处理后释放内存
    - 性能监控：记录 API 延迟和处理时间
    """
    
    # 分批处理配置
    PAGES_PER_BATCH = 10  # 增加批大小以提高并发效率
    GC_AFTER_BATCH = True
    
    def __init__(self, ocr_engine: str = "auto"):
        """初始化处理器

        Args:
            ocr_engine: OCR 引擎选择："deepseek" / "mineru" / "auto"。
        """
        self.settings = get_settings()
        self.image_processor = ImageProcessor()
        self.mineru_client = MinerUClient()
        self.ocr_engine = ocr_engine
        self.dpi = self.settings.pdf_render_dpi
        
        # 动态获取最优并发数（而不是固定值）
        self.max_concurrent = concurrency_manager.get_optimal_concurrency("io_bound")
        logger.info(f"ImagePDFProcessor initialized with dynamic concurrency={self.max_concurrent}")
        
        # 初始化 OCRRouter（用于逐页 OCR）
        self.ocr_router = OCRRouter()
    
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
        
        # 当选择 MinerU 时，走整PDF解析链路，返回单个整文 ContentChunk
        if (self.ocr_engine or "").lower() == "mineru":
            logger.info("Using MinerU ocr_pdf for whole-document parsing in ImagePDFProcessor")
            try:
                markdown = await self.mineru_client.ocr_pdf(file_path)
                return [
                    ContentChunk(
                        content=markdown,
                        page_number=1,
                        chunk_type=ChunkType.OCR,
                        metadata={"ocr_engine": "mineru", "method": "mineru_pdf"}
                    )
                ]
            except Exception as e:
                logger.error(f"MinerU whole-document parsing failed: {str(e)}")
                raise
        
        try:
            # 打开PDF文档
            doc = fitz.open(file_path)
            total_pages = file_info.total_pages
            
            # 动态获取并发数（考虑性能管理器的建议）
            adjustment = performance_manager.suggest_concurrency_adjustment()
            optimal_concurrent = concurrency_manager.get_optimal_concurrency("io_bound", adjustment)
            semaphore = asyncio.Semaphore(optimal_concurrent)
            
            logger.info(
                f"Processing {total_pages} pages with concurrency={optimal_concurrent} "
                f"(batch_size={self.PAGES_PER_BATCH})"
            )
            
            # 分批流式处理（而不是一次性创建所有任务）
            content_chunks = []
            
            for batch_start in range(0, total_pages, self.PAGES_PER_BATCH):
                batch_end = min(batch_start + self.PAGES_PER_BATCH, total_pages)
                page_nums = list(range(batch_start, batch_end))
                
                logger.debug(
                    f"Processing page batch: {batch_start + 1}-{batch_end} of {total_pages}"
                )
                
                # 创建当前批次的任务
                batch_tasks = [
                    self._process_page_with_semaphore(doc, page_num, semaphore)
                    for page_num in page_nums
                ]
                
                # 并发执行当前批次
                batch_results = await asyncio.gather(*batch_tasks)
                
                # 收集结果
                for result in batch_results:
                    content_chunks.append(result)
                
                # 批处理后释放内存
                if self.GC_AFTER_BATCH:
                    del batch_tasks
                    del batch_results
                    gc.collect()
                    logger.debug("Memory released after batch")
            
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
            logger.debug(
                "Routing OCR for page %s via OCRRouter (strategy=%s)",
                page_number,
                self.ocr_router.strategy,
            )
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
            raise
 
    async def _run_ocr(self, base64_image: str) -> tuple[str, str]:
        """根据配置的引擎执行 OCR，通过 OCRRouter 进行路由。

        Returns:
            (markdown, engine_used)
        """
        engine = (self.ocr_engine or "auto").lower()

        # 明确指定 MinerU（逐页不支持）
        if engine == "mineru":
            raise MinerUAPIException(
                message="MinerU 不支持逐页 image OCR",
                details="请在处理器入口走 mineru 的整PDF解析链路（ocr_pdf）。"
            )

        # deepseek 或 auto 模式：通过 OCRRouter 进行路由
        # OCRRouter 会根据配置的策略（round_robin/failover）选择引擎
        # 注意：MinerU 不支持逐页 OCR，所以 OCRRouter 主要管理 DeepSeek
        markdown, engine_used = await self.ocr_router.ocr_image(base64_image)
        return markdown, engine_used
 
