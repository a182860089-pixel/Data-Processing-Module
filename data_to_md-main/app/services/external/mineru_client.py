"""
MinerU OCR API 客户端
根据官方文档实现：https://opendatalab.github.io/MinerU/

关键特性：
- 异步任务模式：创建任务 → 轮询状态 → 获取结果
- 支持 PDF URL 解析
- 支持本地文件上传解析
- 返回结果为 ZIP 包（包含 markdown、json 等文件）
"""
import asyncio
import logging
import os
import time
import zipfile
from io import BytesIO
from typing import Optional
from urllib.parse import urljoin

import httpx

from app.config import get_settings
from app.exceptions.service_exceptions import MinerUAPIException
from app.services.external.base_ocr_client import BaseOCRClient

logger = logging.getLogger(__name__)

# MinerU 官方 API 基础 URL（注意：不带尾随斜杠也可，由 _build_url 统一处理）
MINERU_API_BASE = "https://mineru.net/api/v4"
# 端点路径不要以斜杠开头，避免 urljoin 覆盖掉 base 的路径段
MINERU_CREATE_TASK = "extract/task"
MINERU_GET_TASK = "extract/task/{task_id}"
MINERU_FILE_UPLOAD = "file-urls/batch"
MINERU_BATCH_RESULTS = "extract-results/batch/{batch_id}"


class MinerUClient(BaseOCRClient):
    """MinerU OCR API 客户端，实现统一 OCR 接口。
    
    支持两种工作流：
    1. URL 解析：直接传入 PDF 的公网 URL
    2. 本地文件上传：上传本地 PDF 文件
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key: str = settings.mineru_api_key
        self.base_url: str = settings.mineru_base_url or MINERU_API_BASE
        self.timeout: int = settings.mineru_timeout
        self.poll_interval: float = 2.0  # 轮询间隔（秒）
        self.max_polls: int = 300  # 最多轮询 300 次 = 10 分钟

        if not self.api_key:
            logger.warning(
                "MinerUClient initialized without MINERU_API_KEY. "
                "MinerU calls will fail."
            )

    def _get_headers(self) -> dict:
        """获取请求头（包含鉴权）"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_url(self, path: str) -> str:
        """安全拼接 base_url 和相对路径，避免 urljoin 覆盖 base 的路径段"""
        base = (self.base_url or "").rstrip("/")
        rel = (path or "").lstrip("/")
        return f"{base}/{rel}"

    async def ocr_image(self, base64_image: str) -> str:
        """MinerU 主要是 PDF 处理，不支持单张图片。此方法抛出异常。"""
        raise MinerUAPIException(
            message="MinerU 不支持单张图片 OCR",
            details="MinerU 主要用于 PDF 文档解析。请使用 ocr_pdf 方法。"
        )

    async def ocr_pdf(self, file_path: str) -> str:
        """对本地 PDF 文件执行 MinerU 解析。
        
        流程：
        1. 申请文件上传链接
        2. 上传 PDF 文件
        3. 轮询任务状态直到完成
        4. 下载结果 ZIP，提取 markdown
        """
        if not self.api_key:
            raise MinerUAPIException(
                message="MinerU 未正确配置",
                details="请设置 MINERU_API_KEY 环境变量"
            )

        if not os.path.exists(file_path):
            raise MinerUAPIException(
                message="PDF 文件不存在",
                details=file_path,
            )

        try:
            # 第 1 步：申请上传链接
            batch_id, upload_url = await self._request_upload_url(file_path)
            logger.info(f"Got upload URL, batch_id={batch_id}")

            # 第 2 步：上传文件
            await self._upload_file(upload_url, file_path)
            logger.info(f"File uploaded successfully")

            # 第 3 步：轮询任务状态
            markdown = await self._poll_and_get_result(batch_id)
            logger.info(f"MinerU processing completed")

            return markdown

        except MinerUAPIException:
            raise
        except Exception as e:
            logger.error(f"MinerU PDF processing failed: {str(e)}")
            raise MinerUAPIException(
                message="MinerU PDF 处理失败",
                details=str(e),
            )

    async def _request_upload_url(self, file_path: str) -> tuple[str, str]:
        """申请文件上传链接。返回 (batch_id, upload_url)"""
        url = self._build_url(MINERU_FILE_UPLOAD)
        headers = self._get_headers()
        payload = {
            "files": [
                {"name": os.path.basename(file_path), "data_id": "auto_upload"}
            ],
            "model_version": "vlm"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except Exception as e:
            logger.error(f"Request upload URL failed: {str(e)}")
            raise MinerUAPIException(
                message="申请上传链接失败",
                details=str(e),
            )

        if resp.status_code != 200:
            logger.error(
                "Request upload URL failed: status=%s, body=%s",
                resp.status_code,
                resp.text,
            )
            raise MinerUAPIException(
                message="申请上传链接失败",
                details=f"HTTP {resp.status_code}: {resp.text}",
            )

        try:
            data = resp.json()
            if data.get("code") != 0:
                raise MinerUAPIException(
                    message="申请上传链接失败",
                    details=f"Code: {data.get('code')}, Msg: {data.get('msg')}",
                )
            batch_id = data["data"]["batch_id"]
            upload_url = data["data"]["file_urls"][0]
            return batch_id, upload_url
        except KeyError as e:
            raise MinerUAPIException(
                message="申请上传链接响应格式错误",
                details=f"Missing key: {str(e)}",
            )

    async def _upload_file(self, upload_url: str, file_path: str) -> None:
        """上传文件到 MinerU 服务器。"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with open(file_path, "rb") as f:
                    # 注意：MinerU 上传时不需要设置 Content-Type
                    resp = await client.put(upload_url, content=f.read())
        except Exception as e:
            logger.error(f"Upload file failed: {str(e)}")
            raise MinerUAPIException(
                message="文件上传失败",
                details=str(e),
            )

        if resp.status_code != 200:
            logger.error(
                "Upload file failed: status=%s, body=%s",
                resp.status_code,
                resp.text,
            )
            raise MinerUAPIException(
                message="文件上传失败",
                details=f"HTTP {resp.status_code}: {resp.text}",
            )

    async def _poll_and_get_result(self, batch_id: str) -> str:
        """轮询任务状态，直到完成。返回 markdown 内容。"""
        url = self._build_url(MINERU_BATCH_RESULTS.format(batch_id=batch_id))
        headers = self._get_headers()

        poll_count = 0
        while poll_count < self.max_polls:
            await asyncio.sleep(self.poll_interval)
            poll_count += 1

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, headers=headers)
            except Exception as e:
                logger.warning(f"Poll task status failed: {str(e)}, retrying...")
                continue

            if resp.status_code != 200:
                logger.warning(
                    f"Poll task status failed: HTTP {resp.status_code}, retrying..."
                )
                continue

            try:
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning(
                        f"Poll task failed: Code {data.get('code')}, retrying..."
                    )
                    continue

                # 检查状态
                result = data["data"]["extract_result"][0]
                state = result.get("state")
                err_msg = result.get("err_msg", "")

                if state == "done":
                    # 任务完成，下载结果
                    zip_url = result.get("full_zip_url")
                    if not zip_url:
                        raise MinerUAPIException(
                            message="任务完成但无结果 URL",
                            details="Missing full_zip_url in response",
                        )
                    markdown = await self._download_and_extract_markdown(zip_url)
                    logger.info("Task completed successfully")
                    return markdown

                elif state == "failed":
                    raise MinerUAPIException(
                        message="MinerU 任务失败",
                        details=f"Error: {err_msg}",
                    )

                elif state in ["pending", "running", "converting", "waiting-file"]:
                    # 继续等待
                    progress = result.get("extract_progress", {})
                    extracted = progress.get("extracted_pages", 0)
                    total = progress.get("total_pages", 0)
                    logger.info(
                        f"Task running: {state}, progress {extracted}/{total}"
                    )
                    continue
                else:
                    logger.warning(f"Unknown state: {state}, retrying...")
                    continue

            except KeyError as e:
                logger.warning(f"Parse response failed: {str(e)}, retrying...")
                continue

        raise MinerUAPIException(
            message="MinerU 任务超时",
            details=f"Task did not complete within {self.max_polls * self.poll_interval} seconds",
        )

    async def _download_and_extract_markdown(self, zip_url: str) -> str:
        """下载结果 ZIP 文件，提取 markdown 内容。"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(zip_url)
        except Exception as e:
            logger.error(f"Download result ZIP failed: {str(e)}")
            raise MinerUAPIException(
                message="下载结果失败",
                details=str(e),
            )

        if resp.status_code != 200:
            logger.error(
                "Download result ZIP failed: status=%s",
                resp.status_code,
            )
            raise MinerUAPIException(
                message="下载结果失败",
                details=f"HTTP {resp.status_code}",
            )

        try:
            # 解析 ZIP
            with zipfile.ZipFile(BytesIO(resp.content)) as z:
                # 查找 markdown 文件（通常叫 document.md）
                md_files = [f for f in z.namelist() if f.endswith(".md")]
                if not md_files:
                    raise MinerUAPIException(
                        message="结果 ZIP 中未找到 markdown 文件",
                        details=f"Files in ZIP: {z.namelist()}",
                    )
                # 取第一个 markdown 文件
                with z.open(md_files[0]) as f:
                    markdown = f.read().decode("utf-8")
                    return markdown
        except zipfile.BadZipFile as e:
            logger.error(f"Parse result ZIP failed: {str(e)}")
            raise MinerUAPIException(
                message="解析结果 ZIP 失败",
                details=str(e),
            )
        except Exception as e:
            logger.error(f"Extract markdown from ZIP failed: {str(e)}")
            raise MinerUAPIException(
                message="提取 markdown 失败",
                details=str(e),
            )
