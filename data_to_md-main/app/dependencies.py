"""
依赖注入模块
提供全局依赖供路由使用
"""
from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import get_settings, Settings


async def get_api_key(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """
    验证API Key（如果需要）
    
    Args:
        authorization: Authorization header
        
    Returns:
        API key if valid
        
    Raises:
        HTTPException: If API key is required but invalid
    """
    settings = get_settings()
    
    if not settings.api_key_required:
        return None
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    # 提取Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    api_key = authorization[7:]  # 移除 "Bearer " 前缀
    
    # TODO: 验证API key（从数据库或配置中）
    # 这里简化处理，实际应该查询数据库
    
    return api_key


def get_config() -> Settings:
    """
    获取配置实例
    
    Returns:
        Settings instance
    """
    return get_settings()

