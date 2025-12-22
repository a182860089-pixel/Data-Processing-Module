"""
图片处理接口
处理图片上传、WebP压缩、图片转Word等请求
"""
import logging
import json
import uuid
import time
import base64
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from typing import Optional

from app.models.request import ImageCompressOptions, ImageToWordOptions
from app.models.response import (
    ErrorResponse, ImageCompressResponse, ImageCompressMetadata,
    ImageToWordResponse, ImageToWordMetadata
)
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


@router.post(
    "/image/to-word",
    response_model=ImageToWordResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse}
    }
)
async def image_to_word(
    file: UploadFile = File(..., description="要转换的图片文件"),
    options: Optional[str] = Form(None, description="转换选项（JSON格式）")
):
    """
    将图片转换为Word文档
    
    通过OCR识别图片内容，转换为格式化的Word文档，保持原始格式。
    
    支持的图片类型：
    - JPEG (.jpg, .jpeg)
    - PNG (.png)
    - TIFF (.tif, .tiff)
    - BMP (.bmp)
    - WebP (.webp)
    
    转换选项：
    - title: Word文档标题（可选）
    - include_markdown: 是否返回Markdown内容（默认false）
    - font_name: 默认字体（默认Microsoft YaHei）
    - font_size: 默认字号（默认11）
    """
    settings = get_settings()
    file_service = FileService()
    start_time = time.time()
    
    try:
        # 1. 验证文件
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空"
            )
        
        # 检查文件类型
        allowed_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {file_ext}，支持: {', '.join(allowed_extensions)}"
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
        convert_options = ImageToWordOptions()
        if options:
            try:
                options_dict = json.loads(options)
                convert_options = ImageToWordOptions(**options_dict)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"选项格式错误: {str(e)}"
                )
        
        # 3. 生成任务ID并保存上传文件
        task_id = f"i2w_{uuid.uuid4().hex[:12]}"
        input_path = Path(await file_service.save_upload_file(file, task_id))
        
        # 4. 准备输出路径
        output_filename = Path(file.filename).stem + ".docx"
        output_path = Path(settings.output_dir) / f"{task_id}_{output_filename}"
        
        # 5. 初始化OCR客户端
        try:
            from app.services.external.deepseek_client import DeepSeekClient
            ocr_client = DeepSeekClient()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "OCR服务不可用",
                    "details": str(e)
                }
            )
        
        # 6. 初始化Word转换器
        try:
            from app.core.converters.image.word_formatter import WordFormatter
            word_formatter = WordFormatter()
            
            # 设置自定义字体
            if convert_options.font_name:
                word_formatter.default_font_name = convert_options.font_name
            if convert_options.font_size:
                from docx.shared import Pt
                word_formatter.default_font_size = Pt(convert_options.font_size)
        except ImportError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Word转换服务不可用，缺python-docx库",
                    "details": str(e)
                }
            )
        
        # 7. 读取图片并转为Base64
        with open(input_path, 'rb') as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # 8. 调用OCR获取Markdown
        logger.info(f"Starting OCR for task: {task_id}")
        markdown_content = await ocr_client.ocr_image(image_base64)
        logger.info(f"OCR completed, markdown length: {len(markdown_content)}")
        
        # 9. 将Markdown转换为Word
        word_formatter.markdown_to_docx(
            markdown_content,
            str(output_path),
            title=convert_options.title
        )
        
        # 10. 获取输出文件大小
        output_size = output_path.stat().st_size
        processing_time = time.time() - start_time
        
        # 11. 构建响应
        response = ImageToWordResponse(
            success=True,
            message="图片转Word完成",
            task_id=task_id,
            filename=file.filename,
            output_filename=output_filename,
            download_url=f"/api/v1/image/word/download/{task_id}",
            markdown_content=markdown_content if convert_options.include_markdown else None,
            metadata=ImageToWordMetadata(
                original_size=file_size,
                output_size=output_size,
                markdown_length=len(markdown_content),
                processing_time=round(processing_time, 2)
            )
        )
        
        logger.info(f"Image to Word conversion successful: {task_id}, time: {processing_time:.2f}s")
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
        logger.error(f"Unexpected error in image_to_word: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "details": str(e)
            }
        )


@router.get("/image/word/download/{task_id}")
async def download_word_document(task_id: str):
    """
    下载转换后的Word文档
    
    Args:
        task_id: 任务ID
        
    Returns:
        Word文档文件
    """
    settings = get_settings()
    output_dir = Path(settings.output_dir)
    
    logger.info(f"Word download request for task_id: {task_id}")
    
    # 查找匹配的文件
    matching_files = list(output_dir.glob(f"{task_id}_*.docx"))
    
    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": "文件不存在",
                "details": f"任务 {task_id} 的Word文档未找到"
            }
        )
    
    file_path = matching_files[0]
    logger.info(f"Serving Word file: {file_path}, size: {file_path.stat().st_size} bytes")
    
    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_path.name
    )
