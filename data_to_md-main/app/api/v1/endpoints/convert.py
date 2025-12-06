"""
转换接口
处理文件上传和转换请求
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Optional
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
    转换文件为Markdown
    
    支持的文件类型：
    - PDF (.pdf)
    
    转换选项：
    - dpi: 图像渲染DPI（72-300，默认144）
    - include_metadata: 是否包含元数据（默认true）
    - max_pages: 最大处理页数（默认100）
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
        
        max_size = settings.pdf_max_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大支持 {settings.pdf_max_size_mb}MB"
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
        response = ConvertSyncResponse(
            success=True,
            task_id=result['task_id'],
            message="文件转换完成",
            filename=file.filename,
            file_type=result['metadata'].get('file_type', 'unknown'),
            markdown_content=result['markdown_content'],
            download_url=f"/api/v1/download/{result['task_id']}",
            metadata={
                'pages_processed': result['metadata'].get('total_pages', 0),
                'ocr_pages': result['metadata'].get('ocr_pages', 0),
                'text_pages': result['metadata'].get('text_pages', 0),
                'processing_time': result['metadata'].get('processing_time', 0),
                'file_size': result['metadata'].get('output_file_size', 0)
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

