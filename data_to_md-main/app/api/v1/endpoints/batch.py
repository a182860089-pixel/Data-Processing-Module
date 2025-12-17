"""
批量转换接口
处理多文件批量上传和转换请求

优化特性：
- 动态并发控制
- 智能优先级队列
- 结果缓存
- 性能监控
"""
import os
import json
import logging
import zipfile
from io import BytesIO
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List, Optional

from app.models.response import ErrorResponse
from app.services.conversion.optimized_batch_manager import optimized_batch_manager
from app.services.storage.file_service import FileService
from app.utils.performance import performance_manager
from app.utils.cache import get_conversion_cache
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
file_service = FileService()
settings = get_settings()

# 批量转换限制
MAX_BATCH_FILES = 20
MAX_FILE_SIZE_MB = 100


@router.post(
    "/convert/batch",
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def batch_convert(
    files: List[UploadFile] = File(..., description="要转换的文件列表（最多20个）"),
    options: Optional[str] = Form(None, description="转换选项（JSON格式）"),
    batch_name: Optional[str] = Form(None, description="批次名称（可选）")
):
    """
    批量转换文件为Markdown
    
    支持的文件类型：PDF, Office文档, 图片
    限制：最多20个文件，每个最大100MB
    """
    # 1. 验证文件数量
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"最多支持 {MAX_BATCH_FILES} 个文件"
        )
    
    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一个文件"
        )
    
    # 2. 解析转换选项
    convert_options = {}
    if options:
        try:
            convert_options = json.loads(options)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="转换选项格式错误"
            )
    
    # 3. 保存上传文件
    file_infos = []
    
    try:
        for upload_file in files:
            content = await upload_file.read()
            file_size = len(content)
            
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件 {upload_file.filename} 超过大小限制"
                )
            
            file_path = file_service.save_upload_file(
                content=content,
                filename=upload_file.filename
            )
            
            file_infos.append({
                "path": file_path,
                "filename": upload_file.filename,
                "size": file_size
            })
        
        # 4. 调用优化的批量处理管理器
        batch = await optimized_batch_manager.process_batch(
            files=file_infos,
            options=convert_options,
            batch_name=batch_name
        )
        
        return {
            "success": True,
            "batch_id": batch.batch_id,
            "batch_name": batch.batch_name,
            "status": batch.status.value,
            "total_files": batch.total_files,
            "completed_files": batch.metadata.get("completed_files", 0),
            "failed_files": batch.metadata.get("failed_files", 0),
            "cached_files": batch.metadata.get("cached_files", 0),
            "batch_status_url": f"/api/v1/batch/{batch.batch_id}",
            "tasks": [
                {
                    "task_id": t.get("task_id"),
                    "filename": t.get("filename"),
                    "status": t.get("status"),
                    "from_cache": t.get("from_cache", False)
                }
                for t in batch.tasks
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch conversion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量转换失败: {str(e)}"
        )


@router.get(
    "/batch/{batch_id}",
    responses={404: {"model": ErrorResponse}}
)
async def get_batch_status(batch_id: str):
    """查询批次状态"""
    try:
        batch = optimized_batch_manager.get_batch(batch_id)
        
        return {
            "success": True,
            "batch_id": batch.batch_id,
            "batch_name": batch.batch_name,
            "status": batch.status.value,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "total_files": batch.total_files,
            "progress": batch.metadata.get("progress_percentage", 0),
            "statistics": {
                "completed_files": batch.metadata.get("completed_files", 0),
                "failed_files": batch.metadata.get("failed_files", 0),
                "cached_files": batch.metadata.get("cached_files", 0)
            },
            "tasks": batch.tasks
        }
        
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"批次不存在: {batch_id}"
        )


@router.get("/batch/{batch_id}/download")
async def download_batch_result(batch_id: str):
    """下载批次转换结果为ZIP"""
    try:
        batch = optimized_batch_manager.get_batch(batch_id)
        
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for task in batch.tasks:
                if task.get("status") == "completed":
                    result = task.get("result", {})
                    content = result.get("markdown_content", "")
                    if isinstance(result, dict) and "content" in result:
                        content = result.get("content", "")
                    
                    if content:
                        original_name = task.get("filename", "unknown")
                        md_name = os.path.splitext(original_name)[0] + ".md"
                        zip_file.writestr(md_name, content)
            
            summary = {
                "batch_id": batch.batch_id,
                "status": batch.status.value,
                "total_files": batch.total_files,
                "completed_files": batch.metadata.get("completed_files", 0),
                "failed_files": batch.metadata.get("failed_files", 0)
            }
            zip_file.writestr(
                "batch_summary.json",
                json.dumps(summary, ensure_ascii=False, indent=2)
            )
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={batch_id}.zip"}
        )
        
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"批次不存在: {batch_id}"
        )


@router.get("/batch/list")
async def list_batches(limit: int = 20, offset: int = 0):
    """列出所有批次"""
    all_batches = optimized_batch_manager.list_batches()
    all_batches.sort(key=lambda b: b.created_at or "", reverse=True)
    paginated = all_batches[offset:offset + limit]
    
    return {
        "success": True,
        "total": len(all_batches),
        "batches": [
            {
                "batch_id": b.batch_id,
                "batch_name": b.batch_name,
                "status": b.status.value,
                "total_files": b.total_files,
                "created_at": b.created_at.isoformat() if b.created_at else None
            }
            for b in paginated
        ]
    }


@router.get("/batch/status")
async def batch_service_status():
    """批量转换服务状态和性能指标"""
    performance_report = optimized_batch_manager.get_performance_report()
    
    return {
        "success": True,
        "service": "batch_conversion",
        "status": "ready",
        "features": [
            "动态并发控制",
            "智能优先级队列",
            "结果缓存",
            "性能监控",
            "分批流式处理"
        ],
        "limits": {
            "max_batch_files": MAX_BATCH_FILES,
            "max_file_size_mb": MAX_FILE_SIZE_MB
        },
        "performance": performance_report
    }
