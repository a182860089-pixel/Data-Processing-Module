"""
MinerU OCR API 客户端

注意：具体的 URL 路径和请求/响应字段需要根据 MinerU 官方文档进行调整，
本实现提供的是一个通用的封装骨架，方便后续接入。
"""
import logging
import os
from typing import Optional

import httpx

from app.config import get_settings
from app.exceptions.service_exceptions import MinerUAPIException
from app.services.external.base_ocr_client import BaseOCRClient

logger = logging.getLogger(__name__)


class MinerUClient(BaseOCRClient):
    """MinerU OCR API 客户端，实现统一 OCR 接口。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key: str = settings.mineru_api_key
        self.base_url: str = (settings.mineru_base_url or "").rstrip("/")
        self.timeout: int = settings.mineru_timeout

        if not self.api_key or not self.base_url:
            # 不直接抛异常，延迟到真正调用时再报错，避免影响未使用 MinerU 的场景
            logger.warning(
                "MinerUClient initialized without proper configuration: "
                "MINERU_API_KEY or MINERU_BASE_URL is empty."
            )

    async def ocr_image(self, base64_image: str) -> str:
        """对单张 Base64 图片调用 MinerU OCR。"""
        if not self.api_key or not self.base_url:
            raise MinerUAPIException(
                message="MinerU 未正确配置",
                details="请设置 MINERU_API_KEY 和 MINERU_BASE_URL 环境变量"
            )

        url = f"{self.base_url}/ocr/image"  # TODO: 根据 MinerU 文档调整实际路径
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "image_base64": base64_image,
            # 根据 MinerU 接口要求添加其他字段，例如：
            # "output_format": "markdown",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except Exception as e:
            logger.error(f"MinerU image OCR request failed: {str(e)}")
            raise MinerUAPIException(
                message="MinerU OCR 调用异常",
                details=str(e),
            )

        if resp.status_code != 200:
            logger.error(
                "MinerU image OCR failed: status=%s, body=%s",
                resp.status_code,
                resp.text,
            )
            raise MinerUAPIException(
                message="MinerU OCR 调用失败",
                details=f"HTTP {resp.status_code}: {resp.text}",
            )

        try:
            data = resp.json()
        except Exception as e:
            raise MinerUAPIException(
                message="MinerU 响应解析失败",
                details=f"{e}: {resp.text}",
            )

        # 这里假设 MinerU 返回字段中包含 markdown 或 text 字段
        markdown = data.get("markdown") or data.get("text")
        if not isinstance(markdown, str):
            raise MinerUAPIException(
                message="MinerU 响应格式不符合预期",
                details=str(data),
            )

        return markdown

    async def ocr_pdf(self, file_path: str) -> str:
        """直接对 PDF 文件调用 MinerU OCR（若其提供整 PDF 接口）。"""
        if not self.api_key or not self.base_url:
            raise MinerUAPIException(
                message="MinerU 未正确配置",
                details="请设置 MINERU_API_KEY 和 MINERU_BASE_URL 环境变量"
            )

        if not os.path.exists(file_path):
            raise MinerUAPIException(
                message="PDF 文件不存在",
                details=file_path,
            )

        url = f"{self.base_url}/ocr/pdf"  # TODO: 根据 MinerU 文档调整实际路径
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(file_path, "rb") as f:
                    files = {"file": (os.path.basename(file_path), f, "application/pdf")}
                    resp = await client.post(url, files=files, headers=headers)
        except Exception as e:
            logger.error(f"MinerU PDF OCR request failed: {str(e)}")
            raise MinerUAPIException(
                message="MinerU PDF OCR 调用异常",
                details=str(e),
            )

        if resp.status_code != 200:
            logger.error(
                "MinerU PDF OCR failed: status=%s, body=%s",
                resp.status_code,
                resp.text,
            )
            raise MinerUAPIException(
                message="MinerU PDF OCR 调用失败",
                details=f"HTTP {resp.status_code}: {resp.text}",
            )

        try:
            data = resp.json()
        except Exception as e:
            raise MinerUAPIException(
                message="MinerU PDF 响应解析失败",
                details=f"{e}: {resp.text}",
            )

        markdown = data.get("markdown") or data.get("text")
        if not isinstance(markdown, str):
            raise MinerUAPIException(
                message="MinerU PDF 响应格式不符合预期",
                details=str(data),
            )

        return markdown