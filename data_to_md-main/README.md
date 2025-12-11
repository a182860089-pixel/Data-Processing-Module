# PDF to Markdown 智能转换系统

基于 FastAPI 和 DeepSeek-OCR 的 PDF 到 Markdown 转换系统。

## 功能特性

### 当前功能 (阶段0-3)
- ✅ 支持纯图片 PDF、图文混排 PDF、纯文本 PDF
- ✅ 使用 DeepSeek-OCR 云端 API 进行 OCR 识别
- ✅ 自动检测 PDF 类型并选择最优处理策略
- ✅ 并发处理多页 PDF，提高转换效率
- ✅ RESTful API 接口，易于集成
- ✅ 完整的错误处理和日志记录
- ✅ 统一的响应格式规范
- ✅ 图片压缩为WebP格式，支持质量、尺寸控制
- ✅ 支持可配置的 PDF 输出模式（带分页/无分页、元数据开关）
- ✅ 改进文本提取与段落识别，优化 Markdown 可读性

### 规划功能
- 📋 MinerU 双引擎 OCR 支持 (阶段4)
- 📋 OCR 引擎负载均衡 (阶段5)
- 📋 Celery 异步任务队列 (阶段6)
- 📋 批量文件并发处理 (阶段7)
- 📋 并发测试、压测与优化 (阶段8)
## 技术栈

- **框架**: FastAPI + Uvicorn
- **PDF 处理**: PyMuPDF (fitz)
- **图像处理**: Pillow
- **OCR 服务**: DeepSeek-OCR (通过 OpenAI SDK)
- **数据验证**: Pydantic v2

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并根据需要修改：

```bash
cp .env.example .env
```

主要配置项：
- `DEEPSEEK_API_KEY`: DeepSeek API 密钥
- `DEEPSEEK_BASE_URL`: API 基础 URL
- `DEEPSEEK_MODEL`: 模型名称
- `PDF_RENDER_DPI`: PDF 渲染 DPI（默认 144）
- `PDF_MAX_SIZE_MB`: 最大文件大小（默认 50MB）

### 3. 启动服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或者直接运行：

```bash
python app/main.py
```

### 4. 访问 API 文档

打开浏览器访问：http://localhost:8000/docs

## API 接口

### 1. 健康检查

```bash
GET /api/v1/health
```

### 2. 转换 PDF

```bash
POST /api/v1/convert
```

**请求参数**:
- `file`: PDF 文件（multipart/form-data）
- `options`: 转换选项（JSON 字符串，可选）

**转换选项**:
```json
{
  "dpi": 144,
  "include_metadata": true,
  "max_pages": 100
}
```

**响应示例**:
```json
{
  "success": true,
  "task_id": "task_abc123",
  "message": "文件转换完成",
  "filename": "example.pdf",
  "file_type": "pdf",
  "markdown_content": "# 转换后的 Markdown 内容...",
  "download_url": "/api/v1/download/task_abc123",
  "metadata": {
    "pages_processed": 10,
    "ocr_pages": 5,
    "text_pages": 5,
    "processing_time": 15.5,
    "file_size": 12345
  }
}
```

### 3. 查询任务状态

```bash
GET /api/v1/status/{task_id}
```

### 4. 下载结果

```bash
GET /api/v1/download/{task_id}
```

### 5. 压缩图片 (阶段2)

```bash
POST /api/v1/image/compress
```

**请求参数**:
- `file`: 图片文件（multipart/form-data）
- `options`: 压缩选项（JSON字符串，可选）

**压缩选项**:
```json
{
  "quality": 90,
  "max_width": 1920,
  "max_height": 1080
}
```

**支持格式**: JPEG, PNG, TIFF, BMP, WebP, HEIC, GIF(静态)

### 6. 图片压缩服务状态

```bash
GET /api/v1/image/status
```

### 6. 批量转换服务状态 (阶段7实现)

```bash
GET /api/v1/batch/status
```

> **详细的 API 文档**: 请参阅 [docs/api_v1.md](docs/api_v1.md)

## 使用示例

### Python 示例

```python
import requests

# 转换 PDF
with open('example.pdf', 'rb') as f:
    files = {'file': f}
    response = requests.post(
        'http://localhost:8000/api/v1/convert',
        files=files
    )
    result = response.json()
    print(f"任务ID: {result['task_id']}")
    print(f"Markdown 内容: {result['markdown_content']}")
```

### cURL 示例

```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@example.pdf" \
  -F 'options={"dpi": 144, "include_metadata": true}'
```

## 测试

运行测试脚本：

```bash
python test_api.py
```

按提示输入 PDF 文件路径进行测试。

## 项目结构

```
data_to_md/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── convert.py      # 转换接口
│   │           ├── health.py       # 健康检查
│   │           ├── status.py       # 状态查询
│   │           ├── image.py        # 图片压缩接口 (阶段2)
│   │           └── batch.py        # 批量转换接口 (阶段7)
│   ├── core/
│   │   ├── base/                   # 基础抽象类
│   │   ├── converters/
│   │   │   └── pdf/                # PDF 转换器
│   │   ├── factory/                # 工厂模式
│   │   └── common/                 # 通用工具
│   ├── services/
│   │   ├── conversion/             # 转换服务
│   │   ├── storage/                # 存储服务
│   │   └── external/               # 外部服务
│   ├── models/                     # 数据模型
│   ├── exceptions/                 # 异常定义
│   ├── config.py                   # 配置管理
│   └── main.py                     # 主应用
├── storage/                        # 存储目录
│   ├── uploads/                    # 上传文件
│   ├── outputs/                    # 输出文件
│   └── logs/                       # 日志文件
├── requirements.txt                # 依赖列表
├── .env.example                    # 环境变量示例
├── test_api.py                     # 测试脚本
└── README.md                       # 项目文档
```

## 处理流程

1. **文件上传**: 接收 PDF 文件并保存到临时目录
2. **类型检测**: 分析 PDF 类型（纯图片/图文混排/纯文本）
3. **内容处理**:
   - 纯图片 PDF: 所有页面使用 OCR
   - 图文混排 PDF: 有图像的页面使用 OCR，无图像的页面提取文本层
   - 纯文本 PDF: 直接提取文本层
4. **Markdown 生成**: 合并所有页面内容，生成最终 Markdown
5. **结果返回**: 返回 Markdown 内容和下载链接

## 配置说明

### PDF 处理配置

- `PDF_RENDER_DPI`: 渲染 DPI，影响 OCR 质量（72-300，推荐 144）
- `PDF_TEXT_THRESHOLD`: 文本阈值，判断页面是否有有效文本（默认 10 字符）
- `PDF_MAX_SIZE_MB`: 最大文件大小限制
- `PDF_MAX_PAGES`: 最大处理页数限制

### API 配置

- `API_TIMEOUT`: API 超时时间（秒）
- `API_MAX_RETRIES`: 最大重试次数
- `MAX_CONCURRENT_API_CALLS`: 最大并发 API 调用数

### 存储配置

- `UPLOAD_DIR`: 上传文件目录
- `OUTPUT_DIR`: 输出文件目录
- `FILE_RETENTION_DAYS`: 文件保留天数

## 注意事项

1. **API 密钥**: 确保配置了有效的 DeepSeek API 密钥
2. **文件大小**: 大文件可能需要较长处理时间
3. **并发限制**: 根据 API 配额调整并发数
4. **存储空间**: 定期清理过期文件

## 故障排查

### 服务无法启动

- 检查端口 8000 是否被占用
- 检查依赖是否正确安装
- 查看日志文件 `storage/logs/`

### 转换失败

- 检查 PDF 文件是否损坏
- 检查 API 密钥是否有效
- 查看错误信息和日志

### OCR 质量不佳

- 尝试提高 `PDF_RENDER_DPI` 值
- 检查原始 PDF 图像质量

## 开发路线图

| 阶段 | 功能 | 难度 | 状态 |
|------|------|------|------|
| 阶段0 | 现有项目梳理与基础清理 | ★☆☆☆☆ | ✅ 已完成 |
| 阶段1 | API 与目录结构规范化 | ★☆☆☆☆ | ✅ 已完成 |
| 阶段2 | 图片压缩 WebP API 封装 | ★★☆☆☆ | ✅ 已完成 |
| 阶段3 | PDF→Markdown 现有功能增强 | ★★☆☆☆ | 📋 待开发 |
| 阶段4 | MinerU 接入与双引擎封装 | ★★★☆☆ | 📋 待开发 |
| 阶段5 | OCR 引擎轮询与负载均衡 | ★★★★☆ | 📋 待开发 |
| 阶段6 | Celery 异步任务队列接入 | ★★★★☆ | 📋 待开发 |
| 阶段7 | 批量上传 & 并发处理 | ★★★★★ | 📋 待开发 |
| 阶段8 | 并发测试、压测与优化 | ★★★★★ | 📋 待开发 |

详细开发计划请查看: [开发计划书.md](开发计划书.md)

---

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。

