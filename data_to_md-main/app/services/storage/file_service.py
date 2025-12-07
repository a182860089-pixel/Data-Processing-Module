"""
文件存储服务
处理文件上传、保存、下载
"""
import os
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from fastapi import UploadFile
from app.config import get_settings
from app.exceptions.service_exceptions import StorageException

logger = logging.getLogger(__name__)


class FileService:
    """文件存储服务"""
    
    def __init__(self):
        """初始化服务"""
        self.settings = get_settings()
        self.upload_dir = Path(self.settings.upload_dir)
        self.output_dir = Path(self.settings.output_dir)
        
        # 确保目录存在
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_upload_file(
        self,
        upload_file: UploadFile,
        task_id: str
    ) -> str:
        """
        保存上传的文件
        
        Args:
            upload_file: 上传的文件
            task_id: 任务ID
            
        Returns:
            str: 保存的文件路径
            
        Raises:
            StorageException: 保存失败
        """
        try:
            # 生成文件名
            filename = self._generate_filename(upload_file.filename, task_id)
            file_path = self.upload_dir / filename
            
            # 保存文件
            with open(file_path, 'wb') as f:
                content = await upload_file.read()
                f.write(content)
            
            logger.info(f"File saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save upload file: {str(e)}")
            raise StorageException(
                message="保存上传文件失败",
                details=str(e)
            )
    
    def save_output_file(
        self,
        content,
        task_id: str,
        original_filename: str,
        is_pdf: bool = False
    ) -> str:
        """
        保存输出文件
        
        Args:
            content: 文件内容（字符串或字节）
            task_id: 任务ID
            original_filename: 原始文件名
            is_pdf: 是否为PDF文件
            
        Returns:
            str: 保存的文件路径
            
        Raises:
            StorageException: 保存失败
        """
        try:
            # 生成输出文件名
            output_filename = self._generate_output_filename(original_filename, task_id, is_pdf=is_pdf)
            file_path = self.output_dir / output_filename
            
            # 保存文件
            if is_pdf:
                # PDF 文件：二进制书写
                with open(file_path, 'wb') as f:
                    f.write(content)
            else:
                # Markdown 文件：文本书写
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            logger.info(f"Output file saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save output file: {str(e)}")
            raise StorageException(
                message="保存输出文件失败",
                details=str(e)
            )
    
    def get_file_path(self, task_id: str, is_output: bool = True) -> Optional[str]:
        """
        获取文件路径
        
        Args:
            task_id: 任务ID
            is_output: 是否为输出文件
            
        Returns:
            Optional[str]: 文件路径
        """
        directory = self.output_dir if is_output else self.upload_dir
        
        # 查找匹配的文件
        for file_path in directory.glob(f"*{task_id}*"):
            if file_path.is_file():
                return str(file_path)
        
        return None
    
    def delete_file(self, file_path: str):
        """
        删除文件
        
        Args:
            file_path: 文件路径
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"File deleted: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
    
    def cleanup_old_files(self, days: int = None):
        """
        清理过期文件
        
        Args:
            days: 保留天数（默认使用配置）
        """
        if days is None:
            days = self.settings.file_retention_days
        
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # 清理上传目录
        self._cleanup_directory(self.upload_dir, cutoff_time)
        
        # 清理输出目录
        self._cleanup_directory(self.output_dir, cutoff_time)
    
    def _cleanup_directory(self, directory: Path, cutoff_time: datetime):
        """
        清理目录中的过期文件
        
        Args:
            directory: 目录路径
            cutoff_time: 截止时间
        """
        try:
            for file_path in directory.glob('*'):
                if file_path.is_file():
                    # 获取文件修改时间
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    # 如果文件过期，删除
                    if mtime < cutoff_time:
                        file_path.unlink()
                        logger.info(f"Cleaned up old file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup directory: {str(e)}")
    
    def _generate_filename(self, original_filename: str, task_id: str) -> str:
        """
        生成文件名
        
        Args:
            original_filename: 原始文件名
            task_id: 任务ID
            
        Returns:
            str: 生成的文件名
        """
        # 获取文件扩展名
        ext = Path(original_filename).suffix
        
        # 生成新文件名：task_id + 扩展名
        return f"{task_id}{ext}"
    
    def _generate_output_filename(self, original_filename: str, task_id: str, is_pdf: bool = False) -> str:
        """
        生成输出文件名
        
        Args:
            original_filename: 原始文件名
            task_id: 任务ID
            is_pdf: 是否为PDF文件
            
        Returns:
            str: 生成的输出文件名
        """
        # 获取原始文件名（不含扩展名）
        stem = Path(original_filename).stem
        
        # 根据类型生成新文件名
        ext = ".pdf" if is_pdf else ".md"
        return f"{stem}_{task_id}{ext}"
    
    def get_file_size(self, file_path: str) -> int:
        """
        获取文件大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            int: 文件大小（字节）
        """
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"Failed to get file size: {str(e)}")
            return 0

