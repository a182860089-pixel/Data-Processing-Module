# 阶段 0 梳理笔记：现有能力与流程概览

> 本文档总结了 `data_to_md-main` 当前的 PDF → Markdown 转换流程、任务管理与 API 时序，以及 `proc_image/smallimg/webp_compress.py` 的核心能力，为后续阶段设计提供基础认识。

---

## 一、PDF → Markdown 流程梳理

### 1.1 整体调用链

1. 外部通过 `POST /api/v1/convert` 上传 PDF。
2. `app/api/v1/endpoints/convert.py`：
   - 校验文件名、大小（`pdf_max_size_mb`）。
   - 解析 `options` 为 `ConvertOptions`。
   - 生成临时 `temp_task_id`，用 `FileService.save_upload_file` 将文件保存到 `storage/uploads/`。
   - 调用 `ConversionService.convert(file_path, filename, options)`。
3. `ConversionService.convert`：
   - 用 `FileTypeDetector` 判断文件类型，PDF 走 `PDFConverter`。
   - 使用 `TaskManager.create_task` 创建任务，状态为 `PENDING`。
   - 将任务状态更新为 `PROCESSING`。
   - 调用 `PDFConverter.convert()` 执行实际转换。
   - 将生成的 Markdown 通过 `FileService.save_output_file` 写入 `storage/outputs/`。
   - 调用 `TaskManager.complete_task` 标记任务完成并记录元数据（页数、OCR 页数、耗时、输出文件大小等）。
4. `convert` 接口把同步转换结果封装为 `ConvertSyncResponse` 返回，包括：
   - `success`、`task_id`、`markdown_content`、`download_url`、`metadata` 等。

### 1.2 PDF 类型判断逻辑（IMAGE / MIXED / TEXT）

相关文件：`app/core/converters/pdf/pdf_analyzer.py`、`app/models/enums.py`

1. `PDFAnalyzer.analyze(file_path)`：
   - 使用 `fitz.open(file_path)` 打开 PDF。
   - 统计总页数 `total_pages`、文件大小 `file_size`。
   - 逐页调用 `get_page_info(page, page_number)`，返回 `PageInfo`：
     - `text = page.get_text()`，根据 `pdf_text_threshold`（来自配置）判断 `has_text`：
       - `has_text = len(text.strip()) >= text_threshold`。
     - `image_list = page.get_images()`，记录 `image_count`。
     - 尝试 `page.find_tables()` 判断是否存在表格：
       - 若有表格，则视为有“图像/图表元素”。
     - 最终用：
       - `has_images = (image_count > 0) or has_tables`。
   - 汇总所有 `PageInfo`，调用 `detect_pdf_type(pages_info)` 计算整体类型。

2. `detect_pdf_type(pages_info)` 判定规则：
   - 统计：
     - `text_pages =` 有文本的页数（`p.has_text`）。
     - `image_pages =` 有图像/表格的页数（`p.has_images`）。
     - `total_pages = len(pages_info)`。
   - 逻辑：
     - 若 `text_pages == 0` → `PDFType.IMAGE`（纯图片 PDF）。
     - 若 `image_pages == 0` → `PDFType.TEXT`（纯文本 PDF）。
     - 否则 → `PDFType.MIXED`（图文混排 PDF）。

3. `PDFConverter._select_processor(pdf_type)`：
   - `IMAGE` → `ImagePDFProcessor`（所有页走 OCR）。
   - `MIXED` → `MixedPDFProcessor`（按页判断是否 OCR）。
   - `TEXT`  → 也使用 `MixedPDFProcessor`（仅文本提取）。
   - 其他类型抛出 `ConversionFailedException`。

### 1.3 页面并发处理模型（asyncio + 信号量）

#### 1.3.1 纯图片 PDF：`ImagePDFProcessor`

文件：`app/core/converters/pdf/image_pdf_processor.py`

- 初始化：
  - `self.dpi = settings.pdf_render_dpi`（默认 144）。
  - `self.max_concurrent = settings.max_concurrent_api_calls`（单文件内 OCR 并发上限）。
  - 依赖：`ImageProcessor`（渲染 PDF 页为图片）、`DeepSeekClient`（OCR 调用）。

- `process(file_path, file_info)`：
  1. 使用 `fitz.open(file_path)` 打开文档。
  2. 创建 `semaphore = asyncio.Semaphore(self.max_concurrent)`。
  3. 对每一页 `page_num in range(file_info.total_pages)`：
     - 构建协程 `self._process_page_with_semaphore(doc, page_num, semaphore)`，加入 `tasks` 列表。
  4. 使用 `await asyncio.gather(*tasks)` 并发执行所有页的处理。
  5. 关闭文档并返回 `List[ContentChunk]`。

- `_process_page_with_semaphore(doc, page_num, semaphore)`：
  - `async with semaphore:` → 串行进入临界区，保证同时进行的 `_process_page` 数量不超过上限。
  - 内部调用 `_process_page(doc, page_num)`。

- `_process_page(doc, page_num)`：
  1. 计算 `page_number = page_num + 1`。
  2. 取 `page = doc[page_num]`。
  3. 通过 `ImageProcessor.render_page_to_base64(page, dpi=self.dpi, optimize=True)` 渲染为 Base64 图片。
  4. 异步调用 `DeepSeekClient.ocr_image(base64_image)`，获取 Markdown 文本。
  5. 组装 `ContentChunk`：
     - `chunk_type = ChunkType.OCR`；
     - `metadata = { 'dpi': self.dpi, 'method': 'deepseek_ocr' }`。
  6. 若 OCR 失败，返回带错误信息的 `ContentChunk`，`metadata` 中包含 `error` 字段。

#### 1.3.2 图文混排 / 纯文本 PDF：`MixedPDFProcessor`

文件：`app/core/converters/pdf/mixed_pdf_processor.py`

- 初始化：
  - 同样使用 `self.dpi`、`self.max_concurrent` 控制渲染与并发。
  - 依赖：`ImageProcessor`（渲染图片）、`TextExtractor`（文本层提取和 Markdown 转换）、`DeepSeekClient`（OCR）。

- `process(file_path, file_info)`：
  1. 打开文档、创建信号量 `Semaphore(max_concurrent_api_calls)`。
  2. 遍历页号：
     - 从 `file_info.pages[page_num]` 取 `page_info`，其中包含 `has_images` 等信息。
     - 为每页构建 `_process_page_with_semaphore(doc, page_num, page_info, semaphore)` 协程，加入任务列表。
  3. `await asyncio.gather(*tasks)` 并发处理所有页面。

- `_process_page(doc, page_num, page_info)`：按页决策策略：
  - 若 `page_info.has_images` 为 `True`：
    - 整页走 OCR：`_process_with_ocr(page, page_number)`：
      - 渲染为 Base64，调用 `DeepSeekClient.ocr_image`，返回 `ChunkType.OCR` 的 `ContentChunk`。
  - 若 `page_info.has_images` 为 `False`：
    - 仅提取文本层：`_process_with_text_extraction(page, page_number)`：
      - `text = TextExtractor.extract_text(page)`；
      - `markdown_content = TextExtractor.text_to_markdown(text)`；
      - 返回 `ChunkType.TEXT` 的 `ContentChunk`。

> 结论：
> - 并发模型统一采用 `asyncio.Semaphore(max_concurrent_api_calls)` + `asyncio.gather`。
> - 单个 PDF 内，多页并发，受全局配置限制，便于后续与 OCR QPS 限流对接。

### 1.4 Markdown 页码 & 元数据开关逻辑

文件：`app/core/common/markdown_generator.py`

#### 1.4.1 构造方式

在 `PDFConverter.convert()` 中：

```python
markdown_generator = MarkdownGenerator(
    include_metadata=options.get('include_metadata', True),
    no_pagination_and_metadata=options.get('no_pagination_and_metadata', False),
)
markdown = markdown_generator.generate(content_chunks, pdf_info)
```

两个关键参数：

- `include_metadata: bool = True`
  - 是否在文首写入元数据（YAML 风格 front matter）。
- `no_pagination_and_metadata: bool = False`
  - 若为 `True`，**优先级高于** `include_metadata`：
    - 不输出元数据；
    - 不输出每页标记与分隔线；
    - 直接将所有 `ContentChunk` 智能拼接为一个连续 Markdown 文本。

#### 1.4.2 普通模式（带页码/可选元数据）

`MarkdownGenerator.generate(content_chunks, file_info)` 默认流程：

1. 若 `no_pagination_and_metadata` 为 `False`：
   - 若 `include_metadata` 为 `True`：
     - 调用 `_generate_metadata(file_info)` 输出：
       ```yaml
       ---
       title: <PDF 标题或默认 "Converted Document">
       pages: <总页数>
       pdf_type: <PDFType>
       generated_at: <ISO 时间戳>
       ---
       ```
2. 对每个 `ContentChunk`：
   - 先插入页面标记：
     ```html
     <!-- Page {page_number} ({chunk_type}) -->
     ```
   - 再追加该页内容 `chunk.content`。
   - 末尾加一个分隔符：`---`。
3. 对整个 Markdown 调用 `post_process()`：
   - `ContentCleaner.remove_special_markers`；
   - `clean_markdown`；
   - `normalize_whitespace`。

> 此模式适合“带分页信息 + 元数据”的场景，便于调试和追踪每页渲染情况。

#### 1.4.3 无分页模式（不带页码 & 元数据）

当 `no_pagination_and_metadata=True` 时：

- 直接走 `_generate_unpaginated(content_chunks)`：
  - 不输出任何 front matter。
  - 不输出页面标记和 `---` 分隔线。
  - 仅按照内容自然拼接，末尾有简单的“句尾标点 + 换行”智能规则：
    - 若当前 `chunk` 内容最后一个字符是句号/问号/感叹号（中英），则在后面插入一个换行，增强可读性。
  - 最后仍走 `post_process()` 清理格式。

> 此模式更接近日常阅读体验，适合作为“整篇文章”直接展示给用户。

---

## 二、任务管理与 API 时序

### 2.1 任务生命周期（TaskManager）

文件：`app/services/conversion/task_manager.py`

- 存储方式：
  - 使用内存字典 `self._tasks: Dict[str, Task]` 保存任务，进程重启后会丢失（为后续持久化预留空间）。

- 创建任务 `create_task(filename, file_path, file_type)`：
  - 生成 `task_id = "task_" + uuid4().hex[:12]`。
  - 初始化 `Task`：
    - `status = TaskStatus.PENDING`；
    - `progress = 0`；
    - `current_page = 0`、`total_pages = 0` 等。

- 状态更新：
  - `update_task_status(task_id, status)`：修改状态并更新时间，若状态为 `COMPLETED` 则记录 `completed_at`。
  - `update_task_progress(task_id, current_page, total_pages)`：调用 `Task.update_progress` 计算进度百分比。
  - `complete_task(task_id, result_path, markdown_content, metadata)`：封装为 `Task.mark_completed(...)`，并记录结果路径、内容、元数据。
  - `fail_task(task_id, error_message)`：调用 `Task.mark_failed`，状态置为 `FAILED` 并记录错误信息。

> 当前实现中，页面级进度更新尚未在 PDF 处理流程里显式调用，但接口已经预留（方便后续与 Celery、分步进度对接）。

### 2.2 同步转换 API：`POST /api/v1/convert`

文件：`app/api/v1/endpoints/convert.py`

1. 参数：
   - `file: UploadFile`（必填）；
   - `options: Optional[str]`，JSON 字符串，映射到 `ConvertOptions`。

2. 校验：
   - 文件名不能为空。
   - 读取整个文件内容计算大小，与 `pdf_max_size_mb` 比较；超限返回 `413`。

3. 转换选项解析：
   - 若传入 `options`，用 `json.loads` 解析，再构造 `ConvertOptions(**options_dict)`。
   - 若解析失败，返回 `400`。

4. 文件保存：
   - 生成 `temp_task_id = "temp_" + uuid4().hex[:12]`。
   - 使用 `FileService.save_upload_file(file, temp_task_id)` 保存到上传目录。

5. 调用转换服务：
   - `result = await ConversionService.convert(file_path, file.filename, convert_options.model_dump())`。

6. 组装响应 `ConvertSyncResponse`：
   - `success = True`；
   - `task_id = result['task_id']`；
   - `message = "文件转换完成"`；
   - `file_type = result['metadata'].get('file_type', 'unknown')`（当前元数据中主要是 `pdf_type`，后续可按需统一命名）；
   - `markdown_content = result['markdown_content']`；
   - `download_url = "/api/v1/download/{task_id}"`；
   - `metadata`：
     - `pages_processed` ← `total_pages`；
     - `ocr_pages`、`text_pages`；
     - `processing_time`；
     - `file_size`（输出文件大小）。

7. 异常处理：
   - `HTTPException` 直接抛出；
   - `BaseAppException` 转换为 500，`detail = e.to_dict()`；
   - 其他异常包装为 `INTERNAL_ERROR`。

### 2.3 状态查询与结果下载 API

文件：`app/api/v1/endpoints/status.py`

1. `GET /api/v1/status/{task_id}`：
   - 新建 `ConversionService`，调用 `get_task_status(task_id)`：
     - 返回结构：`{ task_id, status, progress{ current_page, total_pages, percentage }, result?, error? }`。
   - 封装为 `StatusResponse`：
     - `success = True`；
     - 填充 `status`、`progress`、`result`、`error`。
   - 若 `TaskNotFoundException` → 返回 404；
   - 其他异常 → 500 + `INTERNAL_ERROR`。

2. `GET /api/v1/download/{task_id}`：
   - 使用 `FileService.get_file_path(task_id, is_output=True)` 找到 Markdown 输出文件路径。
   - 若文件不存在 → 返回 404，`code = FILE_NOT_FOUND`。
   - 若存在 → 用 `FileResponse` 直接返回，`media_type="text/markdown"`。

### 2.4 时序图（文字版）

**场景：上传一个 PDF 并获取结果**

1. 客户端：`POST /api/v1/convert (file=example.pdf)`。
2. `convert` 接口：
   - 验证文件 & 解析 `options`；
   - 调用 `FileService.save_upload_file` 保存上传文件；
   - 调用 `ConversionService.convert(file_path, filename, options)`。
3. `ConversionService.convert`：
   - `FileTypeDetector.detect(file_path)` → `FileType.PDF`；
   - `TaskManager.create_task(...)` → 生成 `task_id`，状态 `PENDING`；
   - `update_task_status(task_id, PROCESSING)`；
   - `ConverterFactory.create_converter(FileType.PDF)` → `PDFConverter`；
   - `PDFConverter.convert(file_path, options)`：
     - `PDFAnalyzer.analyze(file_path)` → `PDFInfo(pdf_type, pages, metadata, ...)`；
     - `_select_processor(pdf_type)` → `ImagePDFProcessor` / `MixedPDFProcessor`；
     - `processor.process(file_path, pdf_info)`：并发处理各页，得到 `List[ContentChunk]`；
     - `MarkdownGenerator.generate(content_chunks, pdf_info)` → `markdown`；
     - 封装 `ConversionResult`（markdown + 元数据）。
   - `FileService.save_output_file(markdown, task_id, filename)` → 输出 Markdown 文件路径；
   - 统计耗时 & 输出文件大小，调用 `TaskManager.complete_task(...)`；
   - 返回 `{ task_id, status='completed', markdown_content, output_path, metadata }` 给 `convert` 接口。
4. `convert` 接口：
   - 返回 `ConvertSyncResponse`（含 `markdown_content` 和 `download_url`）。
5. 客户端后续可调用：
   - `GET /api/v1/status/{task_id}` 查询状态；
   - `GET /api/v1/download/{task_id}` 下载 Markdown 文件。

---

## 三、图片压缩脚本能力梳理（WebP）

文件：`proc_image/smallimg/webp_compress.py`

### 3.1 功能概览

- 使用 `pyvips` 高效处理图片，批量转换为有损 WebP：
  - 支持输入格式（不区分大小写）：
    - `.jpg` / `.jpeg` / `.png` / `.tif` / `.tiff` / `.bmp` / `.webp` / `.heic` / `.heif` / `.gif`（动图会被跳过）。
  - 自动：
    - EXIF 自动旋转（`maybe_autorotate`）。
    - 转换为 sRGB 色彩空间（`ensure_srgb`）。
    - 先整数缩小（`shrink`）再连续缩放（`resize`，LANCZOS3 内核），保证质量与性能。
  - 输出为 WebP，有损压缩，尽量去除元数据（strip）。

### 3.2 关键函数与参数

1. `process_one(in_path, out_path, max_w, max_h, quality, overwrite)`：
   - `max_w: int` / `max_h: int`
     - 最大宽高约束（默认在 CLI 中为 `1920x1080`）。
   - `quality: int`
     - WebP 质量，0–100，默认 CLI 里为 `90`（注释里写“默认 85”，但实际参数是 90，可在后续 API 统一）。
   - `overwrite: bool`
     - 输出文件存在时是否覆盖。
   - 处理流程：
     - 若输出文件已存在且不覆盖 → 直接返回 True。
     - `pyvips.Image.new_from_file(..., access="sequential")` 顺序读取大图。
     - `is_animated(image)` 检测多帧/动图（`n_pages > 1`），动图跳过（打印 `[SKIP]`）。
     - `maybe_autorotate(image)` 按 EXIF 方向自动旋转一次。
     - `ensure_srgb(image)` 转换到 sRGB，避免 ICC 丢失导致色偏。
     - `resize_to_box(image, max_w, max_h)`：
       - 若原图已不超过最大尺寸则不缩放。
       - 否则先尝试整数缩放 `shrink`，再按比例 `resize` 到不超过目标盒子。
     - `save_webp(image, out_path, quality)`：
       - 优先 `image.write_to_file(out_path, Q=quality, strip=True)`；
       - 失败则尝试 `image.webpsave(..., strip=True)`；
       - 再次失败则去掉 `strip` 兜底。

2. CLI 参数（`main()`）：

- `input_dir`（位置参数，可选）
  - 待处理图片目录，默认：`D:/coding/proc_image/testimgs`。
- `--output-dir/-o`
  - 输出目录，默认是输入目录下的 `webp_output` 子目录。
- `--max-width`
  - 最大宽度，默认 `1920`。
- `--max-height`
  - 最大高度，默认 `1080`。
- `--quality/-q`
  - WebP 质量，0–100，默认 `90`。
- `--recurse`
  - 是否递归子目录，默认否。
- `--overwrite`
  - 输出文件已存在时是否覆盖，默认否。

> 对未来 API 的启示：
> - 可暴露的核心参数：`quality`、`max_width`、`max_height`；
> - 可进一步扩展：`target_size_kb`、`overwrite` 等高阶选项；
> - 底层实现已经验证在 1920×1080 / 质量 85–90 左右时，单图 200–300KB 内仍可保持较好可读性，适合作为默认策略。

---

## 四、小结（阶段 0 实施结果）

1. **PDF → Markdown 流程**：
   - 已明确从上传 → 类型分析 → 按页并发处理 → Markdown 生成 → 任务落盘的全链路。
   - PDF 类型由文本/图像分布决定，图像与表格统一视为“需要 OCR 的视觉内容”。
   - 并发模型基于 `asyncio.Semaphore(max_concurrent_api_calls)`，单文件内部按页并发，利于配额控制。
   - Markdown 输出支持“带页码/元数据”和“无分页纯内容”两种模式，通过 `include_metadata` 与 `no_pagination_and_metadata` 控制。

2. **任务管理 & API**：
   - 任务生命周期（PENDING → PROCESSING → COMPLETED/FAILED）清晰，暂存于内存，适合后续接入 Redis/DB 持久化。
   - 当前 `/convert` 为同步阻塞接口，适合中小型 PDF，后续可平滑扩展异步 Celery 版本 `/convert/async`。

3. **图片压缩脚本**：
   - `webp_compress.py` 已具备稳定的批量 WebP 压缩能力，支持自动旋转、sRGB、限制分辨率与质量。
   - 参数设计与未来 `ImageCompressOptions` 模型高度契合，可以较为直接地封装为 FastAPI API。

本笔记可作为后续阶段（目录规范化、图片压缩 API、MinerU 接入、Celery 异步化等）的设计基础。