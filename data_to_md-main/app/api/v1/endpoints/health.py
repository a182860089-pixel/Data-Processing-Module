"""
健康检查接口
"""
import logging
from datetime import datetime
from fastapi import APIRouter
from app.models.response import HealthResponse
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查
    
    返回服务状态、版本信息等
    """
    settings = get_settings()
    
    # 检查各个服务状态
    services_status = {
        "api": "up",
        "deepseek_ocr": "up",  # TODO: 实际检查API连接
        "storage": "up"
    }
    
    # 构建响应
    response = HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version=settings.app_version,
        services=services_status,
        metrics={
            "uptime_seconds": 0,  # TODO: 实现实际的运行时间统计
            "total_requests": 0,  # TODO: 实现请求计数
            "active_tasks": 0,    # TODO: 从TaskManager获取
            "queue_size": 0
        }
    )
    
    return response

