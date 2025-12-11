"""
文本提取器
从PDF提取文本层
"""
import logging
import re
import fitz  # PyMuPDF
from app.core.common.content_cleaner import ContentCleaner

logger = logging.getLogger(__name__)


class TextExtractor:
    """文本提取器"""
    
    def __init__(self):
        """初始化提取器"""
        self.cleaner = ContentCleaner()
    
    def extract_text(self, page: fitz.Page) -> str:
        """
        提取页面文本

        使用智能段落检测算法，自动区分段落和行内换行符：
        - 基于文本块的位置、缩进和间距判断段落边界
        - 同一段落内的行会自动合并（去除行内换行符）
        - 段落之间用双换行符分隔

        Args:
            page: PyMuPDF页面对象

        Returns:
            str: 提取的文本，段落已正确分隔
        """
        try:
            # 使用 blocks 模式提取文本
            # blocks 返回格式: (x0, y0, x1, y1, "text", block_no, block_type)
            # block_type: 0=文本块, 1=图像块
            blocks = page.get_text("blocks")

            # 过滤出文本块
            text_blocks = []
            for block in blocks:
                if block[6] == 0:  # 文本块
                    block_text = block[4].strip()
                    if block_text:
                        text_blocks.append({
                            'x0': block[0],
                            'y0': block[1],
                            'x1': block[2],
                            'y1': block[3],
                            'text': block_text
                        })

            if not text_blocks:
                return ""

            # 智能合并文本块为段落
            paragraphs = []
            current_paragraph = []
            prev_block = None

            for block in text_blocks:
                # 删除块内的换行符（直接连接，不加空格）
                block_text = block['text'].replace('\n', '')

                # 判断是否应该开始新段落
                should_start_new_paragraph = False

                if prev_block is None:
                    # 第一个块
                    should_start_new_paragraph = False
                else:
                    # 计算垂直间距
                    vertical_gap = block['y0'] - prev_block['y1']
                    avg_height = (prev_block['y1'] - prev_block['y0'] + block['y1'] - block['y0']) / 2

                    # 计算左缩进变化（正值表示当前块更靠右，即有缩进）
                    left_indent_change = block['x0'] - prev_block['x0']

                    # 检查是否是列表项（以数字、括号、圆点等开头）
                    is_list_item = bool(re.match(r'^[\(（]?[一二三四五六七八九十\d]+[\)）、．.]', block_text.strip()))
                    prev_is_list_item = bool(re.match(r'^[\(（]?[一二三四五六七八九十\d]+[\)）、．.]', prev_block['text'].strip()))

                    # 判断条件（新段落的特征）：
                    # 1. 垂直间距较大（超过1.8倍行高）- 明显的段落间距
                    # 2. 左缩进增加（当前行比前一行更靠右超过15个单位）- 新段落开始
                    # 3. 前一个块以句号/冒号结尾 + 垂直间距较大
                    # 4. 列表项之间不分段（除非缩进变化很大）

                    if is_list_item and prev_is_list_item:
                        # 连续的列表项，保持在同一段落（除非缩进变化很大）
                        if abs(left_indent_change) > 20:
                            should_start_new_paragraph = True
                    elif vertical_gap > avg_height * 1.8:
                        # 垂直间距很大，很可能是新段落
                        should_start_new_paragraph = True
                    elif left_indent_change > 15:
                        # 左缩进明显增加，新段落开始
                        should_start_new_paragraph = True
                    elif prev_block['text'].rstrip().endswith(('。', '！', '？', '：', '.', '!', '?', ':')) and vertical_gap > avg_height * 1.2:
                        # 前一个块以句号/冒号结尾，且有一定的垂直间距
                        should_start_new_paragraph = True

                if should_start_new_paragraph and current_paragraph:
                    # 保存当前段落（直接连接，不加空格）
                    paragraphs.append(''.join(current_paragraph))
                    current_paragraph = []

                current_paragraph.append(block_text)
                prev_block = block

            # 添加最后一个段落
            if current_paragraph:
                paragraphs.append(''.join(current_paragraph))

            # 清理每个段落（移除多余空格）
            cleaned_paragraphs = []
            for para in paragraphs:
                # 移除多余空格
                para = re.sub(r'\s+', ' ', para).strip()
                if para:
                    cleaned_paragraphs.append(para)

            # 用双换行符连接段落（Markdown 段落格式）
            text = "\n\n".join(cleaned_paragraphs)

            return text

        except Exception as e:
            logger.error(f"Failed to extract text from page: {str(e)}")
            raise
    
    def clean_text(self, text: str) -> str:
        """
        清理文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        return self.cleaner.clean_text(text)
    
    def text_to_markdown(self, text: str) -> str:
        """
        将文本转换为Markdown格式
        
        Args:
            text: 原始文本
            
        Returns:
            str: Markdown格式文本
        """
        # 简单处理：保持原始文本格式
        # TODO: 可以添加更复杂的格式识别逻辑
        # - 识别标题（字体大小、粗体）
        # - 识别列表（缩进、符号）
        # - 识别段落
        
        return text

