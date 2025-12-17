# OCR 轮询/熔断机制实现说明

## 背景与目标
在 PDF → Markdown 过程中引入多 OCR 引擎（DeepSeek、MinerU）。为提升稳定性并避免单一引擎被打爆，实现：
- 引擎路由：round_robin / failover
- 熔断：连续失败 N 次短暂熔断，超时后恢复
- 配置化开关：默认更稳的 failover，逐页禁用 MinerU

## 关键实现
### 配置（`app/config.py`）
- `ocr_routing_strategy`：默认 `failover`（推荐稳定模式）。
- `ocr_circuit_breaker_threshold` / `ocr_circuit_breaker_timeout`：熔断阈值与恢复时间。
- `enable_mineru_page_ocr`：默认 `False`，逐页 OCR 不使用 MinerU（MinerU 不支持逐页）。
- 未来预留 `ocr_engine_weights`（未启用）。

### 路由器（`app/core/converters/pdf/ocr_router.py`）
- 引擎注册：默认仅 DeepSeek；如配置开启则附加 MinerU。
- 策略：
  - `round_robin`：循环选择可用引擎（受熔断影响）。
  - `failover`：主用 DeepSeek，失败尝试备用；当前逐页主要用 DeepSeek。
- 熔断：
  - 引擎统计 `EngineStats` 记录连续失败、总调用、最后失败时间。
  - 连续失败达阈值 → 熔断；超时后尝试恢复；成功调用清零。
- 线程安全：使用 `asyncio.Lock` 保护轮询索引与可用性检查。
- 日志：初始化打印策略/阈值/是否启用 MinerU；每次成功/失败记录引擎名与失败次数。

### Processor 集成
- `image_pdf_processor.py` / `mixed_pdf_processor.py`：
  - `ocr_router = OCRRouter()`，逐页 OCR 统一走路由。
  - MinerU 逐页显式报错（保持行为可知），整 PDF 场景仍可在入口选择 MinerU 的 `ocr_pdf`。

### 测试（`tests/test_ocr_router.py`）
- 使用虚拟成功/失败客户端，覆盖：
  - round_robin 轮换不同引擎。
  - 连续失败触发熔断、后续可用性检查。
- 需 `pytest-asyncio` 运行：`PYTHONPATH=... python -m pytest -q tests/test_ocr_router.py`

## 使用与验证
### 启动示例（推荐稳定配置）
```bash
cd data_to_md-main
set OCR_ROUTING_STRATEGY=failover
set ENABLE_MINERU_PAGE_OCR=false
set PYTHONPATH=./data_to_md-main
uvicorn app.main:app --host 0.0.0.0 --port 8001
```
### 触发轮询/熔断
- 纯图片 PDF 才会走逐页 OCR，日志可见引擎选择。
- 要观察熔断：临时让 DeepSeek key 失效，阈值设小（如 2），多次请求后会熔断；恢复后超时再请求可自动恢复。
- 如果希望 round_robin 但避免 MinerU 报错，保持 `ENABLE_MINERU_PAGE_OCR=false`（仅 DeepSeek 参与）。

## 策略选择建议
- 生产/稳定：`failover` + `ENABLE_MINERU_PAGE_OCR=false`（默认）。
- 需要轮询实验：`round_robin`，并仅在确认 MinerU 支持逐页时才开启 `ENABLE_MINERU_PAGE_OCR=true`，否则轮到 MinerU 的页面会报错。

## 修改摘要
- 配置默认切为 failover，新增 MinerU 逐页开关。
- OCRRouter 初始化仅注册 DeepSeek，按配置可选启用 MinerU；日志扩展。
- Processor 改为通过 OCRRouter 调用；逐页 MinerU 仍显式提示不支持。
- 新增异步单测覆盖轮询与熔断。

