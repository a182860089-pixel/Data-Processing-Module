import sys
from pathlib import Path

import pytest

# 允许从仓库根目录导入 app 包（兼容本地测试与编辑器检查）
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.converters.pdf.ocr_router import OCRRouter, EngineStats  # type: ignore
from app.exceptions.service_exceptions import APICallException  # type: ignore


class SuccessClient:
    """Fake OCR client that always succeeds."""

    def __init__(self, name: str):
        self.name = name

    async def ocr_image(self, base64_image: str) -> str:
        return f"md-{self.name}"


class FailingClient:
    """Fake OCR client that always fails."""

    def __init__(self, message: str = "fail"):
        self.message = message

    async def ocr_image(self, base64_image: str) -> str:
        raise APICallException(message=self.message, details="test failure")


def _reset_router_engines(router: OCRRouter, engines: dict):
    """Helper to inject fake engines and reset stats/index."""
    router.engines = engines
    router.engine_stats = {name: EngineStats() for name in engines.keys()}
    router._engine_names = list(engines.keys())
    router._current_index = 0


@pytest.mark.asyncio
async def test_round_robin_switches_between_engines():
    router = OCRRouter(strategy="round_robin", circuit_breaker_threshold=3, circuit_breaker_timeout=60)
    _reset_router_engines(
        router,
        {
            "engine_a": SuccessClient("a"),
            "engine_b": SuccessClient("b"),
        },
    )

    md1, used1 = await router.ocr_image("img")
    md2, used2 = await router.ocr_image("img")

    assert used1 == "engine_a"
    assert used2 == "engine_b"
    assert md1 == "md-a"
    assert md2 == "md-b"


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_consecutive_failures():
    router = OCRRouter(strategy="round_robin", circuit_breaker_threshold=2, circuit_breaker_timeout=60)
    _reset_router_engines(router, {"engine_a": FailingClient("boom")})

    # First failure increments counter
    with pytest.raises(APICallException):
        await router.ocr_image("img")

    # Second failure triggers circuit breaker
    with pytest.raises(APICallException):
        await router.ocr_image("img")

    stats = router.get_engine_stats("engine_a")["engine_a"]
    assert stats["consecutive_failures"] >= 2
    # 触发一次可用性检查以打开熔断
    available = await router._is_engine_available("engine_a")
    assert available is False
    stats = router.get_engine_stats("engine_a")["engine_a"]
    assert stats["is_circuit_open"] is True

