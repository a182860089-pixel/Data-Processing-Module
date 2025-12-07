"""
Office 文档转 PDF 转换器测试
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from app.core.converters.office.office_converter import OfficeConverter
from app.exceptions.converter_exceptions import ConversionFailedException


class TestOfficeConverter:
    """Office 转换器测试类"""
    
    @pytest.fixture
    def converter(self):
        """创建转换器实例"""
        return OfficeConverter()
    
    def test_init(self, converter):
        """测试初始化"""
        assert converter is not None
        assert len(converter.supported_extensions) > 0
        assert '.docx' in converter.supported_extensions
        assert '.pptx' in converter.supported_extensions
        assert '.xlsx' in converter.supported_extensions
    
    def test_get_supported_extensions(self, converter):
        """测试获取支持的扩展名"""
        extensions = converter.get_supported_extensions()
        assert isinstance(extensions, list)
        assert '.docx' in extensions
        assert '.pptx' in extensions
        assert '.xlsx' in extensions
    
    @pytest.mark.asyncio
    async def test_convert_with_invalid_extension(self, converter):
        """测试转换无效的文件扩展名"""
        with pytest.raises(ConversionFailedException):
            await converter.convert('/path/to/file.txt', {})
    
    def test_validate_invalid_file(self, converter):
        """测试验证无效文件"""
        result = converter.validate('/nonexistent/file.docx')
        assert result is False
    
    def test_validate_with_mock(self, converter):
        """使用 Mock 测试验证"""
        with patch('app.core.converters.office.office_converter.Document') as mock_doc:
            mock_doc.return_value = MagicMock()
            # 模拟有效文件
            result = converter.validate('/path/to/file.docx')
            assert result is True
    
    @pytest.mark.asyncio
    async def test_convert_docx_success(self, converter):
        """测试 DOCX 转换成功（Mock）"""
        with patch('app.core.converters.office.office_converter.Document') as mock_doc, \
             patch('app.core.converters.office.office_converter.canvas'):
            
            mock_instance = MagicMock()
            mock_instance.paragraphs = [MagicMock(text='Test paragraph')]
            mock_doc.return_value = mock_instance
            
            # 这里我们测试 _convert_docx_to_pdf 方法
            try:
                result = converter._convert_docx_to_pdf('/path/to/test.docx', {})
                assert isinstance(result, bytes)
                assert len(result) > 0
            except ImportError:
                # 如果库不存在则跳过
                pytest.skip("reportlab not installed")
    
    def test_convert_pptx_with_mock(self, converter):
        """使用 Mock 测试 PPTX 转换"""
        with patch('app.core.converters.office.office_converter.Presentation') as mock_prs, \
             patch('app.core.converters.office.office_converter.canvas'):
            
            mock_instance = MagicMock()
            mock_instance.slides = [MagicMock(), MagicMock()]  # 两个幻灯片
            mock_prs.return_value = mock_instance
            
            try:
                result = converter._convert_pptx_to_pdf('/path/to/test.pptx', {})
                assert isinstance(result, bytes)
                assert len(result) > 0
            except ImportError:
                pytest.skip("python-pptx not installed")
    
    def test_convert_xlsx_with_mock(self, converter):
        """使用 Mock 测试 XLSX 转换"""
        with patch('app.core.converters.office.office_converter.load_workbook') as mock_wb, \
             patch('app.core.converters.office.office_converter.canvas'):
            
            mock_instance = MagicMock()
            mock_ws = MagicMock()
            mock_ws.title = 'Sheet1'
            mock_ws.max_row = 5
            mock_ws.iter_rows.return_value = [
                [MagicMock(text='A1'), MagicMock(text='B1')],
                [MagicMock(text='A2'), MagicMock(text='B2')],
            ]
            mock_instance.active = mock_ws
            mock_wb.return_value = mock_instance
            
            try:
                result = converter._convert_xlsx_to_pdf('/path/to/test.xlsx', {})
                assert isinstance(result, bytes)
                assert len(result) > 0
            except ImportError:
                pytest.skip("openpyxl not installed")


class TestOfficeConverterIntegration:
    """Office 转换器集成测试"""
    
    def test_supported_formats(self):
        """测试支持的格式"""
        converter = OfficeConverter()
        
        # 测试所有支持的格式
        supported = converter.get_supported_extensions()
        
        expected_formats = ['.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']
        for fmt in expected_formats:
            assert fmt in supported, f"Format {fmt} should be supported"
    
    def test_converter_inheritance(self):
        """测试转换器继承"""
        converter = OfficeConverter()
        
        # 检查必要的方法
        assert hasattr(converter, 'convert')
        assert hasattr(converter, 'validate')
        assert hasattr(converter, 'get_supported_extensions')
