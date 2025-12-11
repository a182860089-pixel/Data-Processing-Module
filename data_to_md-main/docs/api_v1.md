# API v1 接口文档

## 概述

本文档描述了数据转换平台 API v1 的所有接口规范。

### 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8

### 统一响应格式

所有 API 响应遵循统一格式：

```json
{
  "success": true/false,
  "data": { /* 响应数据 */ },
  "message": "提示信息",
  "error": { /* 错误信息（仅失败时） */ }
}
```

**字段说明**:
- `success` (boolean): 请求是否成功
- `data` (object, optional): 响应数据对象
- `message` (string): 人类可读的提示信息
- `error` (object, optional): 错误详情（仅在 `success=false` 时出现）

---

## 1. 健康检查

### 1.1 服务健康检查

检查服务运行状态。

**请求**:
```
GET /api/v1/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-06T09:45:00Z",
  "version": "1.0.0",
  "services": {
    "deepseek_api": "available",
    "storage": "available"
  }
}
```

---

## 2. PDF 转换服务

### 2.1 转换 PDF 为 Markdown (同步)

上传 PDF 文件并同步转换为 Markdown 格式。

**请求**:
```
POST /api/v1/convert
```

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | PDF 文件 |
| options | JSON String | 否 | 转换选项 |

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
  "markdown_content": "# 转换后的内容...",
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

---

### 2.2 查询任务状态

**请求**:
```
GET /api/v1/status/{task_id}
```

**响应示例**:
```json
{
  "success": true,
  "task_id": "task_abc123",
  "status": "completed",
  "progress": {
    "current_page": 10,
    "total_pages": 10,
    "percentage": 100
  }
}
```

---

### 2.3 下载转换结果

**请求**:
```
GET /api/v1/download/{task_id}
```

---

## 3. 图片压缩服务 (阶段2实现)

### 3.1 压缩图片

将图片压缩为WebP格式。

**请求**:
```
POST /api/v1/image/compress
Content-Type: multipart/form-data
```

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 图片文件 |
| options | JSON String | 否 | 压缩选项 |

**压缩选项**:
```json
{
  "quality": 90,
  "max_width": 1920,
  "max_height": 1080,
  "target_size_kb": 250
}
```

**支持的格式**: JPEG, PNG, TIFF, BMP, WebP, HEIC, GIF(静态)

**响应示例**:
```json
{
  "success": true,
  "message": "图片压缩完成",
  "filename": "photo.jpg",
  "output_filename": "photo.webp",
  "download_url": "/api/v1/image/download/img_abc123",
  "metadata": {
    "original_size": 2048576,
    "output_size": 256000,
    "compression_ratio": 87.5,
    "original_dimensions": "3840x2160",
    "output_dimensions": "1920x1080",
    "quality": 90
  }
}
```

---

### 3.2 下载压缩图片

**请求**:
```
GET /api/v1/image/download/{task_id}
```

---

### 3.3 服务状态查询

**请求**:
```
GET /api/v1/image/status
```

**响应示例**:
```json
{
  "success": true,
  "service": "image_compression",
  "status": "operational",
  "message": "图片压缩服务已启用（阶段2）",
  "supported_formats": ["jpg", "jpeg", "png", "tiff", "bmp", "webp", "heic", "gif"]
}
```

---

## 4. 批量转换服务 (阶段7实现)

### 4.1 服务状态查询

**请求**:
```
GET /api/v1/batch/status
```

**响应示例**:
```json
{
  "success": true,
  "service": "batch_conversion",
  "status": "not_implemented",
  "message": "批量转换功能将在阶段7实现"
}
```

---

## 5. 开发路线图

| 阶段 | 功能 | 状态 |
|------|------|------|
| 阶段0 | 基础 PDF 转换 | ✅ 已完成 |
| 阶段1 | API 规范化 | ✅ 已完成 |
| 阶段2 | 图片压缩 API | ✅ 已完成 |
| 阶段3 | PDF 功能增强 | 📋 待开发 |
| 阶段4 | MinerU 双引擎 | 📋 待开发 |
| 阶段5 | OCR 负载均衡 | 📋 待开发 |
| 阶段6 | Celery 异步队列 | 📋 待开发 |
| 阶段7 | 批量处理 | 📋 待开发 |
| 阶段8 | 压测优化 | 📋 待开发 |
