# Data Processing Module - 数据处理平台

基于 FastAPI 构建的多功能数据转换平台，支持 PDF 转 Markdown、多格式文件转换、图片压缩、微信文章爬取等功能。

## 🚀 功能特性

### 已实现功能

- ✅ **PDF → Markdown 转换**
  - 支持纯图片 PDF、图文混排 PDF、纯文本 PDF
  - 使用 DeepSeek-OCR 云端 API 进行 OCR 识别
  - 自动检测 PDF 类型并选择最优处理策略
  - 并发处理多页 PDF，提高转换效率
  - 可配置的输出模式（带分页/无分页、元数据开关）

- ✅ **多格式文件 → PDF 转换**
  - Office 文档：DOCX、PPTX、XLSX
  - 图片格式：JPG、PNG、GIF、TIFF、BMP、WebP、HEIC
  - 自动文件类型检测

- ✅ **图片压缩服务**
  - 压缩为 WebP 格式
  - 支持质量、尺寸控制
  - 支持多种输入格式

- ✅ **微信公众号文章爬虫**
  - 基于 crawl4ai 实现
  - 自动提取正文并转换为 Markdown
  - 支持单篇/批量爬取

- ✅ **异步任务处理**
  - Celery + Redis 异步任务队列
  - 任务状态实时查询
  - 批量文件并发处理

### 规划功能

- 📋 MinerU 双引擎 OCR 支持
- 📋 OCR 引擎负载均衡
- 📋 并发测试、压测与优化

## 🛠 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **PDF 处理**: PyMuPDF (fitz)
- **图像处理**: Pillow, pyvips
- **OCR 服务**: DeepSeek-OCR (通过 OpenAI SDK)
- **Office 处理**: python-pptx, python-docx, openpyxl
- **PDF 生成**: reportlab, fpdf2
- **异步队列**: Celery + Redis
- **网页爬取**: crawl4ai
- **数据验证**: Pydantic v2

## 📁 项目结构

```
Data Processing Module/
├── data_to_md-main/          # 核心后端服务
│   ├── app/
│   │   ├── api/v1/endpoints/ # API 端点
│   │   │   ├── convert.py    # 转换接口
│   │   │   ├── image.py      # 图片压缩接口
│   │   │   ├── batch.py      # 批量转换接口
│   │   │   ├── crawler.py    # 爬虫接口
│   │   │   └── status.py     # 状态查询
│   │   ├── core/             # 核心转换器
│   │   │   ├── converters/   # 各类转换器实现
│   │   │   └── factory/      # 工厂模式
│   │   ├── services/         # 业务服务
│   │   │   ├── conversion/   # 转换服务
│   │   │   ├── crawler/      # 爬虫服务
│   │   │   └── queue/        # 任务队列
│   │   ├── models/           # 数据模型
│   │   └── config.py         # 配置管理
│   ├── storage/              # 存储目录
│   └── requirements.txt      # 依赖列表
├── proc_image/               # 图片处理前端
├── tests/                    # 测试目录
├── START_ALL.ps1             # 一键启动脚本
└── 开发计划书.md              # 详细开发计划
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd data_to_md-main
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

主要配置项：
- `DEEPSEEK_API_KEY`: DeepSeek API 密钥
- `DEEPSEEK_BASE_URL`: API 基础 URL
- `CELERY_BROKER_URL`: Redis 地址（异步任务需要）

### 3. 启动服务

**方式一：使用启动脚本（推荐）**
```powershell
./START_ALL.ps1
```

**方式二：手动启动**
```bash
# 启动后端 API
cd data_to_md-main
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动 Celery Worker（需要 Redis）
celery -A celery_worker.celery_app worker -l info -P solo --concurrency=2
```

### 4. 访问服务

- 📌 后端 API: http://localhost:8000
- 📌 API 文档: http://localhost:8000/docs
- 📌 前端页面: http://localhost:5173

## 📖 API 接口

### PDF/文件转换

```bash
# 同步转换
POST /api/v1/convert

# 异步转换
POST /api/v1/convert/async

# 查询状态
GET /api/v1/status/{task_id}

# 下载结果
GET /api/v1/download/{task_id}
```

### 图片压缩

```bash
POST /api/v1/image/compress
```

### 微信文章爬取

```bash
# 单篇爬取
POST /api/v1/crawl/wechat

# 批量爬取
POST /api/v1/crawl/wechat/batch
```

### 批量转换

```bash
# 提交批量任务
POST /api/v1/batch/convert

# 查询批次状态
GET /api/v1/batch/status/{batch_id}
```

## 📝 使用示例

### Python 示例

```python
import requests

# PDF 转 Markdown
with open('example.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/convert',
        files={'file': f},
        data={'options': '{"dpi": 144}'}
    )
    result = response.json()
    print(result['markdown_content'])
```

### cURL 示例

```bash
# 转换 PDF
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@example.pdf" \
  -F 'options={"dpi": 144}'

# 压缩图片
curl -X POST "http://localhost:8000/api/v1/image/compress" \
  -F "file=@image.jpg" \
  -F 'options={"quality": 85}'
```

## 📋 开发路线图

| 阶段 | 功能 | 状态 |
|------|------|------|
| 阶段 0-1 | 项目梳理与 API 规范化 | ✅ 已完成 |
| 阶段 2 | 图片压缩 WebP API | ✅ 已完成 |
| 阶段 3 | PDF→Markdown 功能增强 | ✅ 已完成 |
| 阶段 3.5 | 多格式文件→PDF 转换 | ✅ 已完成 |
| 阶段 4 | MinerU 双引擎 OCR | 📋 待开发 |
| 阶段 5 | OCR 引擎负载均衡 | 📋 待开发 |
| 阶段 6 | Celery 异步任务队列 | ✅ 已完成 |
| 阶段 7 | 批量上传 & 并发处理 | ✅ 已完成 |
| 阶段 8 | 并发测试与优化 | 📋 待开发 |

详细开发计划请查看: [开发计划书.md](开发计划书.md)

## 📚 相关文档

- [Swagger 测试指南](Swagger测试指南.md)
- [前端接入方案](前端接入方案(3.5阶段).md)
- [阶段 3.5 开发总结](阶段3.5开发总结.md)
- [阶段 3.5 测试报告](阶段3.5测试报告.md)

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
