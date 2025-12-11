# 阶段3完成总结：PDF→Markdown 现有功能增强

## 📋 任务概述

**阶段**: 阶段3  
**难度**: ★★☆☆☆  
**状态**: ✅ 已完成  
**完成时间**: 2025-12-06

---

## ✅ 已完成的任务

### 1. 转换选项与输出模式增强

#### 1.1 新增 ConvertOptions 模型 (`app/models/request.py`)

**新增/强化字段**:
- `dpi`: 图像渲染 DPI（72–300，默认 144）
- `show_page_number`: 是否在 Markdown 中显示页码标记
- `include_metadata`: 是否在开头生成文档元数据（front matter）
- `no_pagination_and_metadata`: 兼容参数，一键关闭分页与元数据（优先级最高）
- `async` (别名: `async_mode`): 预留异步处理开关（当前仍以同步实现为主）
- `max_pages`: 最大处理页数（默认 100）

**模式约定**:
- **模式A（带页码+元数据）**：`show_page_number=True`, `include_metadata=True`
- **模式B（纯内容阅读）**：`show_page_number=False`, `include_metadata=False`
- **兼容模式**：`no_pagination_and_metadata=True` ≈ 模式B（强制关闭分页+元数据）

#### 1.2 接口入参统一解析 (`app/api/v1/endpoints/convert.py`)

- 接口 `POST /api/v1/convert` 通过 `ConvertOptions` 统一解析 `options`：
  - 从 `Form` 中接收 JSON 字符串 `options`
  - 使用 `ConvertOptions(**options_dict)` 做校验与默认值填充
- 保留原有参数含义（`dpi`、`include_metadata`、`max_pages`），同时向下兼容历史调用方式

**效果**:
- 转换选项集中到一个 Pydantic 模型，方便文档生成与前后端对齐
- 为后续引入异步模式、页数限制等能力预留了统一入口

---

### 2. Markdown 输出质量提升

#### 2.1 MarkdownGenerator 多模式输出 (`app/core/common/markdown_generator.py`)

**核心职责**:
- 将 `ContentChunk` 列表 + `PDFInfo` 合成为完整 Markdown 文本
- 支持“带分页/带元数据”和“无分页纯内容”两种主输出模式

**关键特性**:
- 构造参数：
  - `show_page_number`: 控制是否插入 `<!-- Page N (type) -->` 页面标记
  - `include_metadata`: 控制是否生成文首 YAML 风格元数据块
  - `no_pagination_and_metadata`: 兼容参数，优先级最高，直接切换到纯内容模式
- `generate(...)`：
  - 模式A：可选元数据 + 每页前插入页面标记 + 页尾 `---` 分隔符
  - 模式B：不插入页面标记与分隔，仅按内容顺序拼接
- `_generate_metadata(...)`：统一生成：
  - `title`, `pages`, `pdf_type`, `generated_at`
- `_generate_unpaginated(...)`：
  - 智能句尾处理：若 chunk 以句号/问号/感叹号（中英）结尾，则自动插入换行
  - 不输出任何页码/分隔符/元数据，仅保留纯内容
- `post_process(...)`：调用 `ContentCleaner` 做统一清洗（见下一节）

#### 2.2 内容清洗管线 (`app/core/common/content_cleaner.py`)

**ContentCleaner 主要能力**:
- `clean_text`：
  - 统一换行符 (`\r\n` → `\n`)
  - 合并多余空白，仅保留单个空格
  - 去除行首尾空白、多余空行（最多保留一个空行）
- `clean_markdown`：
  - 在 `clean_text` 基础上，额外处理：
    - 清理多余的 ``` 代码块标记
    - 标题前后空行归一化
    - 再次收敛重复空行
- `remove_special_markers`：
  - 去除 LLM/模型输出中的特殊标记：`<|end_of_sentence|>`、`<|end_of_text|>`、`<|ref|>`、`<|det|>` 等
- `normalize_whitespace`：
  - 再次统一换行符
  - 清理行尾空白，保证 Markdown 更整洁

**整合位置**:
- `MarkdownGenerator.post_process` 对最终 Markdown 进行一站式清理
- `TextExtractor` 也复用 `ContentCleaner` 做基础文本规整

**效果**:
- 明显减少“奇怪换行、冗余空行、残留标记”等问题
- 同一份 PDF 在不同引擎参数下输出更稳定、更易阅读

---

### 3. 文本提取与段落识别增强

#### 3.1 TextExtractor 智能段落算法 (`app/core/converters/pdf/text_extractor.py`)

**改造点**:
- 不再直接使用 `page.get_text("text")` 粗暴拼接，而是：
  - 使用 `page.get_text("blocks")` 获取文本块（带坐标、类型）
  - 过滤出纯文本块，丢弃图片块
- 基于 **块间位置信息** 进行段落划分：
  - 垂直间距（行间距/段间距）
  - 左侧缩进变化（是否是新段落或列表缩进）
  - 前一块结尾是否为句号/冒号等标点
  - 列表项识别（中英文序号、“一二三、1.、(1)” 等）
- 段落内行处理：
  - 删除块内的硬换行（视为同一段落的换行），直接拼接
  - 段落之间用双换行 `\n\n` 分隔，符合 Markdown 段落习惯

**输出特点**:
- 段落边界更自然，尽量还原原文逻辑结构
- 列表段落在多数情况下可以保持连贯显示

#### 3.2 文本 → Markdown 的封装

- `text_to_markdown(...)` 目前保持“轻加工”策略：
  - 保留原始段落结构，不做激进的标题/列表重写
  - 为后续更智能的结构化识别（标题、列表、表格）预留扩展点
- 与 `MixedPDFProcessor` 配合：
  - 对无图片的页面直接走 `TextExtractor`，避免不必要的 OCR 调用

**效果**:
- 纯文本或图文混排中的“文本页”阅读体验显著提升
- 多列/表格较多的 PDF 在文本模式下仍具备可读性

---

### 4. PDF 转换流程与元数据增强

#### 4.1 PDFConverter 接入新输出模式 (`app/core/converters/pdf/pdf_converter.py`)

- 在 `convert(...)` 中：
  - 调用 `PDFAnalyzer.analyze` 获取 `PDFInfo`（类型、页数、文件大小等）
  - 依据 `PDFType` 选择处理器：
    - `IMAGE` → `ImagePDFProcessor`
    - `MIXED` → `MixedPDFProcessor`
    - `TEXT` → `MixedPDFProcessor`（只走文本提取）
  - 从 `options` 中读取：`show_page_number` / `include_metadata` / `no_pagination_and_metadata`
  - 创建 `MarkdownGenerator`，生成最终 Markdown
- 元数据增强：
  - `total_pages`: 总页数
  - `pdf_type`: 分析得到的 PDF 类型
  - `file_size`: 原始文件大小
  - `ocr_pages`: OCR 处理的页数
  - `text_pages`: 文本提取的页数

#### 4.2 ConversionService / TaskManager 输出信息统一 (`app/services/conversion/conversion_service.py`)

- `ConversionService.convert(...)`：
  - 负责接入 `FileTypeDetector`、`ConverterFactory`、`TaskManager` 和 `FileService`
  - 在完成转换后补充元数据：
    - `processing_time`: 处理耗时（秒）
    - `output_file_size`: 输出 Markdown 文件大小
  - 最终通过 `task_manager.complete_task(...)` 持久化任务结果
- `get_task_status(...)`：
  - 返回统一的任务状态结构：
    - `status`（枚举 `TaskStatus`）
    - `progress`（`current_page` / `total_pages` / `percentage`）
    - `result`（在完成时携带 `markdown_content`、`download_url`、`metadata`）

**接口侧体现**:
- `POST /api/v1/convert` → `ConvertSyncResponse`：
  - `metadata` 中包含：`pages_processed`、`ocr_pages`、`text_pages`、`processing_time`、`file_size`
- `GET /api/v1/status/{task_id}` → `StatusResponse`：
  - 返回任务进度和（若已完成）结果摘要，便于前端构建进度条与结果预览

---

### 5. 测试与验证

#### 5.1 单元测试：PDFConverter 全面覆盖 (`tests/test_core/test_pdf_converter.py`)

**覆盖场景**:
1. 纯图片 PDF：
   - 所有页面走 OCR 流程
   - 验证 `ocr_pages == total_pages`、`text_pages == 0`
2. 图文混排 PDF：
   - 带图片/表格的页面走 OCR，其余走文本提取
   - 验证 OCR 页数与文本页数统计正确
3. 纯文本 PDF：
   - 所有页面均走文本提取逻辑
4. 输出模式：
   - 模式A：带页码+元数据 → Markdown 中应包含元数据和 `<!-- Page N -->` 标记
   - 模式B：纯内容 → 不应出现元数据和页码标记
   - 兼容模式：`no_pagination_and_metadata=True` 等价于模式B
5. 处理器选择：
   - `PDFType.IMAGE` → `ImagePDFProcessor`
   - `PDFType.MIXED` / `TEXT` → `MixedPDFProcessor`

> 测试中广泛使用 `unittest.mock` 对 OCR 和 PDF 分析进行模拟，加快执行速度并聚焦业务逻辑正确性。

#### 5.2 集成验证脚本：无分页模式联调 (`test_no_pagination.py`)

- 脚本目标：快速对比“带分页模式”与“无分页纯内容模式”的输出差异
- 使用方式：
  1. 启动服务：`python app/main.py`
  2. 运行脚本：`python test_no_pagination.py`
- 验证点：
  - 默认模式：
    - Markdown 开头包含元数据 `--- ... ---`
    - 内容中包含 `<!-- Page ... -->` 和 `---` 分隔符
  - 无分页模式：
    - 不包含元数据块
    - 不包含页面标记和分隔符
    - Markdown 文本更接近“整篇文章”阅读体验

---

## 🎯 实现效果

### 1. 输出模式可配置，兼顾调试与阅读

- 对后端/算法侧：
  - 模式A（带页码+元数据）便于排查问题、复现单页效果、做质量对比
- 对终端用户/前端展示：
  - 模式B（纯内容）更贴近日常阅读体验，可直接渲染为文章详情或知识库内容
- 兼容参数 `no_pagination_and_metadata` 确保旧调用方式无感升级

### 2. Markdown 更干净、更稳定

- 统一的清洗策略减少了：
  - 杂乱的换行、粘连的标点、尾部空白
  - 模型残留控制标记对最终展示的干扰
- 在相同 PDF 上多次调用，输出差异主要来自 OCR 本身，而非后处理抖动

### 3. 任务状态与元数据更易被消费

- 前端可直接使用 `StatusResponse.progress` 绘制进度条
- 调用方可根据 `ocr_pages` / `text_pages` 快速判断文档类型和处理成本
- `processing_time` 与 `output_file_size` 为后续压测与性能优化提供基础指标

---

## 🧪 测试命令示例

```bash
# 运行单元测试（示例）
pytest tests/test_core/test_pdf_converter.py -q

# 启动服务并手动验证无分页模式
python app/main.py
python test_no_pagination.py
```

---

## 📁 新增/修改文件清单（阶段3相关）

### 新增
- ✅ `app/core/common/markdown_generator.py`  — Markdown 生成与多模式控制
- ✅ `app/core/common/content_cleaner.py`      — 文本/Markdown 清洗工具
- ✅ `app/core/converters/pdf/text_extractor.py` — 智能文本提取与段落识别
- ✅ `tests/test_core/test_pdf_converter.py`  — PDF 转换核心单元测试
- ✅ `test_no_pagination.py`                  — 无分页模式联调脚本
- ✅ `docs/stage3_summary.md`                 — 本阶段总结文档

### 主要修改
- ✅ `app/models/request.py` — 新增 `ConvertOptions` 并扩展输出模式相关字段
- ✅ `app/api/v1/endpoints/convert.py` — 使用 `ConvertOptions` 解析 `options`，返回扩展元数据
- ✅ `app/core/converters/pdf/pdf_converter.py` — 接入 `MarkdownGenerator` 与新的元数据统计
- ✅ `app/core/converters/pdf/mixed_pdf_processor.py` — 统一走 `TextExtractor` / OCR 的混合策略
- ✅ `app/core/converters/pdf/image_pdf_processor.py` — 保持并发模型，与新元数据统计兼容
- ✅ `app/services/conversion/conversion_service.py` — 填充处理耗时和输出文件大小
- ✅ `app/services/conversion/task_manager.py` — 继续承载扩展后的任务元数据
- ✅ `app/models/response.py` — 对 `ConvertSyncResponse` / `StatusResponse` 补充元数据结构说明

---

## 📊 进度更新

| 项目   | 进度      |
|--------|-----------|
| 阶段0 | ✅ 100% |
| 阶段1 | ✅ 100% |
| 阶段2 | ✅ 100% |
| 阶段3 | ✅ 100% |
| 阶段4-8 | 📋 待开始 |

**总体进度**: 4/9 阶段完成 (约44%)

---

## 🎉 总结

阶段3围绕“PDF→Markdown 现有功能增强”这一目标，完成了如下工作：

1. ✅ 将转换选项集中封装为 `ConvertOptions`，统一入口、约定清晰
2. ✅ 引入 `MarkdownGenerator` + `ContentCleaner`，显著提升 Markdown 输出质量
3. ✅ 通过 `TextExtractor` 智能段落算法，改善文本类 PDF 的阅读体验
4. ✅ 补齐转换元数据与任务状态字段，为后续异步队列、批量处理和压测优化打基础
5. ✅ 编写针对核心流程的单元测试与联调脚本，确保功能稳定可回归

**难度评估**: ★★☆☆☆（符合预期）
- 涉及对现有链路的“增强”而非彻底重构
- 主要挑战在于兼顾“兼容性 + 可配置性 + 输出质量”三者平衡

**下一步**: 进入阶段4 — MinerU 接入与双引擎封装，进一步提升复杂文档的识别能力。