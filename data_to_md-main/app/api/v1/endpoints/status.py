"""
任务状态查询接口
"""
import logging
from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import FileResponse
from pathlib import Path
from app.models.response import StatusResponse, ErrorResponse
from app.services.conversion.conversion_service import ConversionService
from app.services.storage.file_service import FileService
from app.exceptions.service_exceptions import TaskNotFoundException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/status/{task_id}",
    response_model=StatusResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态信息
    """
    conversion_service = ConversionService()
    
    try:
        status_info = conversion_service.get_task_status(task_id)
        
        response = StatusResponse(
            success=True,
            task_id=status_info['task_id'],
            status=status_info['status'],
            progress=status_info.get('progress'),
            result=status_info.get('result'),
            error=status_info.get('error')
        )
        
        return response
        
    except TaskNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "获取任务状态失败",
                "details": str(e)
            }
        )


@router.get("/download/{task_id}")
async def download_result(task_id: str):
    """
    下载转换结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        Markdown文件
    """
    file_service = FileService()
    
    try:
        # 获取输出文件路径
        file_path = file_service.get_file_path(task_id, is_output=True)
        
        if not file_path or not Path(file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "FILE_NOT_FOUND",
                    "message": "文件不存在",
                    "details": f"任务 {task_id} 的结果文件未找到"
                }
            )
        
        # 根据文件类型设置正确的 media_type
        filename = Path(file_path).name
        if filename.endswith('.pdf'):
            media_type = "application/pdf"
        elif filename.endswith('.md'):
            media_type = "text/markdown"
        else:
            media_type = "application/octet-stream"
        
        # 返回文件
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "下载文件失败",
                "details": str(e)
            }
        )

