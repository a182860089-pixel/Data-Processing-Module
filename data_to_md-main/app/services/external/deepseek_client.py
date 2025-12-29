"""
DeepSeek OCR API 客户端
封装 DeepSeek-OCR API 调用，支持多 API Key 轮询
"""
import re
import asyncio
import logging
import time
from typing import Optional, List
from openai import AsyncOpenAI
from app.config import get_settings
from app.exceptions.service_exceptions import DeepSeekAPIException
from app.services.external.base_ocr_client import BaseOCRClient

logger = logging.getLogger(__name__)


class MultiKeyRateLimiter:
    """多 API Key 轮询速率限制器
    
    每个 Key 独立限速，轮询选择当前可用的 Key
    """
    
    def __init__(self, api_keys: List[str], rpm_per_key: int = 60):
        """
        Args:
            api_keys: API Key 列表
            rpm_per_key: 每个 Key 每分钟最大请求数
        """
        self.api_keys = api_keys
        self.rpm_per_key = rpm_per_key
        self.min_interval = 60.0 / rpm_per_key
        
        # 每个 Key 的上次请求时间
        self.last_request_times = {key: 0.0 for key in api_keys}
        self._lock = asyncio.Lock()
        self._current_index = 0
        
        logger.info(f"MultiKeyRateLimiter initialized: {len(api_keys)} keys, {rpm_per_key} RPM each")
    
    async def acquire(self) -> str:
        """获取一个可用的 API Key，必要时等待
        
        Returns:
            str: 可用的 API Key
        """
        async with self._lock:
            now = time.time()
            
            # 尝试找到一个已经冷却的 Key
            for _ in range(len(self.api_keys)):
                key = self.api_keys[self._current_index]
                elapsed = now - self.last_request_times[key]
                
                if elapsed >= self.min_interval:
                    # 这个 Key 可用
                    self.last_request_times[key] = now
                    self._current_index = (self._current_index + 1) % len(self.api_keys)
                    return key
                
                # 试下一个 Key
                self._current_index = (self._current_index + 1) % len(self.api_keys)
            
            # 所有 Key 都在冷却中，等待最快可用的
            min_wait = float('inf')
            best_key = self.api_keys[0]
            
            for key in self.api_keys:
                elapsed = now - self.last_request_times[key]
                wait_needed = self.min_interval - elapsed
                if wait_needed < min_wait:
                    min_wait = wait_needed
                    best_key = key
            
            if min_wait > 0:
                logger.debug(f"All keys cooling, waiting {min_wait:.2f}s")
                await asyncio.sleep(min_wait)
            
            self.last_request_times[best_key] = time.time()
            return best_key


# 全局多 Key 限制器
_multi_key_limiter: Optional[MultiKeyRateLimiter] = None


def get_multi_key_limiter() -> MultiKeyRateLimiter:
    """Get or create global multi-key rate limiter"""
    global _multi_key_limiter
    if _multi_key_limiter is None:
        settings = get_settings()
        
        # 收集所有 API Keys
        api_keys = []
        
        # 从 DEEPSEEK_API_KEYS 获取（逗号分隔）
        if settings.deepseek_api_keys:
            keys = [k.strip() for k in settings.deepseek_api_keys.split(',') if k.strip()]
            api_keys.extend(keys)
        
        # 如果没有多 Key，使用单个 Key
        if not api_keys and settings.deepseek_api_key:
            api_keys.append(settings.deepseek_api_key)
        
        if not api_keys:
            raise ValueError("No DeepSeek API keys configured")
        
        rpm = getattr(settings, 'deepseek_rpm_limit', 60)
        _multi_key_limiter = MultiKeyRateLimiter(api_keys, rpm_per_key=rpm)
        
        logger.info(f"Multi-key limiter ready: {len(api_keys)} keys, total capacity {len(api_keys) * rpm} RPM")
    
    return _multi_key_limiter


class DeepSeekClient(BaseOCRClient):
    """DeepSeek OCR API 客户端，支持多 API Key 轮询"""
    
    def __init__(self):
        """初始化客户端"""
        settings = get_settings()
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model
        self.max_tokens = settings.deepseek_max_tokens
        self.timeout = settings.deepseek_timeout
        
        # 缓存不同 API Key 的客户端
        self._clients: dict[str, AsyncOpenAI] = {}
    
    def _get_client(self, api_key: str) -> AsyncOpenAI:
        """获取或创建指定 API Key 的客户端"""
        if api_key not in self._clients:
            self._clients[api_key] = AsyncOpenAI(
                base_url=self.base_url,
                api_key=api_key,
            )
        return self._clients[api_key]
    
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
            # 获取可用的 API Key（带速率限制）
            api_key = await get_multi_key_limiter().acquire()
            client = self._get_client(api_key)
            
            # 构建请求
            request_data = self._build_request(image_base64, prompt)
            
            # 调用API（带重试）
            response = await self._retry_with_backoff(
                lambda: client.chat.completions.create(**request_data)
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
        coro_func,
        max_retries: int = 5,
        initial_delay: float = 2.0
    ):
        """
        带指数退避的异步重试机制，特别处理限流错误
        
        Args:
            coro_func: 返回协程的函数
            max_retries: 最大重试次数
            initial_delay: 初始延迟（秒）
            
        Returns:
            函数执行结果
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await coro_func()
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # 检查是否是限流错误 (429/403)
                is_rate_limit = '429' in error_str or '403' in error_str or 'rate' in error_str or 'forbidden' in error_str
                
                if attempt < max_retries:
                    # 限流错误使用更长的延迟
                    if is_rate_limit:
                        wait_time = delay * 2  # 限流时等待更长
                        logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries + 1}), "
                            f"waiting {wait_time}s before retry: {str(e)}"
                        )
                    else:
                        wait_time = delay
                        logger.warning(
                            f"API call failed (attempt {attempt + 1}/{max_retries + 1}), "
                            f"retrying in {wait_time}s: {str(e)}"
                        )
                    
                    await asyncio.sleep(wait_time)
                    delay = min(delay * 2, 30)  # 指数退避，最大 30 秒
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

