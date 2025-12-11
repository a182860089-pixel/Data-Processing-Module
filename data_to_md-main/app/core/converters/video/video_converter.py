"""
视频转换器
实现视频到Markdown和PDF的转换
支持提取关键帧、时间戳和元数据
"""
import logging
import os
from typing import Dict, Any, List
from pathlib import Path
import cv2
from datetime import timedelta
from app.core.base.converter import BaseConverter, ConversionResult
from app.core.converters.video.video_processor import VideoProcessor
from app.core.converters.video.markdown_generator import VideoMarkdownGenerator
from app.core.converters.video.pdf_generator import VideoPDFGenerator
from app.exceptions.converter_exceptions import ConversionFailedException

logger = logging.getLogger(__name__)


class VideoConverter(BaseConverter):
    """视频转换器 - 支持视频转MD和PDF"""
    
    def __init__(self):
        """初始化转换器"""
        self.video_processor = VideoProcessor()
        self.markdown_generator = VideoMarkdownGenerator()
        self.pdf_generator = VideoPDFGenerator()
    
    async def convert(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """
        转换视频文件
        
        Args:
            file_path: 视频文件路径
            options: 转换选项，包括：
                - output_type: 'markdown' 或 'pdf'（默认markdown）
                - keyframe_interval: 关键帧间隔（秒，默认5）
                - extract_frames: 是否提取帧（默认True）
                - include_metadata: 是否包含元数据（默认True）
                - frame_quality: 帧质量1-100（默认85）
                - max_frames: 最大提取帧数（默认100）
        
        Returns:
            ConversionResult: 转换结果
        """
        logger.info(f"Starting video conversion: {file_path}")
        
        try:
            # 1. 验证视频文件
            if not self.validate(file_path):
                raise ConversionFailedException(
                    message="无效的视频文件",
                    details=f"无法读取视频文件: {file_path}"
                )
            
            # 2. 提取视频信息和关键帧
            output_type = options.get('output_type', 'markdown')
            video_info = await self.video_processor.process(
                file_path=file_path,
                options=options
            )
            logger.info(
                f"Video processed: duration={video_info['duration']}s, "
                f"fps={video_info['fps']}, "
                f"frames_extracted={len(video_info['frames'])}"
            )
            
            # 3. 根据输出类型生成结果
            if output_type == 'pdf':
                # 生成PDF
                pdf_content = await self.pdf_generator.generate(
                    video_info=video_info,
                    options=options
                )
                result = ConversionResult(
                    pdf_content=pdf_content,
                    metadata=video_info['metadata'],
                    status='success',
                    output_type='pdf'
                )
            else:
                # 生成Markdown（默认）
                markdown_content = await self.markdown_generator.generate(
                    video_info=video_info,
                    options=options
                )
                result = ConversionResult(
                    markdown=markdown_content,
                    metadata=video_info['metadata'],
                    status='success',
                    output_type='markdown'
                )
            
            logger.info(f"Video conversion completed successfully")
            return result
            
        except ConversionFailedException:
            raise
        except Exception as e:
            logger.error(f"Video conversion failed: {str(e)}")
            raise ConversionFailedException(
                message="视频转换失败",
                details=str(e)
            )
    
    def validate(self, file_path: str) -> bool:
        """
        验证是否为有效的视频文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            bool: 是否有效
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Video file not found: {file_path}")
                return False
            
            # 尝试打开视频文件
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                logger.error(f"Cannot open video file: {file_path}")
                return False
            
            # 检查是否能读取帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.error(f"Cannot read video frame: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Video validation failed: {str(e)}")
            return False
    
    def get_supported_extensions(self) -> List[str]:
        """
        返回支持的文件扩展名列表
        
        Returns:
            List[str]: 支持的扩展名
        """
        return ['.mp4', '.MP4', '.avi', '.AVI', '.mov', '.MOV', '.wmv', '.WMV', '.mkv', '.MKV', '.flv', '.FLV']

