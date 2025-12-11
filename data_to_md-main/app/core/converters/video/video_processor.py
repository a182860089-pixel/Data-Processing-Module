"""
视频处理器
提取视频的关键帧、时间戳和元数据
"""
import logging
import cv2
import os
from typing import Dict, Any, List
from pathlib import Path
from datetime import timedelta
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class VideoProcessor:
    """视频处理器 - 提取帧和元数据"""
    
    def __init__(self):
        """初始化处理器"""
        self.supported_formats = ['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv']
    
    async def process(
        self,
        file_path: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理视频文件，提取关键帧和元数据
        
        Args:
            file_path: 视频文件路径
            options: 处理选项
        
        Returns:
            Dict: 包含视频信息、关键帧等数据
        """
        logger.info(f"Processing video: {file_path}")
        
        cap = cv2.VideoCapture(file_path)
        
        try:
            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"Video info: fps={fps}, frames={total_frames}, "
                       f"resolution={width}x{height}, duration={duration:.2f}s")
            
            # 提取关键帧
            keyframe_interval = options.get('keyframe_interval', 5)  # 秒
            extract_frames = options.get('extract_frames', True)
            max_frames = options.get('max_frames', 100)
            frame_quality = options.get('frame_quality', 85)
            
            frames = []
            if extract_frames:
                frames = self._extract_keyframes(
                    cap=cap,
                    fps=fps,
                    total_frames=total_frames,
                    keyframe_interval=keyframe_interval,
                    max_frames=max_frames,
                    frame_quality=frame_quality
                )
            
            # 元数据
            metadata = {
                'file_size': os.path.getsize(file_path),
                'duration': duration,
                'fps': fps,
                'total_frames': total_frames,
                'resolution': f"{width}x{height}",
                'width': width,
                'height': height,
                'frames_extracted': len(frames),
                'codec': self._get_codec_name(cap)
            }
            
            logger.info(f"Extracted {len(frames)} keyframes")
            
            return {
                'duration': duration,
                'fps': fps,
                'total_frames': total_frames,
                'width': width,
                'height': height,
                'frames': frames,
                'metadata': metadata
            }
            
        finally:
            cap.release()
    
    def _extract_keyframes(
        self,
        cap: cv2.VideoCapture,
        fps: float,
        total_frames: int,
        keyframe_interval: float,
        max_frames: int,
        frame_quality: int
    ) -> List[Dict[str, Any]]:
        """
        提取关键帧
        
        Args:
            cap: 视频捕获对象
            fps: 帧率
            total_frames: 总帧数
            keyframe_interval: 关键帧间隔（秒）
            max_frames: 最大帧数
            frame_quality: 帧质量
        
        Returns:
            List: 关键帧列表
        """
        frames = []
        interval_frames = int(keyframe_interval * fps)
        
        if interval_frames < 1:
            interval_frames = 1
        
        frame_number = 0
        frame_index = 0
        
        while frame_number < total_frames and len(frames) < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # 计算时间戳
            timestamp = frame_number / fps
            time_str = self._format_timestamp(timestamp)
            
            # 编码图像为base64（用于Markdown和PDF）
            frame_base64 = self._encode_frame_to_base64(frame, frame_quality)
            
            frames.append({
                'index': frame_index,
                'frame_number': frame_number,
                'timestamp': timestamp,
                'time_str': time_str,
                'frame_data': frame_base64,
                'height': frame.shape[0],
                'width': frame.shape[1]
            })
            
            frame_number += interval_frames
            frame_index += 1
        
        return frames
    
    def _encode_frame_to_base64(self, frame, quality: int = 85) -> str:
        """
        将帧编码为base64字符串
        
        Args:
            frame: OpenCV帧
            quality: 图像质量
        
        Returns:
            str: Base64编码的图像
        """
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        return frame_base64
    
    def _format_timestamp(self, timestamp: float) -> str:
        """
        格式化时间戳
        
        Args:
            timestamp: 秒数
        
        Returns:
            str: 格式化的时间字符串 (HH:MM:SS.ms)
        """
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        milliseconds = int((timestamp % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def _get_codec_name(self, cap: cv2.VideoCapture) -> str:
        """
        获取视频编码格式
        
        Args:
            cap: 视频捕获对象
        
        Returns:
            str: 编码格式名称
        """
        try:
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            return codec.strip()
        except:
            return "unknown"

