"""
OCR 引擎路由管理器
实现多引擎轮询、故障转移和熔断机制
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

from app.services.external.base_ocr_client import BaseOCRClient
from app.services.external.deepseek_client import DeepSeekClient
from app.services.external.mineru_client import MinerUClient
from app.exceptions.service_exceptions import APICallException, MinerUAPIException
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EngineStats:
    """引擎统计信息"""
    consecutive_failures: int = 0
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_failure_time: Optional[float] = None
    is_circuit_open: bool = False
    
    def reset_failures(self):
        """重置失败计数"""
        self.consecutive_failures = 0
        self.is_circuit_open = False
    
    def record_success(self):
        """记录成功调用"""
        self.total_calls += 1
        self.total_successes += 1
        self.reset_failures()
    
    def record_failure(self):
        """记录失败调用"""
        self.total_calls += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
    
    def check_circuit_breaker(self, threshold: int, timeout: int) -> bool:
        """
        检查熔断器状态
        
        Args:
            threshold: 熔断阈值（连续失败次数）
            timeout: 熔断恢复时间（秒）
            
        Returns:
            bool: True 表示熔断器打开（不可用），False 表示可用
        """
        # 如果连续失败次数未达到阈值，熔断器关闭
        if self.consecutive_failures < threshold:
            if self.is_circuit_open:
                logger.info(f"Circuit breaker recovered (failures: {self.consecutive_failures})")
                self.is_circuit_open = False
            return False
        
        # 如果达到阈值，检查是否超时恢复
        if self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= timeout:
                logger.info(f"Circuit breaker timeout expired, attempting recovery")
                self.reset_failures()
                return False
        
        # 熔断器打开
        if not self.is_circuit_open:
            logger.warning(
                f"Circuit breaker opened (failures: {self.consecutive_failures}, "
                f"threshold: {threshold})"
            )
            self.is_circuit_open = True
        
        return True
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        success_rate = (
            self.total_successes / self.total_calls * 100
            if self.total_calls > 0
            else 0.0
        )
        return {
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": round(success_rate, 2),
            "consecutive_failures": self.consecutive_failures,
            "is_circuit_open": self.is_circuit_open,
        }


class OCRRouter:
    """OCR 引擎路由管理器
    
    支持两种路由策略：
    - round_robin: 按顺序轮询引擎
    - failover: 主用引擎失败时自动切换到备用引擎
    
    支持熔断机制：
    - 连续失败 N 次后进入熔断状态
    - 熔断时间后自动恢复
    """
    
    def __init__(
        self,
        strategy: Optional[str] = None,
        circuit_breaker_threshold: Optional[int] = None,
        circuit_breaker_timeout: Optional[int] = None
    ):
        """
        初始化 OCRRouter
        
        Args:
            strategy: 路由策略 ("round_robin" 或 "failover")，None 时使用配置值
            circuit_breaker_threshold: 熔断阈值（连续失败次数），None 时使用配置值
            circuit_breaker_timeout: 熔断恢复时间（秒），None 时使用配置值
        """
        self.settings = get_settings()
        
        # 使用配置值或传入参数
        self.strategy = (strategy or self.settings.ocr_routing_strategy).lower()
        self.circuit_breaker_threshold = (
            circuit_breaker_threshold or self.settings.ocr_circuit_breaker_threshold
        )
        self.circuit_breaker_timeout = (
            circuit_breaker_timeout or self.settings.ocr_circuit_breaker_timeout
        )
        
        # 初始化引擎
        self.engines: Dict[str, BaseOCRClient] = {
            "deepseek": DeepSeekClient(),
        }
        # MinerU 逐页 OCR 默认禁用；如需实验性启用，可在配置里打开
        if self.settings.enable_mineru_page_ocr:
            self.engines["mineru"] = MinerUClient()
        
        # 引擎统计信息
        self.engine_stats: Dict[str, EngineStats] = {
            name: EngineStats() for name in self.engines.keys()
        }
        
        # 验证路由策略
        if self.strategy not in ["round_robin", "failover"]:
            logger.warning(
                f"Invalid routing strategy '{self.strategy}', falling back to 'round_robin'"
            )
            self.strategy = "round_robin"
        
        # round_robin 状态
        self._engine_names = list(self.engines.keys())
        self._current_index = 0
        self._lock = asyncio.Lock()
        
        logger.info(
            f"OCRRouter initialized with strategy='{self.strategy}', "
            f"circuit_breaker_threshold={circuit_breaker_threshold}, "
            f"circuit_breaker_timeout={circuit_breaker_timeout}, "
            f"enable_mineru_page_ocr={self.settings.enable_mineru_page_ocr}"
        )
    
    async def ocr_image(self, base64_image: str) -> Tuple[str, str]:
        """
        执行 OCR，根据策略选择引擎
        
        Args:
            base64_image: Base64 编码的图像
            
        Returns:
            Tuple[str, str]: (markdown_content, engine_used)
            
        Raises:
            APICallException: 所有引擎都失败时抛出
        """
        if self.strategy == "round_robin":
            return await self._ocr_with_round_robin(base64_image)
        else:  # failover
            return await self._ocr_with_failover(base64_image)
    
    async def _ocr_with_round_robin(self, base64_image: str) -> Tuple[str, str]:
        """使用轮询策略执行 OCR"""
        async with self._lock:
            # 选择下一个可用引擎
            engine_name = await self._select_available_engine_round_robin()
            if not engine_name:
                raise APICallException(
                    message="所有 OCR 引擎都不可用（熔断或错误）",
                    details="请检查引擎配置和网络连接"
                )
        
        # 尝试使用选中的引擎
        return await self._try_ocr_with_engine(engine_name, base64_image)
    
    async def _ocr_with_failover(self, base64_image: str) -> Tuple[str, str]:
        """使用故障转移策略执行 OCR"""
        # 优先使用 deepseek
        primary_engine = "deepseek"
        fallback_engine = "mineru"
        
        # 尝试主引擎
        if await self._is_engine_available(primary_engine):
            try:
                return await self._try_ocr_with_engine(primary_engine, base64_image)
            except APICallException as e:
                logger.warning(
                    f"Primary engine '{primary_engine}' failed, "
                    f"attempting fallback: {str(e)}"
                )
                # 主引擎失败，尝试备用引擎
                if await self._is_engine_available(fallback_engine):
                    try:
                        return await self._try_ocr_with_engine(fallback_engine, base64_image)
                    except APICallException as fallback_error:
                        logger.error(
                            f"Fallback engine '{fallback_engine}' also failed: {str(fallback_error)}"
                        )
                        raise APICallException(
                            message="所有 OCR 引擎都失败",
                            details=f"主引擎错误: {str(e)}, 备用引擎错误: {str(fallback_error)}"
                        )
                else:
                    raise APICallException(
                        message="主引擎失败且备用引擎不可用",
                        details=f"主引擎错误: {str(e)}"
                    )
        else:
            # 主引擎不可用，尝试备用引擎
            if await self._is_engine_available(fallback_engine):
                return await self._try_ocr_with_engine(fallback_engine, base64_image)
            else:
                raise APICallException(
                    message="所有 OCR 引擎都不可用（熔断）",
                    details="请等待熔断恢复或检查引擎配置"
                )
    
    async def _select_available_engine_round_robin(self) -> Optional[str]:
        """轮询选择下一个可用引擎"""
        max_attempts = len(self._engine_names)
        
        for _ in range(max_attempts):
            # 获取当前索引的引擎
            engine_name = self._engine_names[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._engine_names)
            
            # 检查引擎是否可用
            if await self._is_engine_available(engine_name):
                return engine_name
        
        # 所有引擎都不可用
        return None
    
    async def _is_engine_available(self, engine_name: str) -> bool:
        """
        检查引擎是否可用（未熔断）
        
        Args:
            engine_name: 引擎名称
            
        Returns:
            bool: True 表示可用，False 表示熔断
        """
        if engine_name not in self.engine_stats:
            return False
        
        stats = self.engine_stats[engine_name]
        is_open = stats.check_circuit_breaker(
            self.circuit_breaker_threshold,
            self.circuit_breaker_timeout
        )
        
        return not is_open
    
    async def _try_ocr_with_engine(
        self,
        engine_name: str,
        base64_image: str
    ) -> Tuple[str, str]:
        """
        尝试使用指定引擎执行 OCR
        
        Args:
            engine_name: 引擎名称
            base64_image: Base64 编码的图像
            
        Returns:
            Tuple[str, str]: (markdown_content, engine_name)
            
        Raises:
            APICallException: OCR 调用失败
        """
        if engine_name not in self.engines:
            raise ValueError(f"Unknown engine: {engine_name}")
        
        engine = self.engines[engine_name]
        stats = self.engine_stats[engine_name]
        
        # 特殊处理：MinerU 不支持逐页 OCR
        if engine_name == "mineru":
            raise MinerUAPIException(
                message="MinerU 不支持逐页 image OCR",
                details="请在处理器入口走 mineru 的整PDF解析链路（ocr_pdf）。"
            )
        
        try:
            logger.debug(f"Calling OCR engine: {engine_name}")
            markdown = await engine.ocr_image(base64_image)
            
            # 记录成功
            stats.record_success()
            logger.info(f"OCR success with engine '{engine_name}'")
            
            return markdown, engine_name
            
        except APICallException as e:
            # 记录失败
            stats.record_failure()
            logger.error(
                f"OCR failed with engine '{engine_name}': {str(e)} "
                f"(consecutive failures: {stats.consecutive_failures})"
            )
            raise
    
    def get_engine_stats(self, engine_name: Optional[str] = None) -> Dict:
        """
        获取引擎统计信息
        
        Args:
            engine_name: 引擎名称，None 表示获取所有引擎的统计
            
        Returns:
            Dict: 统计信息字典
        """
        if engine_name:
            if engine_name in self.engine_stats:
                return {
                    engine_name: self.engine_stats[engine_name].get_stats()
                }
            else:
                return {}
        else:
            return {
                name: stats.get_stats()
                for name, stats in self.engine_stats.items()
            }
    
    def reset_engine_stats(self, engine_name: Optional[str] = None):
        """
        重置引擎统计信息
        
        Args:
            engine_name: 引擎名称，None 表示重置所有引擎
        """
        if engine_name:
            if engine_name in self.engine_stats:
                self.engine_stats[engine_name] = EngineStats()
                logger.info(f"Reset stats for engine: {engine_name}")
        else:
            for name in self.engine_stats:
                self.engine_stats[name] = EngineStats()
            logger.info("Reset stats for all engines")

