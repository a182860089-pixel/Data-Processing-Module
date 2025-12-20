"""
任务状态查询接口
"""
import logging
from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import FileResponse
from pathlib import Path
from celery import states
from celery.result import AsyncResult
from app.models.enums import TaskStatus
from app.models.response import (
    StatusResponse,
    ErrorResponse,
    ConversionResult,
    ConversionMetadata,
)
from app.services.conversion.conversion_service import ConversionService
from app.services.storage.file_service import FileService
from app.services.queue.celery_app import celery_app
from app.exceptions.service_exceptions import TaskNotFoundException

logger = logging.getLogger(__name__)

router = APIRouter()


def _map_celery_state(state: str) -> TaskStatus:
    """Map Celery state to internal TaskStatus enum."""
    if state in (states.STARTED, states.RETRY, "PROGRESS"):
        return TaskStatus.PROCESSING
    if state == states.SUCCESS:
        return TaskStatus.COMPLETED
    if state in (states.FAILURE, states.REVOKED):
        return TaskStatus.FAILED
    return TaskStatus.PENDING


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
        # 不存在于本地 TaskManager 时，尝试查询 Celery 任务
        try:
            async_result = AsyncResult(task_id, app=celery_app)
            celery_state = async_result.state
            mapped_status = _map_celery_state(celery_state)

            meta = async_result.info if isinstance(async_result.info, dict) else None
            error_info = None
            result_info = None

            if celery_state == states.SUCCESS:
                payload = async_result.result or {}
                metadata = payload.get("metadata", {}) or {}
                conv_metadata = ConversionMetadata(
                    pages_processed=metadata.get("total_pages", 0),
                    ocr_pages=metadata.get("ocr_pages"),
                    text_pages=metadata.get("text_pages"),
                    processing_time=metadata.get("processing_time", 0),
                    file_size=metadata.get("output_file_size", 0),
                    output_type=metadata.get("output_type", payload.get("output_type", "markdown")),
                )
                result_info = ConversionResult(
                    markdown_content=payload.get("markdown_content"),
                    download_url=f"/api/v1/download/{payload.get('task_id', task_id)}",
                    metadata=conv_metadata,
                )
            elif celery_state in (states.FAILURE, states.REVOKED):
                error_info = ErrorResponse(
                    code="TASK_FAILED",
                    message="任务失败",
                    details=str(async_result.info) if async_result.info else "任务执行失败",
                )

            return StatusResponse(
                success=True,
                task_id=task_id,
                status=mapped_status,
                progress=None,
                result=result_info,
                error=error_info,
                message=meta.get("step") if meta else None,
            )
        except ValueError as ve:
            # Celery 反序列化失败（损坏的任务数据），自动清理并返回失败状态
            if "Exception information must include" in str(ve):
                logger.warning(f"Corrupted task data detected for {task_id}, cleaning up...")
                try:
                    # 尝试从 Redis 中删除损坏的任务数据
                    async_result = AsyncResult(task_id, app=celery_app)
                    async_result.forget()
                    logger.info(f"Cleaned up corrupted task: {task_id}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to cleanup task {task_id}: {cleanup_err}")
                
                return StatusResponse(
                    success=True,
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    progress=None,
                    result=None,
                    error=ErrorResponse(
                        code="TASK_CORRUPTED",
                        message="任务数据损坏，已自动清理",
                        details="请重新提交任务",
                    ),
                )
            raise
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

