"""
图片压缩接口
处理图片上传和WebP压缩请求
"""
import logging
import json
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Optional

from app.models.request import ImageCompressOptions
from app.models.response import ErrorResponse, ImageCompressResponse, ImageCompressMetadata
from app.services.storage.file_service import FileService
from app.config import get_settings
from app.exceptions.base_exceptions import BaseAppException

# WebPCompressor将在需要时延迟导入
WEBP_AVAILABLE = True  # 默认假设可用，实际使用时才检查

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/image/compress",
    response_model=ImageCompressResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def compress_image(
    file: UploadFile = File(..., description="要压缩的图片文件"),
    options: Optional[str] = Form(None, description="压缩选项（JSON格式）")
):
    """
    压缩图片为WebP格式
    
    支持的图片类型：
    - JPEG (.jpg, .jpeg)
    - PNG (.png)
    - TIFF (.tif, .tiff)
    - BMP (.bmp)
    - WebP (.webp)
    - HEIC (.heic, .heif)
    - GIF (.gif，静态图片）
    
    压缩选项：
    - quality: WebP质量（0-100，默认90）
    - max_width: 最大宽度（默认1920）
    - max_height: 最大高度（默认1080）
    - target_size_kb: 目标文件大小（可选）
    """
    settings = get_settings()
    file_service = FileService()
    
    try:
        # 1. 验证文件
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空"
            )
        
        # 检查文件大小
        content = await file.read()
        file_size = len(content)
        await file.seek(0)
        
        max_size = settings.image_max_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大支持 {settings.image_max_size_mb}MB"
            )
        
        # 2. 解析选项
        compress_options = ImageCompressOptions()
        if options:
            try:
                options_dict = json.loads(options)
                compress_options = ImageCompressOptions(**options_dict)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"选项格式错误: {str(e)}"
                )
        
        # 3. 生成任务ID并保存上传文件
        task_id = f"img_{uuid.uuid4().hex[:12]}"
        input_path = Path(await file_service.save_upload_file(file, task_id))
        
        # 4. 准备输出路径
        output_filename = Path(file.filename).stem + ".webp"
        output_path = Path(settings.output_dir) / f"{task_id}_{output_filename}"
        
        # 5. 执行压缩
        try:
            from app.core.converters.image.webp_compressor import WebPCompressor
            compressor = WebPCompressor()
        except ImportError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "图片压缩服务不可用，libvips未安装",
                    "details": str(e)
                }
            )
        
        success, metadata = compressor.compress(
            input_path=input_path,
            output_path=output_path,
            quality=compress_options.quality,
            max_width=compress_options.max_width,
            max_height=compress_options.max_height,
            overwrite=True
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="图片压缩失败"
            )
        
        # 6. 构建响应
        response = ImageCompressResponse(
            success=True,
            message="图片压缩完成",
            filename=file.filename,
            output_filename=output_filename,
            download_url=f"/api/v1/image/download/{task_id}",
            metadata=ImageCompressMetadata(**metadata)
        )
        
        logger.info(f"Image compression successful: {task_id}")
        return response
        
    except HTTPException:
        raise
    except BaseAppException as e:
        logger.error(f"Application error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "details": str(e)
            }
        )


@router.get("/image/download/{task_id}")
async def download_compressed_image(task_id: str):
    """
    下载压缩后的图片
    
    Args:
        task_id: 任务ID
        
    Returns:
        WebP图片文件
    """
    from fastapi.responses import FileResponse
    
    settings = get_settings()
    output_dir = Path(settings.output_dir)
    
    logger.info(f"Download request for task_id: {task_id}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Output directory exists: {output_dir.exists()}")
    
    # 查找匹配的文件
    matching_files = list(output_dir.glob(f"{task_id}_*.webp"))
    
    logger.info(f"Files matching pattern '{task_id}_*.webp': {matching_files}")
    
    if not matching_files:
        # 列出目录中所有文件以供调试
        all_files = list(output_dir.glob("*"))
        logger.warning(f"No matching files found for task {task_id}. Files in output_dir: {all_files}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": "文件不存在",
                "details": f"任务 {task_id} 的结果文件未找到。输出目录: {output_dir}，文件数: {len(all_files)}"
            }
        )
    
    file_path = matching_files[0]
    logger.info(f"Serving file: {file_path}, size: {file_path.stat().st_size} bytes")
    
    return FileResponse(
        path=str(file_path),
        media_type="image/webp",
        filename=file_path.name
    )


@router.get("/image/status")
async def image_service_status():
    """
    图片压缩服务状态
    
    Returns:
        服务状态信息
    """
    # 尝试导入检查libvips是否可用
    try:
        from app.core.converters.image.webp_compressor import WebPCompressor
        # 尝试初始化
        WebPCompressor()
        return {
            "success": True,
            "service": "image_compression",
            "status": "operational",
            "message": "图片压缩服务已启用（阶段2）",
            "supported_formats": ["jpg", "jpeg", "png", "tiff", "bmp", "webp", "heic", "gif"],
            "libvips_available": True
        }
    except ImportError as e:
        return {
            "success": False,
            "service": "image_compression",
            "status": "unavailable",
            "message": "图片压缩服务不可用，缺libvips库",
            "libvips_available": False,
            "error": str(e),
            "install_instruction": "Please install libvips: https://www.libvips.org/install.html"
        }
