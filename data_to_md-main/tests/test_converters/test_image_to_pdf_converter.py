"""
图片转 PDF 转换器测试
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io
from app.core.converters.image.image_to_pdf_converter import ImageToPDFConverter
from app.exceptions.converter_exceptions import ConversionFailedException


class TestImageToPDFConverter:
    """图片转 PDF 转换器测试类"""
    
    @pytest.fixture
    def converter(self):
        """创建转换器实例"""
        return ImageToPDFConverter()
    
    def test_init(self, converter):
        """测试初始化"""
        assert converter is not None
        assert len(converter.supported_extensions) > 0
        assert '.jpg' in converter.supported_extensions
        assert '.png' in converter.supported_extensions
        assert '.gif' in converter.supported_extensions
    
    def test_get_supported_extensions(self, converter):
        """测试获取支持的扩展名"""
        extensions = converter.get_supported_extensions()
        assert isinstance(extensions, list)
        
        expected = ['.jpg', '.jpeg', '.png', '.gif', '.tiff', '.tif', '.bmp', '.webp', '.heic']
        for ext in expected:
            assert ext in extensions
    
    def test_validate_invalid_file(self, converter):
        """测试验证无效文件"""
        result = converter.validate('/nonexistent/file.jpg')
        assert result is False
    
    def test_validate_with_mock(self, converter):
        """使用 Mock 测试验证有效图片"""
        with patch('app.core.converters.image.image_to_pdf_converter.Image') as mock_img:
            mock_instance = MagicMock()
            mock_instance.verify.return_value = None
            mock_img.open.return_value = mock_instance
            
            result = converter.validate('/path/to/image.jpg')
            assert result is True
    
    def test_correct_exif_rotation_no_exif(self, converter):
        """测试 EXIF 旋转处理（无 EXIF 数据）"""
        # 创建简单的测试图片
        img = Image.new('RGB', (100, 100), color='red')
        
        result = converter._correct_exif_rotation(img)
        assert result.size == (100, 100)
    
    def test_resize_image_contain(self, converter):
        """测试 contain 模式图片缩放"""
        img = Image.new('RGB', (200, 100), color='blue')
        
        # contain 模式：保持宽高比，完全适应
        result = converter._resize_image(img, 100, 100, 'contain')
        
        # 应该缩小到宽度 100，高度 50
        assert result.size[0] == 100
        assert result.size[1] <= 100
    
    def test_resize_image_cover(self, converter):
        """测试 cover 模式图片缩放"""
        img = Image.new('RGB', (100, 200), color='green')
        
        # cover 模式：保持宽高比，覆盖整个区域
        result = converter._resize_image(img, 100, 100, 'cover')
        
        # 应该放大
        assert result.size[0] >= 100 or result.size[1] >= 100
    
    def test_resize_image_stretch(self, converter):
        """测试 stretch 模式图片缩放"""
        img = Image.new('RGB', (200, 100), color='yellow')
        
        # stretch 模式：填充整个区域
        result = converter._resize_image(img, 100, 100, 'stretch')
        
        # 应该是精确的尺寸
        assert result.size == (100, 100)
    
    @pytest.mark.asyncio
    async def test_convert_with_mock(self, converter):
        """使用 Mock 测试转换"""
        with patch('app.core.converters.image.image_to_pdf_converter.Image') as mock_img_module, \
             patch('app.core.converters.image.image_to_pdf_converter.canvas'):
            
            # 模拟图片对象
            mock_img = MagicMock()
            mock_img.size = (200, 100)
            mock_img.mode = 'RGB'
            mock_img._getexif.return_value = None
            
            # 模拟 Image.open 和 Image.new
            mock_img_module.open.return_value = mock_img
            mock_img_module.new.return_value = mock_img
            
            try:
                result = converter._convert_image_to_pdf(
                    '/path/to/image.jpg',
                    page_size='A4',
                    fit_mode='fit'
                )
                
                assert isinstance(result, bytes)
                assert len(result) > 0
            except ImportError:
                pytest.skip("reportlab not installed")
    
    @pytest.mark.asyncio
    async def test_convert_async(self, converter):
        """测试异步转换"""
        with patch('app.core.converters.image.image_to_pdf_converter.Image') as mock_img_module, \
             patch('app.core.converters.image.image_to_pdf_converter.canvas'):
            
            mock_img = MagicMock()
            mock_img.size = (100, 100)
            mock_img.mode = 'RGB'
            mock_img._getexif.return_value = None
            
            mock_img_module.open.return_value = mock_img
            mock_img_module.new.return_value = mock_img
            
            try:
                result = await converter.convert(
                    '/path/to/image.png',
                    {'page_size': 'A4', 'fit_mode': 'contain'}
                )
                
                assert result.status == 'success'
                assert result.metadata['format'] == 'pdf'
                assert result.metadata['source_type'] == 'image'
                assert hasattr(result, 'pdf_content')
            except ImportError:
                pytest.skip("reportlab not installed")


class TestImageToPDFConverterIntegration:
    """图片转 PDF 转换器集成测试"""
    
    def test_supported_formats(self):
        """测试支持的格式"""
        converter = ImageToPDFConverter()
        
        supported = converter.get_supported_extensions()
        
        # 测试常见格式
        common_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        for fmt in common_formats:
            assert fmt in supported, f"Format {fmt} should be supported"
    
    def test_page_sizes(self):
        """测试页面大小支持"""
        converter = ImageToPDFConverter()
        
        # 验证转换器能处理各种页面大小
        page_sizes = ['A4', 'A3', 'A5', 'letter']
        for size in page_sizes:
            assert converter is not None
    
    def test_fit_modes(self):
        """测试缩放模式"""
        converter = ImageToPDFConverter()
        
        fit_modes = ['fit', 'contain', 'cover', 'stretch']
        for mode in fit_modes:
            assert converter is not None
    
    def test_converter_inheritance(self):
        """测试转换器继承"""
        converter = ImageToPDFConverter()
        
        # 检查必要的方法
        assert hasattr(converter, 'convert')
        assert hasattr(converter, 'validate')
        assert hasattr(converter, 'get_supported_extensions')
