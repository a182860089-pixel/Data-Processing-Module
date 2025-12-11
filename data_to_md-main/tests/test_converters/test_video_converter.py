"""
视频转换器测试
"""
import pytest
import os
import cv2
import numpy as np
from pathlib import Path
import asyncio
from app.core.converters.video.video_converter import VideoConverter
from app.core.converters.video.video_processor import VideoProcessor
from app.core.converters.video.markdown_generator import VideoMarkdownGenerator
from app.core.converters.video.pdf_generator import VideoPDFGenerator


@pytest.fixture
def sample_video_file(tmp_path):
    """创建示例视频文件"""
    video_path = tmp_path / "test_video.mp4"
    
    # 创建一个简单的视频文件
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(
        str(video_path),
        fourcc,
        30.0,  # FPS
        (640, 480)  # 分辨率
    )
    
    # 添加10秒的帧（300帧）
    for i in range(300):
        # 创建一个蓝色背景的帧
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (255, 0, 0)  # BGR格式，所以是蓝色
        
        # 添加帧号文本
        cv2.putText(
            frame,
            f"Frame {i}",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )
        
        out.write(frame)
    
    out.release()
    return str(video_path)


class TestVideoConverter:
    """视频转换器测试类"""
    
    def test_converter_initialization(self):
        """测试转换器初始化"""
        converter = VideoConverter()
        assert converter is not None
        assert converter.video_processor is not None
        assert converter.markdown_generator is not None
        assert converter.pdf_generator is not None
    
    def test_validate_video_file(self, sample_video_file):
        """测试视频文件验证"""
        converter = VideoConverter()
        assert converter.validate(sample_video_file) is True
    
    def test_validate_invalid_file(self, tmp_path):
        """测试无效文件验证"""
        converter = VideoConverter()
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("This is not a video")
        
        assert converter.validate(str(invalid_file)) is False
    
    def test_validate_nonexistent_file(self):
        """测试不存在的文件验证"""
        converter = VideoConverter()
        assert converter.validate("/nonexistent/file.mp4") is False
    
    def test_supported_extensions(self):
        """测试支持的扩展名"""
        converter = VideoConverter()
        extensions = converter.get_supported_extensions()
        
        assert '.mp4' in extensions
        assert '.avi' in extensions
        assert '.mov' in extensions
        assert '.wmv' in extensions
    
    @pytest.mark.asyncio
    async def test_video_conversion_to_markdown(self, sample_video_file):
        """测试视频转Markdown"""
        converter = VideoConverter()
        
        options = {
            'output_type': 'markdown',
            'keyframe_interval': 2,
            'max_frames': 10,
            'include_metadata': True,
            'include_frames': True
        }
        
        result = await converter.convert(sample_video_file, options)
        
        assert result is not None
        assert result.markdown is not None
        assert len(result.markdown) > 0
        assert result.output_type == 'markdown'
        assert '视频内容摘要' in result.markdown
        assert '视频信息' in result.markdown
    
    @pytest.mark.asyncio
    async def test_video_conversion_to_pdf(self, sample_video_file):
        """测试视频转PDF"""
        converter = VideoConverter()
        
        options = {
            'output_type': 'pdf',
            'keyframe_interval': 2,
            'max_frames': 5,
            'include_metadata': True,
            'include_frames': True
        }
        
        result = await converter.convert(sample_video_file, options)
        
        assert result is not None
        assert result.pdf_content is not None
        assert len(result.pdf_content) > 0
        assert result.output_type == 'pdf'
        # PDF文件以%PDF开头
        assert result.pdf_content.startswith(b'%PDF')


class TestVideoProcessor:
    """视频处理器测试类"""
    
    @pytest.mark.asyncio
    async def test_process_video(self, sample_video_file):
        """测试视频处理"""
        processor = VideoProcessor()
        
        options = {
            'keyframe_interval': 2,
            'max_frames': 10,
            'extract_frames': True,
            'frame_quality': 85
        }
        
        video_info = await processor.process(sample_video_file, options)
        
        assert video_info is not None
        assert video_info['duration'] > 0
        assert video_info['fps'] > 0
        assert video_info['total_frames'] > 0
        assert video_info['width'] == 640
        assert video_info['height'] == 480
        assert len(video_info['frames']) > 0
        assert video_info['metadata'] is not None
    
    @pytest.mark.asyncio
    async def test_extract_keyframes(self, sample_video_file):
        """测试关键帧提取"""
        processor = VideoProcessor()
        
        options = {
            'keyframe_interval': 1,
            'max_frames': 5,
            'extract_frames': True,
            'frame_quality': 85
        }
        
        video_info = await processor.process(sample_video_file, options)
        frames = video_info['frames']
        
        assert len(frames) > 0
        assert all('timestamp' in frame for frame in frames)
        assert all('time_str' in frame for frame in frames)
        assert all('frame_data' in frame for frame in frames)
        assert all('frame_number' in frame for frame in frames)


class TestVideoMarkdownGenerator:
    """Markdown生成器测试类"""
    
    @pytest.mark.asyncio
    async def test_generate_markdown(self):
        """测试Markdown生成"""
        generator = VideoMarkdownGenerator()
        
        video_info = {
            'duration': 10.0,
            'fps': 30.0,
            'total_frames': 300,
            'width': 640,
            'height': 480,
            'frames': [
                {
                    'index': 0,
                    'frame_number': 0,
                    'timestamp': 0.0,
                    'time_str': '00:00:00.000',
                    'frame_data': 'test_base64_data',
                    'width': 640,
                    'height': 480
                }
            ],
            'metadata': {
                'file_size': 1000000,
                'duration': 10.0,
                'fps': 30.0,
                'total_frames': 300,
                'resolution': '640x480',
                'width': 640,
                'height': 480,
                'frames_extracted': 1,
                'codec': 'h264'
            }
        }
        
        options = {
            'include_metadata': True,
            'include_frames': True
        }
        
        markdown = await generator.generate(video_info, options)
        
        assert markdown is not None
        assert '视频内容摘要' in markdown
        assert '视频信息' in markdown
        assert '640x480' in markdown
        assert '30.00 FPS' in markdown


class TestVideoPDFGenerator:
    """PDF生成器测试类"""
    
    @pytest.mark.asyncio
    async def test_generate_pdf(self):
        """测试PDF生成"""
        generator = VideoPDFGenerator()
        
        video_info = {
            'duration': 10.0,
            'fps': 30.0,
            'total_frames': 300,
            'width': 640,
            'height': 480,
            'frames': [
                {
                    'index': 0,
                    'frame_number': 0,
                    'timestamp': 0.0,
                    'time_str': '00:00:00.000',
                    'frame_data': None,  # 不包含实际帧数据以简化测试
                    'width': 640,
                    'height': 480
                }
            ],
            'metadata': {
                'file_size': 1000000,
                'duration': 10.0,
                'fps': 30.0,
                'total_frames': 300,
                'resolution': '640x480',
                'width': 640,
                'height': 480,
                'frames_extracted': 1,
                'codec': 'h264'
            }
        }
        
        options = {
            'include_metadata': True,
            'include_frames': True
        }
        
        pdf_content = await generator.generate(video_info, options)
        
        assert pdf_content is not None
        assert len(pdf_content) > 0
        assert pdf_content.startswith(b'%PDF')


# 可运行的测试脚本
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

