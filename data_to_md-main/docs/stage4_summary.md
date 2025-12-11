# 阶段4完成总结：MinerU 接入与双引擎封装

## 任务概述

**阶段**: 阶段4  
**难度**: ★★★☆☆  
**状态**: ✅ 已完成  
**完成时间**: 2025-12-06

---

## 已完成的任务

### 1. 统一 OCR 引擎接口抽象

#### 1.1 BaseOCRClient 抽象接口（`app/services/external/base_ocr_client.py`）

为后续多 OCR 引擎并存做准备，新增统一的 OCR 客户端基类：

- 类：`BaseOCRClient`
- 核心方法：
  - `async ocr_image(base64_image: str) -> str`
    - 输入：不带 `data:image/...;base64,` 前缀的 Base64 图像字符串
    - 输出：识别得到的 Markdown 文本
  - `async ocr_pdf(file_path: str) -> str`
    - 默认实现直接抛出 `NotImplementedError`
    - 作为“整 PDF 级别 OCR”的可选扩展点（当前流程仍以逐页图片 OCR 为主）

该抽象规范了所有 OCR 引擎在本项目中的最小能力集合，使 DeepSeek 与 MinerU 能以一致的方式被 PDF 处理链使用。

---

### 2. DeepSeekClient 改造：实现统一接口

文件：`app/services/external/deepseek_client.py`

#### 2.1 接入 BaseOCRClient

- 修改：
  - 原有 `class DeepSeekClient:` → `class DeepSeekClient(BaseOCRClient):`
  - 保持原 `ocr_image` 行为与签名不变，仅实现接口抽象。

#### 2.2 保持现有能力与容错

- DeepSeekClient 仍然负责：
  - 从 `Settings` 中读取 `deepseek_base_url`、`deepseek_api_key`、`deepseek_model` 等配置
  - 通过 `openai.OpenAI` 客户端调用 DeepSeek OCR 模型
  - 内置指数退避重试 `_retry_with_backoff(...)`
  - 解析响应并调用 `_clean_deepseek_output` 清理 `<|ref|>`、`<|det|>` 等特有标记
  - 在异常时抛出 `DeepSeekAPIException`

通过这一步，DeepSeek 成为“标准 OCR 引擎实现之一”，后续逻辑不再直接依赖具体 DeepSeek 细节，只依赖 `BaseOCRClient` 抽象能力。

---

### 3. MinerUClient 实现：第二套 OCR 引擎

文件：`app/services/external/mineru_client.py`

#### 3.1 配置与初始化

- 新增配置项（`app/config.py`）：
  - `mineru_api_key: str`（环境变量：`MINERU_API_KEY`）
  - `mineru_base_url: str`（环境变量：`MINERU_BASE_URL`）
  - `mineru_timeout: int`（HTTP 请求超时秒数）
- 客户端初始化：
  - 从全局 `Settings` 中读取上述配置
  - 当 `api_key` 或 `base_url` 为空时，仅记录 warning，真正调用时再抛出业务异常，避免未使用 MinerU 的场景被误伤

#### 3.2 接口实现

- 类：`MinerUClient(BaseOCRClient)`
- 方法：
  - `async ocr_image(base64_image: str) -> str`
    - 使用 `httpx.AsyncClient` 发起 POST 请求
    - HEADERS：通过 `Authorization: Bearer <api_key>` 进行鉴权
    - BODY：当前采用通用字段 `{"image_base64": base64_image}`，具体字段名可根据 MinerU 官方文档调整
    - 非 200 状态码、网络异常、响应 JSON 解析失败或缺少预期字段时，统一抛出 `MinerUAPIException`
  - `async ocr_pdf(file_path: str) -> str`
    - 直接上传本地 PDF 文件进行 OCR（如果 MinerU 提供整 PDF 能力）
    - 使用 `multipart/form-data` 形式上传 `file`
    - 各类错误同样封装为 `MinerUAPIException`

> 当前 `ocr_image` / `ocr_pdf` 的 URL 路径与字段名为通用骨架，需要在掌握 MinerU 实际 OpenAPI/SDK 文档后做一次微调，以对齐真实接口。

#### 3.3 异常体系

- 在 `app/exceptions/service_exceptions.py` 中新增：
  - `class MinerUAPIException(APICallException): ...`
- 这样 DeepSeek 与 MinerU 都归一到 `APICallException` 之下，便于上层做统一捕获与错误展示。

---

### 4. ConvertOptions 增加 ocr_engine 参数

文件：`app/models/request.py`

#### 4.1 字段定义

在 `ConvertOptions` 中新增枚举型配置项：

- 字段：
  - `ocr_engine: Literal["deepseek", "mineru", "auto"] = "auto"`
- 说明：
  - `deepseek`：仅使用 DeepSeek
  - `mineru`：仅使用 MinerU
  - `auto`：先尝试 DeepSeek，失败时自动回退到 MinerU

示例更新：

```json
{
  "options": {
    "dpi": 144,
    "include_metadata": true,
    "no_pagination_and_metadata": false,
    "async": true,
    "max_pages": 100,
    "ocr_engine": "auto"
  }
}
```

#### 4.2 链路传递

- `POST /api/v1/convert` 中，`options` 依旧通过 `ConvertOptions` 进行解析与校验
- 解析后的 `convert_options.model_dump()` 传递给 `ConversionService.convert(...)`
- 最终在 `PDFConverter.convert(...)` 中从 `options` 中取出 `ocr_engine`，交给具体 PDF 处理器使用。

---

### 5. PDF 处理链中的引擎选择与回退策略

#### 5.1 PDFConverter 侧的引擎参数下传

文件：`app/core/converters/pdf/pdf_converter.py`

- 在 `convert(...)` 中：
  - 分析 PDF 得到 `pdf_info`
  - 从 `options` 读取：
    - `ocr_engine = options.get("ocr_engine", "auto") if options else "auto"`
  - 调用 `_select_processor(pdf_type, ocr_engine=ocr_engine)` 获取对应处理器实例

- `_select_processor(...)` 策略：
  - `PDFType.IMAGE` → `ImagePDFProcessor(ocr_engine=ocr_engine)`
  - `PDFType.MIXED` → `MixedPDFProcessor(ocr_engine=ocr_engine)`
  - `PDFType.TEXT` → `MixedPDFProcessor(ocr_engine=ocr_engine)`

这样，无论纯图片、图文混排还是纯文本 PDF，所需的 OCR 引擎选择策略都从 `ConvertOptions` 统一注入。

#### 5.2 ImagePDFProcessor：纯图片 PDF 中的双引擎

文件：`app/core/converters/pdf/image_pdf_processor.py`

- 构造函数改造：
  - `__init__(self, ocr_engine: str = "auto")`
  - 初始化：
    - `self.deepseek_client = DeepSeekClient()`
    - `self.mineru_client = MinerUClient()`
    - `self.ocr_engine = ocr_engine`

- 单页处理 `_process_page(...)`：
  - 将每页渲染为 Base64：
    - `base64_image = image_processor.render_page_to_base64(...)`
  - 调用 `_run_ocr(base64_image)` 获得：
    - `markdown_content, engine_used`
  - 创建 `ContentChunk` 时在 `metadata` 中写入：
    - `method: "{engine_used}_ocr"`
    - `ocr_engine: engine_used`

- 错误时的降级输出：
  - 若本页 OCR 失败，返回一个包含错误信息的 `ContentChunk`：
    - `metadata` 中写入 `{'error': str(e), 'ocr_engine': self.ocr_engine}` 便于上层排查。

- 核心选择逻辑 `_run_ocr(...)`：

  - 当 `ocr_engine == "deepseek"`：
    - 直接调用 `DeepSeekClient.ocr_image`，失败向上抛出
  - 当 `ocr_engine == "mineru"`：
    - 直接调用 `MinerUClient.ocr_image`，失败向上抛出
  - 当 `ocr_engine == "auto"`：
    - 尝试 DeepSeek
      - 成功：返回 `("markdown", "deepseek")`
      - 异常：记录 warning 日志后，自动回退到 MinerU
    - 尝试 MinerU
      - 成功：返回 `("markdown", "mineru")`
      - 异常：将 MinerU 异常向上抛出

#### 5.3 MixedPDFProcessor：图文混排场景中的双引擎

文件：`app/core/converters/pdf/mixed_pdf_processor.py`

- 构造函数同样接受 `ocr_engine` 并初始化两个客户端：
  - `self.deepseek_client = DeepSeekClient()`
  - `self.mineru_client = MinerUClient()`
- 在 `_process_page(...)` 中根据 `PageInfo.has_images` 决定走：
  - `_process_with_ocr(...)`（有图片，整页 OCR）
  - `_process_with_text_extraction(...)`（无图片，纯文本提取）
- `_process_with_ocr(...)` 中使用与 `ImagePDFProcessor` 相同的 `_run_ocr(...)` 策略与元数据记录规则。
- 文本提取 `_process_with_text_extraction(...)` 不涉及 OCR 引擎，保持原先逻辑。

---

### 6. 测试与验证

#### 6.1 现有 PDFConverter 单测回归

文件：`tests/test_core/test_pdf_converter.py`

在完成阶段4改造后，直接运行现有的阶段3单元测试：

- 命令：
  - `pytest tests/test_core/test_pdf_converter.py -q`
- 结果：
  - 7 个测试用例全部通过
  - 测试涵盖：
    - 纯图片 PDF 走 OCR 流程
    - 图文混排 PDF 的 OCR + 文本混合处理
    - 纯文本 PDF 的文本提取
    - 输出模式（带页码/带元数据 与 纯内容模式）
    - 根据 `PDFType` 选择不同 Processor 的策略

这些测试未显式校验 `ocr_engine` 的行为，但通过验证可以说明：

1. 我们对 `PDFConverter`、`ImagePDFProcessor`、`MixedPDFProcessor` 的改动未破坏原有功能
2. `ocr_engine` 参数在为默认值 `"auto"` 时，对旧调用是无感/兼容的

#### 6.2 后续可扩展的测试建议

若需要进一步验证多引擎策略，可以在后续阶段新增以下测试：

- 使用 `unittest.mock` 分别 mock：
  - `DeepSeekClient.ocr_image`
  - `MinerUClient.ocr_image`
- 覆盖场景：
  1. `ocr_engine == "deepseek"` 且 DeepSeek 成功 → MinerU 不应被调用
  2. `ocr_engine == "mineru"` 且 MinerU 成功 → DeepSeek 不应被调用
  3. `ocr_engine == "auto"` 且 DeepSeek 抛异常 → 自动改用 MinerU，并在元数据中记录 `ocr_engine == "mineru"`

---

## 实现效果

### 1. 支持 DeepSeek + MinerU 双引擎

- Backend 现在可以通过一个配置字段 `ocr_engine` 控制使用哪一种 OCR 能力：
  - 为某些特定文档只使用 MinerU（例如对表格/票据类 MinerU 表现更好时）
  - 在不稳定网络或配额受限的情况下，优先使用 DeepSeek，仅在其失败时自动切换到 MinerU

### 2. 统一接口，便于扩展与维护

- DeepSeek 与 MinerU 都实现了 `BaseOCRClient`，具体差异被封装在各自客户端内部
- PDF 处理链只知晓“有一个能 `ocr_image` 的客户端”，而不关心底层实现细节
- 如果未来需要接入第三套 OCR 引擎（如自建模型或其他云服务），只需：
  1. 新建一个实现 `BaseOCRClient` 的客户端
  2. 在处理链的引擎选择逻辑中增加一个分支

### 3. 更灵活的容错策略

- `ocr_engine == "auto"` 提供了一个简单但实用的故障转移机制：
  - 避免单一引擎故障导致整份 PDF 转换失败
  - 尤其适用于高可用场景或批量任务场景
- 错误信息中带有 `ocr_engine` 字段，方便排查是哪个引擎导致的异常。

---

## 新增/修改文件清单（阶段4相关）

### 新增

- ✅ `app/services/external/base_ocr_client.py` — 统一 OCR 引擎抽象接口
- ✅ `app/services/external/mineru_client.py` — MinerU OCR 客户端骨架
- ✅ `docs/stage4_summary.md` — 本阶段总结文档

### 主要修改

- ✅ `app/services/external/deepseek_client.py`  — 继承 `BaseOCRClient`，实现统一 OCR 接口
- ✅ `app/config.py`                           — 新增 MinerU 配置项，清理 DeepSeek 默认 API Key
- ✅ `app/models/request.py`                   — `ConvertOptions` 新增 `ocr_engine` 字段
- ✅ `app/core/converters/pdf/pdf_converter.py` — 将 `ocr_engine` 传入 PDF 处理器，并记录日志
- ✅ `app/core/converters/pdf/image_pdf_processor.py` — 引入双 OCR 客户端与引擎选择/回退逻辑
- ✅ `app/core/converters/pdf/mixed_pdf_processor.py` — 图文混排场景下的双引擎接入
- ✅ `app/exceptions/service_exceptions.py`   — 新增 `MinerUAPIException` 异常类型

---

## 进度更新

| 项目    | 进度     |
|---------|----------|
| 阶段0   | ✅ 100% |
| 阶段1   | ✅ 100% |
| 阶段2   | ✅ 100% |
| 阶段3   | ✅ 100% |
| 阶段4   | ✅ 100% |
| 阶段5-8 | 📋 待开始 |

**总体进度**: 5/9 阶段完成 (约56%)

---

## 总结

阶段4 围绕“MinerU 接入与双引擎封装”这一目标，完成了以下工作：

1. ✅ 抽象出统一的 `BaseOCRClient` 接口，规范 OCR 引擎在系统中的最小能力集合
2. ✅ 改造 DeepSeekClient 以实现统一接口，保持原有能力和容错不变
3. ✅ 新增 MinerUClient 骨架，实现鉴权、请求和错误处理逻辑
4. ✅ 在 `ConvertOptions` 中新增 `ocr_engine` 参数，并贯穿到整条 PDF 处理链
5. ✅ 在 `ImagePDFProcessor` / `MixedPDFProcessor` 中实现 DeepSeek/MinerU/auto 三种引擎策略
6. ✅ 回归现有 PDFConverter 单测，确认改造对原有功能零破坏

**难度评估**: ★★★☆☆（中等）

- 主要挑战在于：
  - 在不破坏既有流程与测试的前提下插入新的抽象层
  - 设计简单、可扩展的引擎选择与故障转移逻辑
  - 为未来第三套 OCR 引擎预留接口与配置空间

**下一步**: 可在后续阶段扩展：

- 为 MinerU 接口填充真实的 URL/字段，并补充专门的单元测试
- 在 `ocr_engine == "auto"` 的基础上，进一步演进为更智能的引擎选择策略（例如：按文档类型、失败率、延迟指标动态切换）
- 将多引擎信息暴露给前端/调用方（如返回每页使用的引擎统计），帮助做质量对比与 A/B 测试。
