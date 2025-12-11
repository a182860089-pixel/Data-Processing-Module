"""
DeepSeek OCR API 客户端
封装 DeepSeek-OCR API 调用
"""
import re
import time
import logging
from typing import Optional
from openai import OpenAI
from app.config import get_settings
from app.exceptions.service_exceptions import DeepSeekAPIException
from app.services.external.base_ocr_client import BaseOCRClient

logger = logging.getLogger(__name__)


class DeepSeekClient(BaseOCRClient):
    """DeepSeek OCR API 客户端，实现统一 OCR 接口"""
    
    def __init__(self):
        """初始化客户端"""
        settings = get_settings()
        self.client = OpenAI(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
        )
        self.model = settings.deepseek_model
        self.max_tokens = settings.deepseek_max_tokens
        self.timeout = settings.deepseek_timeout
    
    async def ocr_image(
        self,
        image_base64: str,
        prompt: str = None
    ) -> str:
        """
        调用OCR API识别图像
        
        Args:
            image_base64: Base64编码的图像
            prompt: 自定义提示词
            
        Returns:
            str: Markdown格式的识别结果
            
        Raises:
            DeepSeekAPIException: API调用失败
        """
        if prompt is None:
            prompt = "<|grounding|>Convert the document to markdown."
        
        try:
            # 构建请求
            request_data = self._build_request(image_base64, prompt)
            
            # 调用API（带重试）
            response = await self._retry_with_backoff(
                lambda: self.client.chat.completions.create(**request_data)
            )
            
            # 解析响应
            markdown = self._parse_response(response)
            
            # 清理DeepSeek特有的多余符号
            cleaned_markdown = self._clean_deepseek_output(markdown)
            
            return cleaned_markdown
            
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {str(e)}")
            raise DeepSeekAPIException(
                message="OCR API调用失败",
                details=str(e)
            )
    
    def _build_request(self, image_base64: str, prompt: str) -> dict:
        """
        构建API请求体
        
        Args:
            image_base64: Base64编码的图像
            prompt: 提示词
            
        Returns:
            dict: 请求参数
        """
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "stream": False,
            "max_tokens": self.max_tokens,
            "temperature": 0.0
        }
    
    def _parse_response(self, response) -> str:
        """
        解析API响应
        
        Args:
            response: API响应对象
            
        Returns:
            str: Markdown内容
        """
        try:
            content = response.choices[0].message.content
            return content
        except (AttributeError, IndexError, KeyError) as e:
            raise DeepSeekAPIException(
                message="解析API响应失败",
                details=str(e)
            )
    
    async def _retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ):
        """
        带指数退避的重试机制
        
        Args:
            func: 要执行的函数
            max_retries: 最大重试次数
            initial_delay: 初始延迟（秒）
            
        Returns:
            函数执行结果
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay}s: {str(e)}"
                    )
                    time.sleep(delay)
                    delay *= 2  # 指数退避
                else:
                    logger.error(f"API call failed after {max_retries + 1} attempts")
        
        raise last_exception
    
    def _clean_deepseek_output(self, markdown: str) -> str:
        """
        清理DeepSeek-OCR输出中的多余符号
        
        说明：
        - DeepSeek-OCR返回的Markdown可能包含特定的多余符号
        - 这些符号是该API特有的，需要在客户端内部清理
        
        清理内容：
        - 移除 <|ref|> 和 <|det|> 标签行
        - 清理多余空行
        - 规范化空白字符
        
        Args:
            markdown: 原始Markdown内容
            
        Returns:
            str: 清理后的Markdown内容
        """
        # 按行处理，只保留不包含标签的行
        lines = markdown.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 跳过包含 <|ref|> 或 <|det|> 标签的行
            if '<|ref|>' not in line and '<|det|>' not in line:
                cleaned_lines.append(line)
        
        # 合并行并移除多余空行
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n\s*\n+', '\n\n', result)
        
        return result.strip()

