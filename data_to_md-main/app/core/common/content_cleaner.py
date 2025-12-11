"""
内容清理器
清理和规范化文本内容
"""
import re
import logging

logger = logging.getLogger(__name__)


class ContentCleaner:
    """内容清理器"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        清理文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 移除多余空白（但保留单个空格）
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # 移除多余空行（最多保留一个空行）
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def clean_markdown(markdown: str) -> str:
        """
        清理Markdown内容
        
        Args:
            markdown: 原始Markdown
            
        Returns:
            str: 清理后的Markdown
        """
        if not markdown:
            return ""
        
        # 基础文本清理
        markdown = ContentCleaner.clean_text(markdown)
        
        # 清理多余的markdown代码块标记
        markdown = re.sub(r'```+\s*$', '', markdown, flags=re.MULTILINE)
        markdown = re.sub(r'^```+\s*', '', markdown, flags=re.MULTILINE)
        
        # 规范化标题（确保标题前后有空行）
        markdown = re.sub(r'\n(#{1,6}\s+.+)\n', r'\n\n\1\n\n', markdown)
        
        # 移除多余空行
        markdown = re.sub(r'\n\s*\n+', '\n\n', markdown)
        
        return markdown.strip()
    
    @staticmethod
    def remove_special_markers(text: str) -> str:
        """
        移除特殊标记
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        
        # 移除常见的特殊标记
        patterns = [
            r'<\|end_of_sentence\|>',
            r'<\|end_of_text\|>',
            r'<\|ref\|>',
            r'<\|det\|>',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text)
        
        return text
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        规范化空白字符
        
        Args:
            text: 原始文本
            
        Returns:
            str: 规范化后的文本
        """
        if not text:
            return ""
        
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 移除行尾空白
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        
        # 移除行首空白（但保留缩进）
        # text = re.sub(r'^[ \t]+', '', text, flags=re.MULTILINE)
        
        return text

