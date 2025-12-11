"""
配置管理模块
加载环境变量并提供配置类
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用配置
    app_name: str = Field(default="PDF-to-Markdown-API", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=4, env="WORKERS")
    
    # DeepSeek API配置
    deepseek_api_key: str = Field(
        default="",
        env="DEEPSEEK_API_KEY"
    )
    deepseek_base_url: str = Field(
        default="https://api.siliconflow.cn",
        env="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(
        default="deepseek-ai/DeepSeek-OCR",
        env="DEEPSEEK_MODEL"
    )
    deepseek_max_tokens: int = Field(default=4096, env="DEEPSEEK_MAX_TOKENS")
    deepseek_timeout: int = Field(default=60, env="DEEPSEEK_TIMEOUT")

    # MinerU API配置（占位，需根据实际部署填写环境变量）
    mineru_api_key: str = Field(
        default="",
        env="MINERU_API_KEY"
    )
    mineru_base_url: str = Field(
        default="",
        env="MINERU_BASE_URL"
    )
    mineru_timeout: int = Field(default=60, env="MINERU_TIMEOUT")
    
    # PDF处理配置
    pdf_max_size_mb: int = Field(default=500, env="PDF_MAX_SIZE_MB")
    pdf_max_pages: int = Field(default=100, env="PDF_MAX_PAGES")
    pdf_render_dpi: int = Field(default=144, env="PDF_RENDER_DPI")
    pdf_text_threshold: int = Field(default=10, env="PDF_TEXT_THRESHOLD")
    
    # 并发配置
    max_concurrent_tasks: int = Field(default=5, env="MAX_CONCURRENT_TASKS")
    max_concurrent_api_calls: int = Field(default=3, env="MAX_CONCURRENT_API_CALLS")
    
    # 存储配置
    upload_dir: str = Field(default="./storage/uploads", env="UPLOAD_DIR")
    output_dir: str = Field(default="./storage/outputs", env="OUTPUT_DIR")
    log_dir: str = Field(default="./storage/logs", env="LOG_DIR")
    cache_dir: str = Field(default="./storage/cache", env="CACHE_DIR")
    file_retention_days: int = Field(default=7, env="FILE_RETENTION_DAYS")
    
    # 图片压缩配置
    image_max_size_mb: int = Field(default=20, env="IMAGE_MAX_SIZE_MB")
    image_default_quality: int = Field(default=90, env="IMAGE_DEFAULT_QUALITY")
    image_max_width: int = Field(default=1920, env="IMAGE_MAX_WIDTH")
    image_max_height: int = Field(default=1080, env="IMAGE_MAX_HEIGHT")
    
    # Office 文档转 PDF 配置
    office_conversion_method: str = Field(default="python", env="OFFICE_CONVERSION_METHOD")  # python or libreoffice
    office_conversion_timeout: int = Field(default=60, env="OFFICE_CONVERSION_TIMEOUT")
    office_max_size_mb: int = Field(default=100, env="OFFICE_MAX_SIZE_MB")
    
    # 图片转 PDF配置
    image_to_pdf_page_size: str = Field(default="A4", env="IMAGE_TO_PDF_PAGE_SIZE")
    image_to_pdf_fit_mode: str = Field(default="fit", env="IMAGE_TO_PDF_FIT_MODE")
    image_to_pdf_max_size_mb: int = Field(default=50, env="IMAGE_TO_PDF_MAX_SIZE_MB")
    
    # 视频转探 配置
    video_max_size_mb: int = Field(default=500, env="VIDEO_MAX_SIZE_MB")
    video_keyframe_interval: int = Field(default=5, env="VIDEO_KEYFRAME_INTERVAL")
    video_max_frames: int = Field(default=100, env="VIDEO_MAX_FRAMES")
    video_frame_quality: int = Field(default=85, env="VIDEO_FRAME_QUALITY")
    video_extract_frames: bool = Field(default=True, env="VIDEO_EXTRACT_FRAMES")
    
    # 安全配置
    api_key_required: bool = Field(default=False, env="API_KEY_REQUIRED")
    allowed_origins: str = Field(default="*", env="ALLOWED_ORIGINS")
    max_request_size_mb: int = Field(default=500, env="MAX_REQUEST_SIZE_MB")
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_rotation: str = Field(default="1 day", env="LOG_ROTATION")
    log_retention: str = Field(default="30 days", env="LOG_RETENTION")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("upload_dir", "output_dir", "log_dir", "cache_dir")
    def create_directories(cls, v):
        """确保目录存在"""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    
    @validator("pdf_render_dpi")
    def validate_dpi(cls, v):
        """验证DPI范围"""
        if not 72 <= v <= 300:
            raise ValueError("DPI must be between 72 and 300")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    def get_upload_path(self, filename: str) -> Path:
        """获取上传文件路径"""
        return Path(self.upload_dir) / filename
    
    def get_output_path(self, filename: str) -> Path:
        """获取输出文件路径"""
        return Path(self.output_dir) / filename
    
    def get_log_path(self, filename: str) -> Path:
        """获取日志文件路径"""
        return Path(self.log_dir) / filename


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例（用于依赖注入）"""
    return settings

