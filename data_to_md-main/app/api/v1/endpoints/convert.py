"""
转换接口
处理文件上传和转换请求
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Optional, List
import json
from app.models.request import ConvertOptions
from app.models.response import ConvertResponse, ConvertSyncResponse, ErrorResponse
from app.services.conversion.conversion_service import ConversionService
from app.services.storage.file_service import FileService
from app.config import get_settings
from app.exceptions.base_exceptions import BaseAppException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/convert",
    response_model=ConvertSyncResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def convert_file(
    file: UploadFile = File(..., description="要转换的文件"),
    options: Optional[str] = Form(None, description="转换选项（JSON格式）")
):
    """
    转换文件
    
    支持的文件类型（最大500MB）：
    - PDF (.pdf) -> Markdown
    - Office (.docx, .pptx, .xlsx, etc.) -> PDF
    - 图片 (.jpg, .png, .gif, .webp, etc.) -> PDF
    - 视频 (.mp4, .avi, .mov, .wmv, .mkv, .flv) -> Markdown 或 PDF
    
    转换选项（JSON格式）：
    - output_type: 'markdown' 或 'pdf'
    - keyframe_interval: 关键帧提取间隔（秒）
    - max_frames: 最大帧数
    - frame_quality: 帧质量 (1-100)
    - include_metadata: 是否包含元数据
    - include_frames: 是否包含关键帧
    """
    settings = get_settings()
    conversion_service = ConversionService()
    file_service = FileService()
    
    try:
        # 1. 验证文件
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空"
            )
        
        # 检查文件大小
        file_size = 0
        content = await file.read()
        file_size = len(content)
        await file.seek(0)  # 重置文件指针
        
        # 使用 max_request_size_mb 作为文件大小限制（500MB）
        max_size = settings.max_request_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大支持 {settings.max_request_size_mb}MB"
            )
        
        # 2. 解析选项
        convert_options = ConvertOptions()
        if options:
            try:
                options_dict = json.loads(options)
                convert_options = ConvertOptions(**options_dict)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"选项格式错误: {str(e)}"
                )
        
        # 3. 生成临时任务ID用于保存文件
        import uuid
        temp_task_id = f"temp_{uuid.uuid4().hex[:12]}"
        
        # 4. 保存上传的文件
        file_path = await file_service.save_upload_file(file, temp_task_id)
        
        # 5. 执行转换（同步模式）
        result = await conversion_service.convert(
            file_path=file_path,
            filename=file.filename,
            options=convert_options.model_dump()
        )
        
        # 6. 构建响应
        markdown_content = result.get('markdown_content', '') or ''
        output_type = result.get('output_type', 'markdown')
        
        logger.info(f"Conversion result - output_type: {output_type}, markdown_length: {len(markdown_content)}")
        logger.info(f"Result keys: {result.keys()}")
        
        response = ConvertSyncResponse(
            success=True,
            task_id=result['task_id'],
            message="文件转换完成",
            filename=file.filename,
            file_type=output_type,
            markdown_content=markdown_content,
            download_url=f"/api/v1/download/{result['task_id']}",
            metadata={
                'pages_processed': result['metadata'].get('total_pages', 0),
                'ocr_pages': result['metadata'].get('ocr_pages', 0),
                'text_pages': result['metadata'].get('text_pages', 0),
                'processing_time': result['metadata'].get('processing_time', 0),
                'file_size': result['metadata'].get('output_file_size', 0),
                'output_type': output_type,
                'frames_extracted': result['metadata'].get('frames_extracted', 0),
                'duration': result['metadata'].get('duration', 0),
            }
        )
        
        logger.info(f"Conversion successful: {result['task_id']}")
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


@router.post(
    "/convert/images",
    response_model=ConvertSyncResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def convert_images_to_pdf(
    files: List[UploadFile] = File(..., description="要转换的图片文件列表"),
    options: Optional[str] = Form(None, description="转换选项（JSON格式）")
):
    """
    将多张图片转换为多页 PDF
    
    支持的图片类型（最大500MB）：
    - 图片 (.jpg, .jpeg, .png, .gif, .webp, .tiff, .bmp, .heic, etc.)
    
    转换选项（JSON格式）：
    - page_size: 页面大小 ('A4', 'A3', 'A5', 'letter')
    - fit_mode: 缩放模式 ('fit', 'contain', 'cover', 'stretch')
    """
    settings = get_settings()
    conversion_service = ConversionService()
    file_service = FileService()
    
    try:
        # 1. 验证文件
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要选择一张图片"
            )
        
        # 2. 保存所有文件并获取路径
        import uuid
        temp_task_id = f"temp_{uuid.uuid4().hex[:12]}"
        file_paths = []
        total_size = 0
        
        for idx, file in enumerate(files):
            if not file.filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"第{idx + 1}个文件名不能为空"
                )
            
            # 检查文件大小
            content = await file.read()
            file_size = len(content)
            total_size += file_size
            await file.seek(0)
            
            # 单个文件大小限制
            max_size = settings.max_request_size_mb * 1024 * 1024
            if file_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"第{idx + 1}个文件过大，最大支持 {settings.max_request_size_mb}MB"
                )
            
            # 保存文件
            file_path = await file_service.save_upload_file(file, f"{temp_task_id}_{idx}")
            file_paths.append(file_path)
        
        # 总文件大小不超过 5GB
        if total_size > 5 * 1024 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="上传文件总大小过大，请分批上传"
            )
        
        # 3. 解析选项
        convert_options = ConvertOptions()
        if options:
            try:
                options_dict = json.loads(options)
                convert_options = ConvertOptions(**options_dict)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"选项格式错误: {str(e)}"
                )
        
        # 4. 将文件路径添加到选项中
        options_dict = convert_options.model_dump()
        options_dict['file_paths'] = file_paths
        
        # 5. 执行转换（使用第一个文件作为主文件，其余通过 options 传递）
        result = await conversion_service.convert(
            file_path=file_paths[0],
            filename=f"{len(files)}_images.pdf",
            options=options_dict
        )
        
        # 6. 构建响应
        markdown_content = result.get('markdown_content', '') or ''
        output_type = result.get('output_type', 'pdf')
        
        response = ConvertSyncResponse(
            success=True,
            task_id=result['task_id'],
            message=f"成功将{len(files)}张图片转换为PDF",
            filename=f"{len(files)}_images.pdf",
            file_type=output_type,
            markdown_content=markdown_content,
            download_url=f"/api/v1/download/{result['task_id']}",
            metadata={
                'image_count': len(files),
                'pages_processed': len(file_paths),
                'processing_time': result['metadata'].get('processing_time', 0),
                'file_size': result['metadata'].get('output_file_size', 0),
                'output_type': output_type,
            }
        )
        
        logger.info(f"Multi-image conversion successful: {result['task_id']} ({len(files)} images)")
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

