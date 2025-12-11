"""
Markdown生成器
将内容片段合并为完整的Markdown文档
"""
import logging
from typing import List
from datetime import datetime
from app.core.base.processor import ContentChunk
from app.models.file_info import PDFInfo
from app.core.common.content_cleaner import ContentCleaner

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """
    Markdown生成器
    
    支持多种输出模式：
    - 模式A（带页码+元数据）: 适合文档分析、索引和内容审查
    - 模式B（纯内容阅读）: 适合直接阅读、分享和二次编辑
    """

    def __init__(
        self, 
        show_page_number: bool = True,
        include_metadata: bool = True, 
        no_pagination_and_metadata: bool = False
    ):
        """
        初始化生成器

        Args:
            show_page_number: 是否显示页码标记
            include_metadata: 是否包含文档元数据
            no_pagination_and_metadata: 【兼容参数】是否取消分页和元数据(优先级最高)
        """
        # 兼容旧参数：no_pagination_and_metadata 优先级最高
        if no_pagination_and_metadata:
            self.show_page_number = False
            self.include_metadata = False
        else:
            self.show_page_number = show_page_number
            self.include_metadata = include_metadata
        
        self.no_pagination_and_metadata = no_pagination_and_metadata
        self.cleaner = ContentCleaner()
    
    def generate(
        self,
        content_chunks: List[ContentChunk],
        file_info: PDFInfo
    ) -> str:
        """
        生成Markdown文档

        Args:
            content_chunks: 内容片段列表
            file_info: 文件信息

        Returns:
            str: 完整的Markdown文档
        """
        # 模式B: 纯内容阅读模式（不显示页码也不显示元数据）
        if not self.show_page_number and not self.include_metadata:
            return self._generate_unpaginated(content_chunks)

        parts = []

        # 添加元数据（模式A或单独启用）
        if self.include_metadata:
            metadata = self._generate_metadata(file_info)
            parts.append(metadata)

        # 合并各页内容
        for chunk in content_chunks:
            # 添加页面标记（如果启用）
            if self.show_page_number:
                page_marker = f"\n\n<!-- Page {chunk.page_number} ({chunk.chunk_type}) -->\n\n"
                parts.append(page_marker)
            else:
                # 不显示页码时，只添加简单的分隔
                parts.append("\n\n")

            # 添加内容
            parts.append(chunk.content)

            # 添加页面分隔符（如果显示页码）
            if self.show_page_number:
                parts.append("\n\n---\n\n")

        # 合并所有部分
        markdown = "".join(parts)

        # 后处理
        markdown = self.post_process(markdown)

        return markdown
    
    def _generate_metadata(self, file_info: PDFInfo) -> str:
        """
        生成文档元数据
        
        Args:
            file_info: 文件信息
            
        Returns:
            str: 元数据部分
        """
        metadata_lines = [
            "---",
            f"title: {file_info.metadata.get('title', 'Converted Document')}",
            f"pages: {file_info.total_pages}",
            f"pdf_type: {file_info.pdf_type}",
            f"generated_at: {datetime.now().isoformat()}",
            "---",
            ""
        ]
        
        return "\n".join(metadata_lines)
    
    def post_process(self, markdown: str) -> str:
        """
        后处理Markdown内容
        
        Args:
            markdown: 原始Markdown
            
        Returns:
            str: 处理后的Markdown
        """
        # 清理特殊标记
        markdown = self.cleaner.remove_special_markers(markdown)
        
        # 清理Markdown格式
        markdown = self.cleaner.clean_markdown(markdown)
        
        # 规范化空白字符
        markdown = self.cleaner.normalize_whitespace(markdown)
        
        return markdown
    
    def _generate_unpaginated(self, content_chunks: List[ContentChunk]) -> str:
        """
        生成无分页的Markdown（不包含元数据、页面标记和分隔符）

        智能拼接规则:
        - 如果页面末尾是句号等标点,添加一个换行符
        - 否则直接拼接

        Args:
            content_chunks: 内容片段列表

        Returns:
            str: 无分页的Markdown文档
        """
        parts = []
        sentence_endings = {'.', '!', '?', '。', '!', '?'}

        for i, chunk in enumerate(content_chunks):
            content = chunk.content.rstrip()  # 去掉末尾空白

            if content:
                parts.append(content)

                # 如果不是最后一个chunk,根据末尾字符决定是否添加换行
                if i < len(content_chunks) - 1:
                    if content[-1] in sentence_endings:
                        parts.append("\n")

        markdown = "".join(parts)
        markdown = self.post_process(markdown)

        return markdown

    def generate_simple(self, content_chunks: List[ContentChunk]) -> str:
        """
        生成简单的Markdown（不包含元数据和页面标记）

        Args:
            content_chunks: 内容片段列表

        Returns:
            str: Markdown文档
        """
        parts = []

        for chunk in content_chunks:
            parts.append(chunk.content)
            parts.append("\n\n")

        markdown = "".join(parts)
        markdown = self.post_process(markdown)

        return markdown

