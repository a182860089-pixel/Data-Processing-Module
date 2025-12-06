"""
FastAPI 主应用
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.endpoints import convert, health, status, image, batch
from app.config import get_settings
from app.exceptions.base_exceptions import BaseAppException

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时执行
    logger.info("Application starting up...")
    settings = get_settings()
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"DeepSeek API: {settings.deepseek_base_url}")
    
    yield
    
    # 关闭时执行
    logger.info("Application shutting down...")


# 创建 FastAPI 应用
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="PDF to Markdown Intelligent Conversion System",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    """处理应用自定义异常"""
    logger.error(f"Application error: {exc.message}")
    return JSONResponse(
        status_code=500,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "details": str(exc)
        }
    )


# 注册路由
app.include_router(
    convert.router,
    prefix="/api/v1",
    tags=["conversion"]
)

app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["health"]
)

app.include_router(
    status.router,
    prefix="/api/v1",
    tags=["status"]
)

app.include_router(
    image.router,
    prefix="/api/v1",
    tags=["image"]
)

app.include_router(
    batch.router,
    prefix="/api/v1",
    tags=["batch"]
)


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

