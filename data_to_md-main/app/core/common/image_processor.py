"""
图像处理器
处理PDF页面渲染和图像转换
"""
import base64
import io
import logging
from typing import Tuple
from PIL import Image
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class ImageProcessor:
    """图像处理器"""
    
    def render_page_to_image(
        self,
        page: fitz.Page,
        dpi: int = 144
    ) -> Image.Image:
        """
        将PDF页面渲染为图像
        
        Args:
            page: PyMuPDF页面对象
            dpi: 渲染分辨率
            
        Returns:
            PIL Image对象
        """
        try:
            # 计算缩放矩阵
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为pixmap
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            return image
            
        except Exception as e:
            logger.error(f"Failed to render page to image: {str(e)}")
            raise
    
    def image_to_base64(self, image: Image.Image) -> str:
        """
        将图像转换为Base64字符串
        
        Args:
            image: PIL Image对象
            
        Returns:
            str: Base64编码的字符串
        """
        try:
            # 转换为RGB模式（如果是RGBA）
            if image.mode == 'RGBA':
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # 使用alpha通道作为mask
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 保存到BytesIO
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Base64编码
            base64_str = base64.b64encode(buffer.read()).decode('utf-8')
            
            return base64_str
            
        except Exception as e:
            logger.error(f"Failed to convert image to base64: {str(e)}")
            raise
    
    def optimize_image(
        self,
        image: Image.Image,
        max_size: int = 2048
    ) -> Image.Image:
        """
        优化图像尺寸
        
        Args:
            image: PIL Image对象
            max_size: 最大尺寸（宽或高）
            
        Returns:
            PIL Image对象
        """
        try:
            width, height = image.size
            
            # 如果图像尺寸超过max_size，等比缩放
            if width > max_size or height > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Image resized from {width}x{height} to {new_width}x{new_height}")
            
            return image
            
        except Exception as e:
            logger.error(f"Failed to optimize image: {str(e)}")
            raise
    
    def render_page_to_base64(
        self,
        page: fitz.Page,
        dpi: int = 144,
        optimize: bool = True,
        max_size: int = 2048
    ) -> str:
        """
        将PDF页面渲染为Base64字符串（一步到位）
        
        Args:
            page: PyMuPDF页面对象
            dpi: 渲染分辨率
            optimize: 是否优化图像
            max_size: 最大尺寸
            
        Returns:
            str: Base64编码的字符串
        """
        # 渲染为图像
        image = self.render_page_to_image(page, dpi)
        
        # 优化图像（可选）
        if optimize:
            image = self.optimize_image(image, max_size)
        
        # 转换为Base64
        base64_str = self.image_to_base64(image)
        
        return base64_str

