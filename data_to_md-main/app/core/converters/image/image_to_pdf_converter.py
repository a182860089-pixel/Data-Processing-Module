"""
图片转 PDF 转换器
支持单张或多张图片转换为 PDF
"""
import logging
from typing import Dict, Any, List
from pathlib import Path
import io
from PIL import Image
from app.core.base.converter import BaseConverter, ConversionResult
from app.exceptions.converter_exceptions import ConversionFailedException

logger = logging.getLogger(__name__)


class ImageToPDFConverter(BaseConverter):
    """图片转 PDF 转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.supported_extensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.tif', '.bmp', '.webp', '.heic'
        ]
    
    async def convert(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """
        将单张或多张图片转换为 PDF
        支持以下两种方式：
        1. file_path 为单个文件路径
        2. options 中包含 'file_paths' 列表（多张图片）
        
        Args:
            file_path: 源图片文件路径（兼容单文件）
            options: 转换选项，可包含 file_paths 列表
            
        Returns:
            ConversionResult: 转换结果
        """
        try:
            # 获取转换选项
            page_size = options.get('page_size', 'A4')
            fit_mode = options.get('fit_mode', 'fit')  # contain/cover/stretch
            
            # 检查是否有多个文件
            file_paths = options.get('file_paths')
            if file_paths and isinstance(file_paths, list) and len(file_paths) > 0:
                logger.info(f"Starting multi-image to PDF conversion: {len(file_paths)} images")
                # 多张图片转 PDF
                pdf_content = self._convert_multiple_images_to_pdf(file_paths, page_size, fit_mode)
            else:
                logger.info(f"Starting single image to PDF conversion: {file_path}")
                # 单张图片转 PDF
                pdf_content = self._convert_image_to_pdf(file_path, page_size, fit_mode)
            
            logger.info(f"Image to PDF conversion completed: {len(pdf_content)} bytes")
            
            result = ConversionResult(
                pdf_content=pdf_content,
                metadata={
                    'format': 'pdf',
                    'source_type': 'image',
                    'file_size': len(pdf_content),
                    'page_size': page_size,
                    'image_count': len(file_paths) if file_paths else 1,
                },
                status='success',
                output_type='pdf'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Image to PDF conversion failed: {str(e)}")
            raise ConversionFailedException(
                message="图片转 PDF 失败",
                details=str(e)
            )
    
    def _convert_image_to_pdf(
        self,
        file_path: str,
        page_size: str = 'A4',
        fit_mode: str = 'fit'
    ) -> bytes:
        """
        将单张或多张图片转换为 PDF
        
        Args:
            file_path: 图片文件路径
            page_size: 页面大小（A4、Letter 等）
            fit_mode: 缩放模式（fit、contain、cover、stretch）
            
        Returns:
            bytes: PDF 内容
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4, A3, A5
            from reportlab.lib.units import inch
            from reportlab.lib.utils import ImageReader
            
            # 获取页面大小
            page_sizes = {
                'A4': A4,
                'A3': A3,
                'A5': A5,
                'letter': letter,
            }
            page_dim = page_sizes.get(page_size, A4)
            width, height = page_dim
            
            # 打开图片
            img = Image.open(file_path)
            
            # 处理 EXIF 旋转
            img = self._correct_exif_rotation(img)
            
            # 转换色彩空间到 RGB（如果需要）
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 缩放图片以适应页面
            img_width, img_height = img.size
            img = self._resize_image(img, width, height, fit_mode)
            
            # 保存图片到临时缓冲区
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # 创建 PDF
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=page_dim)
            
            # 计算图片在页面上的位置（居中）
            img_width_pt = width - 2 * 0.5 * inch
            img_height_pt = height - 2 * 0.5 * inch
            
            c.drawImage(
                ImageReader(img_buffer),
                0.5 * inch,
                0.5 * inch,
                width=img_width_pt,
                height=img_height_pt,
                preserveAspectRatio=True
            )
            
            c.showPage()
            c.save()
            
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Image conversion to PDF failed: {str(e)}")
            raise ConversionFailedException(
                message="图片转 PDF 处理失败",
                details=str(e)
            )
    
    def _correct_exif_rotation(self, img: Image.Image) -> Image.Image:
        """
        根据 EXIF 信息修正图片旋转
        
        Args:
            img: PIL 图片对象
            
        Returns:
            Image.Image: 修正后的图片
        """
        try:
            from PIL import ExifTags
            
            exif_data = img._getexif()
            if not exif_data:
                return img
            
            exif = {ExifTags.TAGS[k]: v for k, v in exif_data.items()}
            orientation = exif.get('Orientation', 1)
            
            # 根据 EXIF 方向值旋转
            if orientation == 2:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 4:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                img = img.transpose(Image.ROTATE_90).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 7:
                img = img.transpose(Image.ROTATE_270).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
            
            return img
            
        except Exception:
            return img
    
    def _convert_multiple_images_to_pdf(
        self,
        file_paths: List[str],
        page_size: str = 'A4',
        fit_mode: str = 'fit'
    ) -> bytes:
        """
        将多张图片按顺序拼接成多页 PDF
        
        Args:
            file_paths: 图片文件路径列表
            page_size: 页面大小（A4、Letter 等）
            fit_mode: 缩放模式（fit、contain、cover、stretch）
            
        Returns:
            bytes: PDF 内容
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4, A3, A5
            from reportlab.lib.units import inch
            from reportlab.lib.utils import ImageReader
            
            # 获取页面大小
            page_sizes = {
                'A4': A4,
                'A3': A3,
                'A5': A5,
                'letter': letter,
            }
            page_dim = page_sizes.get(page_size, A4)
            width, height = page_dim
            
            # 创建 PDF
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=page_dim)
            
            # 计算图片在页面上的位置（居中）
            img_width_pt = width - 2 * 0.5 * inch
            img_height_pt = height - 2 * 0.5 * inch
            
            # 逐张处理每个图片
            for idx, file_path in enumerate(file_paths):
                logger.info(f"Processing image {idx + 1}/{len(file_paths)}: {file_path}")
                
                # 打开图片
                img = Image.open(file_path)
                
                # 处理 EXIF 旋转
                img = self._correct_exif_rotation(img)
                
                # 转换色彩空间到 RGB（如果需要）
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 缩放图片以适应页面
                img = self._resize_image(img, width, height, fit_mode)
                
                # 保存图片到临时缓冲区
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                # 绘制图片到 PDF 页面
                c.drawImage(
                    ImageReader(img_buffer),
                    0.5 * inch,
                    0.5 * inch,
                    width=img_width_pt,
                    height=img_height_pt,
                    preserveAspectRatio=True
                )
                
                # 除了最后一张，都需要添加新页面
                if idx < len(file_paths) - 1:
                    c.showPage()
            
            c.showPage()
            c.save()
            
            pdf_buffer.seek(0)
            logger.info(f"Successfully created multi-image PDF with {len(file_paths)} pages")
            return pdf_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Multi-image to PDF conversion failed: {str(e)}")
            raise ConversionFailedException(
                message="多张图片转 PDF 失败",
                details=str(e)
            )
    
    def _resize_image(
        self,
        img: Image.Image,
        max_width: float,
        max_height: float,
        fit_mode: str
    ) -> Image.Image:
        """
        按指定模式缩放图片
        
        Args:
            img: PIL 图片对象
            max_width: 最大宽度
            max_height: 最大高度
            fit_mode: 缩放模式
            
        Returns:
            Image.Image: 缩放后的图片
        """
        img_width, img_height = img.size
        
        if fit_mode == 'contain':
            # 保持宽高比，缩放以完全适应
            scale = min(max_width / img_width, max_height / img_height)
            new_size = (int(img_width * scale), int(img_height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        elif fit_mode == 'cover':
            # 保持宽高比，缩放以覆盖整个区域（可能裁剪）
            scale = max(max_width / img_width, max_height / img_height)
            new_size = (int(img_width * scale), int(img_height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        elif fit_mode == 'stretch':
            # 拉伸以完全填充区域
            img = img.resize((int(max_width), int(max_height)), Image.Resampling.LANCZOS)
        
        return img
    
    def validate(self, file_path: str) -> bool:
        """验证是否为有效的图片文件"""
        try:
            img = Image.open(file_path)
            img.verify()
            return True
        except Exception as e:
            logger.error(f"Image file validation failed: {str(e)}")
            return False
    
    def get_supported_extensions(self) -> List[str]:
        """返回支持的文件扩展名列表"""
        return self.supported_extensions
