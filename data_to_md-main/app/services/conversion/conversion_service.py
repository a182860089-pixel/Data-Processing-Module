"""
转换服务
统一的转换入口，协调转换流程
"""
import logging
import time
from typing import Dict, Any
from app.core.factory.file_type_detector import FileTypeDetector
from app.core.factory.converter_factory import ConverterFactory
from app.services.conversion.task_manager import TaskManager
from app.services.storage.file_service import FileService
from app.models.enums import TaskStatus
from app.exceptions.converter_exceptions import ConversionFailedException

logger = logging.getLogger(__name__)


class ConversionService:
    """转换服务"""
    
    def __init__(self):
        """初始化服务"""
        self.file_type_detector = FileTypeDetector()
        self.converter_factory = ConverterFactory()
        self.task_manager = TaskManager()
        self.file_service = FileService()
    
    async def convert(
        self,
        file_path: str,
        filename: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        转换文件为Markdown
        
        Args:
            file_path: 文件路径
            filename: 文件名
            options: 转换选项
            
        Returns:
            Dict[str, Any]: 转换结果
        """
        start_time = time.time()
        
        # 1. 检测文件类型
        file_type = self.file_type_detector.detect(file_path)
        logger.info(f"File type detected: {file_type}")
        
        # 2. 创建任务
        task = self.task_manager.create_task(
            filename=filename,
            file_path=file_path,
            file_type=file_type.value
        )
        
        try:
            # 3. 更新任务状态为处理中
            self.task_manager.update_task_status(
                task.task_id,
                TaskStatus.PROCESSING
            )
            
            # 4. 创建转换器
            converter = self.converter_factory.create_converter(file_type)
            
            # 5. 执行转换
            result = await converter.convert(file_path, options)
            
            # 6. 保存结果
            output_path = self.file_service.save_output_file(
                content=result.markdown,
                task_id=task.task_id,
                original_filename=filename
            )
            
            # 7. 计算处理时间
            processing_time = time.time() - start_time
            
            # 8. 更新任务为完成
            metadata = result.metadata.copy()
            metadata['processing_time'] = processing_time
            metadata['output_file_size'] = self.file_service.get_file_size(output_path)
            
            self.task_manager.complete_task(
                task_id=task.task_id,
                result_path=output_path,
                markdown_content=result.markdown,
                metadata=metadata
            )
            
            logger.info(
                f"Conversion completed: {task.task_id}, "
                f"time={processing_time:.2f}s"
            )
            
            # 9. 返回结果
            return {
                'task_id': task.task_id,
                'status': 'completed',
                'markdown_content': result.markdown,
                'output_path': output_path,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}")
            
            # 标记任务为失败
            self.task_manager.fail_task(
                task_id=task.task_id,
                error_message=str(e)
            )
            
            raise ConversionFailedException(
                message="文件转换失败",
                details=str(e)
            )
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态信息
        """
        task = self.task_manager.get_task(task_id)
        
        result = {
            'task_id': task.task_id,
            'status': task.status,
            'progress': {
                'current_page': task.current_page,
                'total_pages': task.total_pages,
                'percentage': task.progress
            }
        }
        
        if task.status == TaskStatus.COMPLETED:
            result['result'] = {
                'markdown_content': task.markdown_content,
                'download_url': f"/api/v1/download/{task.task_id}",
                'metadata': task.metadata
            }
        elif task.status == TaskStatus.FAILED:
            result['error'] = {
                'message': task.error_message
            }
        
        return result

