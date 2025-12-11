"""
视频Markdown生成器
将提取的视频信息转换为Markdown格式
"""
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class VideoMarkdownGenerator:
    """视频Markdown生成器"""
    
    async def generate(
        self,
        video_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> str:
        """
        生成视频转换的Markdown文档
        
        Args:
            video_info: 视频信息字典
            options: 转换选项
        
        Returns:
            str: Markdown内容
        """
        logger.info("Generating video markdown")
        
        include_metadata = options.get('include_metadata', True)
        include_frames = options.get('include_frames', True)
        
        markdown = []
        
        # 标题
        markdown.append("# 视频内容摘要\n")
        
        # 元数据
        if include_metadata:
            markdown.append(self._generate_metadata_section(video_info['metadata']))
        
        # 关键帧内容
        if include_frames and video_info['frames']:
            markdown.append(self._generate_frames_section(video_info['frames']))
        
        # 转换信息
        markdown.append("\n---\n")
        markdown.append(f"*文档生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        return "".join(markdown)
    
    def _generate_metadata_section(self, metadata: Dict[str, Any]) -> str:
        """
        生成元数据部分
        
        Args:
            metadata: 元数据字典
        
        Returns:
            str: Markdown格式的元数据
        """
        section = []
        section.append("## 视频信息\n\n")
        
        # 格式化元数据
        section.append("| 属性 | 值 |\n")
        section.append("|------|----|\n")
        
        info_items = [
            ("时长", self._format_duration(metadata.get('duration', 0))),
            ("分辨率", metadata.get('resolution', 'N/A')),
            ("帧率", f"{metadata.get('fps', 0):.2f} FPS"),
            ("总帧数", str(metadata.get('total_frames', 0))),
            ("编码格式", metadata.get('codec', 'N/A')),
            ("文件大小", self._format_file_size(metadata.get('file_size', 0))),
            ("提取帧数", str(metadata.get('frames_extracted', 0))),
        ]
        
        for key, value in info_items:
            section.append(f"| {key} | {value} |\n")
        
        section.append("\n")
        return "".join(section)
    
    def _generate_frames_section(self, frames: list) -> str:
        """
        生成关键帧部分
        
        Args:
            frames: 帧列表
        
        Returns:
            str: Markdown格式的帧内容
        """
        section = []
        section.append("## 关键帧内容\n\n")
        
        for frame in frames:
            # 帧标题和时间戳
            section.append(f"### 帧 {frame['index'] + 1} - {frame['time_str']}\n\n")
            
            # 插入图像
            if frame.get('frame_data'):
                section.append(f"![Frame {frame['index'] + 1}](data:image/jpeg;base64,{frame['frame_data']})\n\n")
            
            # 帧信息
            section.append(f"- **时间戳**: {frame['time_str']}\n")
            section.append(f"- **帧号**: {frame['frame_number']}\n")
            section.append(f"- **分辨率**: {frame['width']}x{frame['height']}\n")
            section.append("\n")
        
        return "".join(section)
    
    def _format_duration(self, duration: float) -> str:
        """
        格式化视频时长
        
        Args:
            duration: 秒数
        
        Returns:
            str: 格式化的时长字符串
        """
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节数
        
        Returns:
            str: 格式化的文件大小
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"
