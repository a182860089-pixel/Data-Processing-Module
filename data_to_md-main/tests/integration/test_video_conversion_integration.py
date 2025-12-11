"""
视频转换集成测试
演示完整的视频到Markdown/PDF的转换流程
"""
import pytest
import os
import cv2
import numpy as np
from pathlib import Path
import asyncio
from app.core.factory.converter_factory import ConverterFactory
from app.models.enums import FileType
from app.services.conversion.conversion_service import ConversionService


@pytest.fixture
def sample_video_file(tmp_path):
    """创建示例视频文件"""
    video_path = tmp_path / "demo_video.mp4"
    
    # 创建一个简单的视频文件
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(
        str(video_path),
        fourcc,
        30.0,  # FPS
        (1280, 720)  # 分辨率
    )
    
    # 创建15秒的视频（450帧）
    for i in range(450):
        # 创建不同颜色的帧
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # 根据帧号设置不同的颜色
        if i < 150:
            frame[:] = (255, 0, 0)  # 蓝色
        elif i < 300:
            frame[:] = (0, 255, 0)  # 绿色
        else:
            frame[:] = (0, 0, 255)  # 红色
        
        # 添加时间信息
        timestamp = i / 30.0
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        millis = int((timestamp % 1) * 1000)
        
        time_text = f"{minutes:02d}:{seconds:02d}.{millis:03d}"
        
        cv2.putText(
            frame,
            f"Frame {i} - {time_text}",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            3
        )
        
        out.write(frame)
    
    out.release()
    return str(video_path)


class TestVideoConversionIntegration:
    """视频转换集成测试"""
    
    def test_converter_factory_creates_video_converter(self):
        """测试工厂能否创建视频转换器"""
        factory = ConverterFactory()
        converter = factory.create_converter(FileType.MP4)
        
        assert converter is not None
        assert converter.__class__.__name__ == 'VideoConverter'
    
    def test_all_video_types_supported(self):
        """测试所有视频类型都被支持"""
        factory = ConverterFactory()
        video_types = [FileType.MP4, FileType.AVI, FileType.MOV, FileType.WMV]
        
        for video_type in video_types:
            assert factory.is_supported(video_type)
            converter = factory.create_converter(video_type)
            assert converter is not None
    
    @pytest.mark.asyncio
    async def test_full_video_to_markdown_conversion(self, sample_video_file):
        """测试完整的视频转Markdown流程"""
        from app.core.converters.video.video_converter import VideoConverter
        
        converter = VideoConverter()
        
        # 验证文件
        assert converter.validate(sample_video_file)
        
        # 转换选项
        options = {
            'output_type': 'markdown',
            'keyframe_interval': 3,
            'max_frames': 20,
            'include_metadata': True,
            'include_frames': True,
            'frame_quality': 85
        }
        
        # 执行转换
        result = await converter.convert(sample_video_file, options)
        
        # 验证结果
        assert result.markdown is not None
        assert len(result.markdown) > 100
        assert result.output_type == 'markdown'
        assert '视频内容摘要' in result.markdown
        assert '视频信息' in result.markdown
        assert '关键帧内容' in result.markdown
        assert '15' in result.markdown  # 应该包含15秒的视频
        assert '1280x720' in result.markdown  # 应该包含分辨率
        
        # 验证元数据
        assert result.metadata['duration'] >= 14.9  # 接近15秒
        assert result.metadata['fps'] == 30.0
        assert result.metadata['total_frames'] == 450
        assert result.metadata['resolution'] == '1280x720'
    
    @pytest.mark.asyncio
    async def test_full_video_to_pdf_conversion(self, sample_video_file):
        """测试完整的视频转PDF流程"""
        from app.core.converters.video.video_converter import VideoConverter
        
        converter = VideoConverter()
        
        # 转换选项
        options = {
            'output_type': 'pdf',
            'keyframe_interval': 5,
            'max_frames': 10,
            'include_metadata': True,
            'include_frames': True,
            'frame_quality': 90
        }
        
        # 执行转换
        result = await converter.convert(sample_video_file, options)
        
        # 验证结果
        assert result.pdf_content is not None
        assert len(result.pdf_content) > 5000  # PDF应该有足够的内容
        assert result.output_type == 'pdf'
        assert result.pdf_content.startswith(b'%PDF')  # PDF文件签名
        
        # 验证元数据
        assert result.metadata['frames_extracted'] > 0
        assert result.metadata['duration'] >= 14.9


class TestVideoConversionOptions:
    """视频转换选项测试"""
    
    @pytest.mark.asyncio
    async def test_conversion_without_frames(self, sample_video_file):
        """测试不提取帧的转换"""
        from app.core.converters.video.video_converter import VideoConverter
        
        converter = VideoConverter()
        
        options = {
            'output_type': 'markdown',
            'extract_frames': False,
            'include_metadata': True,
            'include_frames': False
        }
        
        result = await converter.convert(sample_video_file, options)
        
        # 应该只有元数据，没有关键帧
        assert '视频信息' in result.markdown
        assert '关键帧内容' not in result.markdown
    
    @pytest.mark.asyncio
    async def test_conversion_without_metadata(self, sample_video_file):
        """测试不包含元数据的转换"""
        from app.core.converters.video.video_converter import VideoConverter
        
        converter = VideoConverter()
        
        options = {
            'output_type': 'markdown',
            'keyframe_interval': 5,
            'max_frames': 5,
            'include_metadata': False,
            'include_frames': True
        }
        
        result = await converter.convert(sample_video_file, options)
        
        # 应该有关键帧，没有元数据表格
        assert '关键帧内容' in result.markdown
        assert '视频信息' not in result.markdown
    
    @pytest.mark.asyncio
    async def test_custom_keyframe_interval(self, sample_video_file):
        """测试自定义关键帧间隔"""
        from app.core.converters.video.video_converter import VideoConverter
        
        converter = VideoConverter()
        
        # 使用较大的间隔应该产生较少的帧
        options = {
            'output_type': 'markdown',
            'keyframe_interval': 10,  # 10秒间隔
            'max_frames': 100,
            'include_metadata': True,
            'include_frames': True
        }
        
        result = await converter.convert(sample_video_file, options)
        
        # 15秒的视频，10秒间隔应该产生1-2帧
        assert len(result.metadata['frames_extracted']) >= 0


class TestVideoConversionErrorHandling:
    """视频转换错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_invalid_video_file(self, tmp_path):
        """测试处理无效视频文件"""
        from app.core.converters.video.video_converter import VideoConverter
        from app.exceptions.converter_exceptions import ConversionFailedException
        
        converter = VideoConverter()
        
        # 创建一个文本文件，而不是视频
        invalid_file = tmp_path / "not_a_video.txt"
        invalid_file.write_text("This is not a video file")
        
        options = {'output_type': 'markdown'}
        
        with pytest.raises(ConversionFailedException):
            await converter.convert(str(invalid_file), options)
    
    def test_nonexistent_file(self):
        """测试处理不存在的文件"""
        from app.core.converters.video.video_converter import VideoConverter
        
        converter = VideoConverter()
        
        result = converter.validate("/path/that/does/not/exist.mp4")
        assert result is False


# 演示脚本
if __name__ == '__main__':
    print("视频转换集成测试")
    print("=" * 50)
    
    # 运行测试
    pytest.main([__file__, '-v', '-s'])

