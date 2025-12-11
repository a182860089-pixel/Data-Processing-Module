"""
统一 OCR 引擎接口定义

提供基础的异步 OCR 能力抽象，支持按图片或按 PDF 调用。
"""
from abc import ABC, abstractmethod


class BaseOCRClient(ABC):
    """统一 OCR 引擎接口基类。"""

    @abstractmethod
    async def ocr_image(self, base64_image: str) -> str:
        """对单张 Base64 编码图像执行 OCR。"""
        raise NotImplementedError

    async def ocr_pdf(self, file_path: str) -> str:
        """对本地 PDF 文件执行 OCR（可选）。"""
        raise NotImplementedError("ocr_pdf is not implemented for this OCR client")
