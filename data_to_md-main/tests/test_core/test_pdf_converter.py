"""
PDF转换器单元测试

测试场景：
1. 纯图片PDF - 验证OCR流程
2. 图文混排PDF - 验证OCR和文本提取混合处理
3. 纯文本PDF - 验证文本提取流程
4. 输出模式 - 验证页码/元数据显示选项
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.core.converters.pdf.pdf_converter import PDFConverter
from app.core.converters.pdf.pdf_analyzer import PDFAnalyzer
from app.models.enums import PDFType
from app.models.file_info import PDFInfo, PageInfo
from app.core.base.processor import ContentChunk


@pytest.fixture
def mock_pdf_info_image():
    """纯图片PDF的模拟信息"""
    return PDFInfo(
        file_path="test_image.pdf",
        file_size=1024000,
        total_pages=3,
        pdf_type=PDFType.IMAGE,
        pages=[
            PageInfo(page_number=1, has_text=False, text_length=0, has_images=True, image_count=1),
            PageInfo(page_number=2, has_text=False, text_length=0, has_images=True, image_count=1),
            PageInfo(page_number=3, has_text=False, text_length=0, has_images=True, image_count=1),
        ],
        metadata={"title": "Test Image PDF"}
    )


@pytest.fixture
def mock_pdf_info_mixed():
    """图文混排PDF的模拟信息（包含表格）"""
    return PDFInfo(
        file_path="test_mixed.pdf",
        file_size=2048000,
        total_pages=5,
        pdf_type=PDFType.MIXED,
        pages=[
            PageInfo(page_number=1, has_text=True, text_length=200, has_images=False, image_count=0),
            PageInfo(page_number=2, has_text=True, text_length=300, has_images=True, image_count=1),  # 有图表
            PageInfo(page_number=3, has_text=True, text_length=250, has_images=True, image_count=0),  # 有表格
            PageInfo(page_number=4, has_text=True, text_length=180, has_images=False, image_count=0),
            PageInfo(page_number=5, has_text=False, text_length=0, has_images=True, image_count=2),
        ],
        metadata={"title": "Test Mixed PDF"}
    )


@pytest.fixture
def mock_pdf_info_text():
    """纯文本PDF的模拟信息"""
    return PDFInfo(
        file_path="test_text.pdf",
        file_size=512000,
        total_pages=2,
        pdf_type=PDFType.TEXT,
        pages=[
            PageInfo(page_number=1, has_text=True, text_length=500, has_images=False, image_count=0),
            PageInfo(page_number=2, has_text=True, text_length=450, has_images=False, image_count=0),
        ],
        metadata={"title": "Test Text PDF"}
    )


@pytest.fixture
def mock_content_chunks():
    """模拟内容片段"""
    return [
        ContentChunk(page_number=1, chunk_type="ocr", content="# Page 1 Content\n\nThis is OCR text."),
        ContentChunk(page_number=2, chunk_type="text", content="# Page 2 Content\n\nThis is extracted text."),
        ContentChunk(page_number=3, chunk_type="ocr", content="# Page 3 Content\n\n| Col1 | Col2 |\n|------|------|\n| A | B |"),
    ]


class TestPDFConverter:
    """PDF转换器测试类"""

    @pytest.mark.asyncio
    async def test_convert_image_pdf_uses_ocr(self, mock_pdf_info_image, mock_content_chunks):
        """
        测试：纯图片PDF应该走OCR流程
        
        验证点：
        1. 所有页面都使用OCR处理
        2. 内容片段类型都是'ocr'
        """
        converter = PDFConverter()
        
        with patch.object(converter.analyzer, 'analyze', return_value=mock_pdf_info_image):
            with patch('app.core.converters.pdf.pdf_converter.ImagePDFProcessor') as MockProcessor:
                mock_processor = MockProcessor.return_value

                async def mock_process(*args, **kwargs):
                    return [
                        ContentChunk(page_number=1, chunk_type="ocr", content="OCR Page 1"),
                        ContentChunk(page_number=2, chunk_type="ocr", content="OCR Page 2"),
                        ContentChunk(page_number=3, chunk_type="ocr", content="OCR Page 3"),
                    ]

                mock_processor.process = mock_process
                
                result = await converter.convert("test_image.pdf", {})
                
                # 验证使用了OCR处理器
                MockProcessor.assert_called_once()
                
                # 验证元数据中ocr_pages数量
                assert result.metadata['ocr_pages'] == 3
                assert result.metadata['text_pages'] == 0
                assert result.status == 'success'


    @pytest.mark.asyncio
    async def test_convert_mixed_pdf_hybrid_processing(self, mock_pdf_info_mixed):
        """
        测试：图文混排PDF应该混合使用OCR和文本提取
        
        验证点：
        1. 有图表的页面使用OCR
        2. 纯文本页面提取文本层
        3. 混合内容片段类型
        """
        converter = PDFConverter()
        
        with patch.object(converter.analyzer, 'analyze', return_value=mock_pdf_info_mixed):
            with patch('app.core.converters.pdf.pdf_converter.MixedPDFProcessor') as MockProcessor:
                mock_processor = MockProcessor.return_value
                # 模拟混合处理结果：部分OCR，部分文本提取
                async def mock_process(*args, **kwargs):
                    return [
                        ContentChunk(page_number=1, chunk_type="text", content="Text Page 1"),
                        ContentChunk(page_number=2, chunk_type="ocr", content="OCR Page 2 with image"),
                        ContentChunk(page_number=3, chunk_type="ocr", content="OCR Page 3 with table"),
                        ContentChunk(page_number=4, chunk_type="text", content="Text Page 4"),
                        ContentChunk(page_number=5, chunk_type="ocr", content="OCR Page 5"),
                    ]

                mock_processor.process = mock_process
                
                result = await converter.convert("test_mixed.pdf", {})
                
                # 验证使用了混排处理器
                MockProcessor.assert_called_once()
                
                # 验证混合处理
                assert result.metadata['ocr_pages'] == 3  # 页面2,3,5
                assert result.metadata['text_pages'] == 2  # 页面1,4
                assert result.status == 'success'


    @pytest.mark.asyncio
    async def test_convert_text_pdf_extracts_text(self, mock_pdf_info_text):
        """
        测试：纯文本PDF应该走文本提取流程
        
        验证点：
        1. 所有页面都使用文本提取
        2. 内容片段类型都是'text'
        """
        converter = PDFConverter()
        
        with patch.object(converter.analyzer, 'analyze', return_value=mock_pdf_info_text):
            with patch('app.core.converters.pdf.pdf_converter.MixedPDFProcessor') as MockProcessor:
                mock_processor = MockProcessor.return_value

                async def mock_process(*args, **kwargs):
                    return [
                        ContentChunk(page_number=1, chunk_type="text", content="Text Page 1"),
                        ContentChunk(page_number=2, chunk_type="text", content="Text Page 2"),
                    ]

                mock_processor.process = mock_process
                
                result = await converter.convert("test_text.pdf", {})
                
                # 验证使用了混排处理器（纯文本也用它）
                MockProcessor.assert_called_once()
                
                # 验证文本提取
                assert result.metadata['ocr_pages'] == 0
                assert result.metadata['text_pages'] == 2
                assert result.status == 'success'


    @pytest.mark.asyncio
    async def test_output_mode_with_page_numbers_and_metadata(self, mock_pdf_info_text):
        """
        测试：模式A - 带页码和元数据的输出
        
        验证点：
        1. Markdown中包含页码标记
        2. Markdown中包含元数据
        """
        converter = PDFConverter()
        
        with patch.object(converter.analyzer, 'analyze', return_value=mock_pdf_info_text):
            with patch('app.core.converters.pdf.pdf_converter.MixedPDFProcessor') as MockProcessor:
                mock_processor = MockProcessor.return_value

                async def mock_process(*args, **kwargs):
                    return [
                        ContentChunk(page_number=1, chunk_type="text", content="Content 1"),
                        ContentChunk(page_number=2, chunk_type="text", content="Content 2"),
                    ]

                mock_processor.process = mock_process
                
                # 模式A: 显示页码和元数据
                options = {
                    'show_page_number': True,
                    'include_metadata': True,
                }
                
                result = await converter.convert("test.pdf", options)
                markdown = result.markdown
                
                # 验证包含元数据
                assert 'title:' in markdown or 'pages:' in markdown
                
                # 验证包含页码标记
                assert '<!-- Page 1' in markdown or 'Page 1' in markdown
                assert '---' in markdown  # 分隔符


    @pytest.mark.asyncio
    async def test_output_mode_without_page_numbers_and_metadata(self, mock_pdf_info_text):
        """
        测试：模式B - 纯内容输出（不带页码和元数据）
        
        验证点：
        1. Markdown中不包含页码标记
        2. Markdown中不包含元数据
        3. 内容流畅连接
        """
        converter = PDFConverter()
        
        with patch.object(converter.analyzer, 'analyze', return_value=mock_pdf_info_text):
            with patch('app.core.converters.pdf.pdf_converter.MixedPDFProcessor') as MockProcessor:
                mock_processor = MockProcessor.return_value

                async def mock_process(*args, **kwargs):
                    return [
                        ContentChunk(page_number=1, chunk_type="text", content="Content 1."),
                        ContentChunk(page_number=2, chunk_type="text", content="Content 2."),
                    ]

                mock_processor.process = mock_process
                
                # 模式B: 不显示页码和元数据
                options = {
                    'show_page_number': False,
                    'include_metadata': False,
                }
                
                result = await converter.convert("test.pdf", options)
                markdown = result.markdown
                
                # 验证不包含元数据
                assert 'title:' not in markdown
                assert 'pages:' not in markdown
                
                # 验证不包含页码标记
                assert '<!-- Page' not in markdown
                assert '---' not in markdown  # 没有分隔符


    @pytest.mark.asyncio
    async def test_compatibility_mode_no_pagination_and_metadata(self, mock_pdf_info_text):
        """
        测试：兼容模式 - no_pagination_and_metadata参数
        
        验证点：
        1. no_pagination_and_metadata=True 等同于模式B
        2. 向后兼容旧代码
        """
        converter = PDFConverter()
        
        with patch.object(converter.analyzer, 'analyze', return_value=mock_pdf_info_text):
            with patch('app.core.converters.pdf.pdf_converter.MixedPDFProcessor') as MockProcessor:
                mock_processor = MockProcessor.return_value

                async def mock_process(*args, **kwargs):
                    return [
                        ContentChunk(page_number=1, chunk_type="text", content="Content 1"),
                    ]

                mock_processor.process = mock_process
                
                # 兼容模式
                options = {
                    'no_pagination_and_metadata': True,
                }
                
                result = await converter.convert("test.pdf", options)
                markdown = result.markdown
                
                # 验证效果等同于模式B
                assert '<!-- Page' not in markdown
                assert 'title:' not in markdown


    def test_processor_selection(self):
        """
        测试：根据PDF类型选择正确的处理器
        
        验证点：
        1. 图片PDF -> ImagePDFProcessor
        2. 混排PDF -> MixedPDFProcessor
        3. 文本PDF -> MixedPDFProcessor（也用混排处理器）
        """
        converter = PDFConverter()
        
        # 测试图片PDF
        from app.core.converters.pdf.image_pdf_processor import ImagePDFProcessor
        processor_image = converter._select_processor(PDFType.IMAGE)
        assert isinstance(processor_image, ImagePDFProcessor)
        
        # 测试混排PDF
        from app.core.converters.pdf.mixed_pdf_processor import MixedPDFProcessor
        processor_mixed = converter._select_processor(PDFType.MIXED)
        assert isinstance(processor_mixed, MixedPDFProcessor)
        
        # 测试文本PDF（也用混排处理器）
        processor_text = converter._select_processor(PDFType.TEXT)
        assert isinstance(processor_text, MixedPDFProcessor)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
