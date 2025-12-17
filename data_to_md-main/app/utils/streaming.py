"""
流式处理器
支持分批处理 PDF 页面，优化内存使用
借鉴 VERT 项目的大文件流式处理机制
"""
import asyncio
import logging
import gc
from typing import List, Callable, Any, TypeVar, Generic, AsyncGenerator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class BatchResult(Generic[T]):
    """批处理结果"""
    batch_index: int
    start_index: int
    end_index: int
    results: List[T]
    errors: List[tuple]  # [(index, error), ...]


class StreamingProcessor:
    """
    流式处理器
    
    特点：
    - 分批处理，控制内存使用
    - 支持进度回调
    - 自动垃圾回收
    - 错误隔离（单个失败不影响整体）
    """
    
    def __init__(
        self,
        batch_size: int = 5,
        max_concurrent: int = 10,
        gc_after_batch: bool = True
    ):
        """
        初始化流式处理器
        
        Args:
            batch_size: 每批处理的项目数
            max_concurrent: 最大并发数
            gc_after_batch: 每批处理后是否触发垃圾回收
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.gc_after_batch = gc_after_batch
    
    async def process_items(
        self,
        items: List[Any],
        processor: Callable[[Any], Any],
        semaphore: Optional[asyncio.Semaphore] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        分批处理项目列表
        
        Args:
            items: 要处理的项目列表
            processor: 处理函数（可以是 async 函数）
            semaphore: 并发信号量
            progress_callback: 进度回调函数 (completed, total)
            
        Returns:
            List[Any]: 处理结果列表
        """
        total = len(items)
        results = [None] * total
        completed = 0
        
        if semaphore is None:
            semaphore = asyncio.Semaphore(self.max_concurrent)
        
        for batch_start in range(0, total, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total)
            batch_items = items[batch_start:batch_end]
            batch_indices = list(range(batch_start, batch_end))
            
            logger.debug(
                f"Processing batch {batch_start // self.batch_size + 1}: "
                f"items {batch_start}-{batch_end - 1}"
            )
            
            # 创建批处理任务
            tasks = []
            for idx, item in zip(batch_indices, batch_items):
                task = self._process_with_semaphore(
                    processor, item, idx, semaphore
                )
                tasks.append(task)
            
            # 并发执行批处理
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for idx, result in zip(batch_indices, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing item {idx}: {result}")
                    results[idx] = None
                else:
                    results[idx] = result
                completed += 1
                
                # 进度回调
                if progress_callback:
                    progress_callback(completed, total)
            
            # 批处理后清理内存
            if self.gc_after_batch:
                del batch_items
                del tasks
                del batch_results
                gc.collect()
                logger.debug(f"Garbage collected after batch")
        
        return results
    
    async def _process_with_semaphore(
        self,
        processor: Callable,
        item: Any,
        index: int,
        semaphore: asyncio.Semaphore
    ) -> Any:
        """使用信号量限制并发处理"""
        async with semaphore:
            try:
                if asyncio.iscoroutinefunction(processor):
                    return await processor(item)
                else:
                    return processor(item)
            except Exception as e:
                logger.error(f"Error processing item {index}: {e}")
                raise
    
    async def stream_process(
        self,
        items: List[Any],
        processor: Callable[[Any], Any],
        semaphore: Optional[asyncio.Semaphore] = None
    ) -> AsyncGenerator[tuple, None]:
        """
        流式处理项目，逐个 yield 结果
        
        Args:
            items: 要处理的项目列表
            processor: 处理函数
            semaphore: 并发信号量
            
        Yields:
            tuple: (index, result, error)
        """
        total = len(items)
        
        if semaphore is None:
            semaphore = asyncio.Semaphore(self.max_concurrent)
        
        for batch_start in range(0, total, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total)
            batch_items = items[batch_start:batch_end]
            batch_indices = list(range(batch_start, batch_end))
            
            tasks = []
            for idx, item in zip(batch_indices, batch_items):
                task = self._process_with_semaphore(
                    processor, item, idx, semaphore
                )
                tasks.append((idx, task))
            
            # 使用 as_completed 实现流式返回
            for idx, task in tasks:
                try:
                    result = await task
                    yield (idx, result, None)
                except Exception as e:
                    yield (idx, None, e)
            
            if self.gc_after_batch:
                gc.collect()


class PDFStreamingProcessor(StreamingProcessor):
    """
    PDF 专用流式处理器
    
    针对 PDF 处理优化：
    - 页面级别的分批处理
    - 内存友好的图像处理
    - OCR 调用优化
    """
    
    def __init__(
        self,
        pages_per_batch: int = 5,
        max_concurrent_ocr: int = 5,
        gc_after_batch: bool = True
    ):
        super().__init__(
            batch_size=pages_per_batch,
            max_concurrent=max_concurrent_ocr,
            gc_after_batch=gc_after_batch
        )
        self.pages_per_batch = pages_per_batch
        self.max_concurrent_ocr = max_concurrent_ocr
    
    async def process_pdf_pages(
        self,
        doc,  # fitz.Document
        page_processor: Callable[[Any, int], Any],
        total_pages: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        分批处理 PDF 页面
        
        Args:
            doc: PyMuPDF 文档对象
            page_processor: 页面处理函数 async def processor(doc, page_num) -> result
            total_pages: 总页数（可选，默认从 doc 获取）
            progress_callback: 进度回调函数
            
        Returns:
            List[Any]: 每页处理结果
        """
        if total_pages is None:
            total_pages = doc.page_count
        
        logger.info(
            f"Processing PDF with {total_pages} pages, "
            f"batch_size={self.pages_per_batch}, "
            f"max_concurrent={self.max_concurrent_ocr}"
        )
        
        results = [None] * total_pages
        completed = 0
        semaphore = asyncio.Semaphore(self.max_concurrent_ocr)
        
        for batch_start in range(0, total_pages, self.pages_per_batch):
            batch_end = min(batch_start + self.pages_per_batch, total_pages)
            page_nums = list(range(batch_start, batch_end))
            
            logger.debug(
                f"Processing page batch: {batch_start + 1}-{batch_end} "
                f"of {total_pages}"
            )
            
            # 创建页面处理任务
            async def process_page(page_num):
                async with semaphore:
                    return await page_processor(doc, page_num)
            
            tasks = [process_page(page_num) for page_num in page_nums]
            
            # 并发处理当前批次的页面
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for page_num, result in zip(page_nums, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing page {page_num + 1}: {result}")
                    # 创建错误占位结果
                    results[page_num] = self._create_error_chunk(page_num, result)
                else:
                    results[page_num] = result
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total_pages)
            
            # 批处理后清理内存
            if self.gc_after_batch:
                del tasks
                del batch_results
                gc.collect()
                logger.debug(f"Memory cleaned after batch")
        
        logger.info(f"PDF processing completed: {completed}/{total_pages} pages")
        return results
    
    def _create_error_chunk(self, page_num: int, error: Exception):
        """创建错误占位内容块"""
        from app.core.base.processor import ContentChunk
        from app.models.enums import ChunkType
        
        return ContentChunk(
            content=f"[Error processing page {page_num + 1}: {str(error)}]",
            page_number=page_num + 1,
            chunk_type=ChunkType.OCR,
            metadata={'error': str(error)}
        )
    
    async def process_pdf_with_progress(
        self,
        doc,
        page_processor: Callable,
        task_manager=None,
        task_id: str = None
    ) -> List[Any]:
        """
        处理 PDF 并更新任务进度
        
        Args:
            doc: PyMuPDF 文档对象
            page_processor: 页面处理函数
            task_manager: 任务管理器（可选）
            task_id: 任务 ID（可选）
            
        Returns:
            List[Any]: 处理结果
        """
        def progress_callback(completed, total):
            if task_manager and task_id:
                try:
                    task_manager.update_task_progress(
                        task_id, completed, total
                    )
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")
            
            # 每 10% 记录一次日志
            if completed % max(1, total // 10) == 0:
                logger.info(f"Progress: {completed}/{total} pages")
        
        return await self.process_pdf_pages(
            doc,
            page_processor,
            progress_callback=progress_callback
        )


# 全局实例
streaming_processor = StreamingProcessor()
pdf_streaming_processor = PDFStreamingProcessor()
