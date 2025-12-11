"""
WebP图片压缩器
从原始脚本中提取核心逻辑并封装为可复用的类
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

# pyvips将在需要时延迟导入
pyvips = None

from app.exceptions.converter_exceptions import ConverterException

logger = logging.getLogger(__name__)

# 支持的输入图片格式
SUPPORTED_IMAGE_FORMATS = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", 
    ".bmp", ".webp", ".heic", ".heif", ".gif"
}


class WebPCompressor:
    """
    WebP图片压缩器
    
    使用pyvips进行高质量、高性能的图片压缩
    """
    
    def __init__(self):
        """初始化压缩器"""
        global pyvips
        
        # 延迟导入pyvips
        if pyvips is None:
            try:
                import pyvips as _pyvips
                pyvips = _pyvips
            except ImportError:
                raise ImportError(
                    "pyvips is required for image compression. "
                    "Install it with: pip install pyvips\n"
                    "Note: pyvips also requires libvips library. "
                    "On Windows, you may need to install libvips binaries."
                )
        
        try:
            # 测试pyvips是否有libvips支持
            pyvips.Image.new_from_array([[0]])
            logger.info("WebP压缩器初始化成功")
        except Exception as e:
            raise ImportError(
                f"pyvips requires libvips library. Error: {str(e)}\n"
                "Please install libvips: https://www.libvips.org/install.html"
            )
    
    def is_supported_format(self, file_path: Path) -> bool:
        """
        检查文件格式是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否支持该格式
        """
        return file_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    
    def is_animated(self, image: 'pyvips.Image') -> bool:
        """
        检查是否为动图
        
        Args:
            image: pyvips图像对象
            
        Returns:
            bool: 是否为动图
        """
        try:
            return int(getattr(image, 'n_pages', 1)) > 1
        except Exception:
            return False
    
    def ensure_srgb(self, image: 'pyvips.Image') -> 'pyvips.Image':
        """
        确保图像为sRGB色彩空间
        
        Args:
            image: pyvips图像对象
            
        Returns:
            转换后的图像
        """
        try:
            if image.interpretation != pyvips.Interpretation.srgb:
                return image.colourspace(pyvips.Interpretation.srgb)
        except Exception:
            pass
        return image
    
    def maybe_autorotate(self, image: 'pyvips.Image') -> 'pyvips.Image':
        """
        根据EXIF信息自动旋转图像
        
        Args:
            image: pyvips图像对象
            
        Returns:
            旋转后的图像
        """
        try:
            res = image.autorot()
            if isinstance(res, pyvips.Image):
                return res
            if isinstance(res, (tuple, list)) and len(res) >= 1 and isinstance(res[0], pyvips.Image):
                return res[0]
        except Exception:
            pass
        return image
    
    def resize_to_box(
        self, 
        image: 'pyvips.Image', 
        max_width: int, 
        max_height: int
    ) -> 'pyvips.Image':
        """
        按比例缩放图像，保证不超过最大宽高
        
        Args:
            image: pyvips图像对象
            max_width: 最大宽度
            max_height: 最大高度
            
        Returns:
            缩放后的图像
        """
        width, height = image.width, image.height
        
        if width <= max_width and height <= max_height:
            return image
        
        scale = min(max_width / width, max_height / height)
        
        # 大幅缩小时，先整数缩小再连续缩放，提升质量和性能
        try:
            shrink = max(1, int(1 / scale))
            if shrink > 1:
                image = image.shrink(shrink, shrink)
                width, height = image.width, image.height
                scale = min(max_width / width, max_height / height)
        except Exception:
            pass
        
        return image.resize(scale, kernel=pyvips.Kernel.LANCZOS3)
    
    def save_webp(
        self, 
        image: 'pyvips.Image', 
        output_path: Path, 
        quality: int
    ) -> None:
        """
        保存为WebP格式
        
        Args:
            image: pyvips图像对象
            output_path: 输出路径
            quality: 压缩质量 (0-100)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 尝试多种保存方式，确保兼容性
        tried_methods = []
        
        try:
            image.write_to_file(str(output_path), Q=quality, strip=True)
            return
        except Exception as e:
            tried_methods.append(("write_to_file(strip=True)", str(e)))
        
        try:
            image.webpsave(str(output_path), Q=quality, strip=True)
            return
        except Exception as e:
            tried_methods.append(("webpsave(strip=True)", str(e)))
        
        try:
            image.write_to_file(str(output_path), Q=quality)
            return
        except Exception as e:
            tried_methods.append(("write_to_file(no-strip)", str(e)))
        
        # 最后尝试
        try:
            image.webpsave(str(output_path), Q=quality)
            return
        except Exception as e:
            tried_methods.append(("webpsave(no-strip)", str(e)))
            raise ConverterException(
                message="保存WebP失败",
                details=f"尝试了多种方法但都失败: {tried_methods}"
            )
    
    def compress(
        self,
        input_path: Path,
        output_path: Path,
        quality: int = 90,
        max_width: int = 1920,
        max_height: int = 1080,
        overwrite: bool = True
    ) -> Tuple[bool, dict]:
        """
        压缩单张图片为WebP格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            quality: WebP质量 (0-100，默认90)
            max_width: 最大宽度 (默认1920)
            max_height: 最大高度 (默认1080)
            overwrite: 是否覆盖已存在文件 (默认True)
            
        Returns:
            Tuple[bool, dict]: (是否成功, 元数据字典)
            
        Raises:
            ConverterException: 压缩失败时抛出
        """
        # 检查格式支持
        if not self.is_supported_format(input_path):
            raise ConverterException(
                message=f"不支持的图片格式: {input_path.suffix}",
                details=f"支持的格式: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )
        
        # 检查输入文件是否存在
        if not input_path.exists():
            raise ConverterException(
                message="输入文件不存在",
                details=str(input_path)
            )
        
        # 检查输出文件
        if output_path.exists() and not overwrite:
            logger.info(f"输出文件已存在，跳过: {output_path}")
            return False, {"reason": "file_exists"}
        
        try:
            # 记录原始文件大小
            original_size = input_path.stat().st_size
            original_width = 0
            original_height = 0
            
            # 加载图像（顺序读取模式，适合大图）
            image = pyvips.Image.new_from_file(str(input_path), access="sequential")
            original_width = image.width
            original_height = image.height
            
            # 跳过动图
            if self.is_animated(image):
                logger.warning(f"跳过动图: {input_path}")
                return False, {"reason": "animated_image"}
            
            # EXIF自动旋转
            image = self.maybe_autorotate(image)
            
            # 转换色彩空间
            image = self.ensure_srgb(image)
            
            # 缩放图像
            image = self.resize_to_box(image, max_width, max_height)
            
            # 保存为WebP
            self.save_webp(image, output_path, quality)
            
            # 获取输出文件大小
            output_size = output_path.stat().st_size
            compression_ratio = (1 - output_size / original_size) * 100 if original_size > 0 else 0
            
            metadata = {
                "original_size": original_size,
                "output_size": output_size,
                "compression_ratio": round(compression_ratio, 2),
                "original_dimensions": f"{original_width}x{original_height}",
                "output_dimensions": f"{image.width}x{image.height}",
                "quality": quality
            }
            
            logger.info(
                f"压缩成功: {input_path.name} "
                f"({original_size/1024:.1f}KB -> {output_size/1024:.1f}KB, "
                f"压缩率: {compression_ratio:.1f}%)"
            )
            
            return True, metadata
            
        except Exception as e:
            logger.error(f"压缩失败: {input_path} - {str(e)}")
            raise ConverterException(
                message="图片压缩失败",
                details=str(e)
            )
