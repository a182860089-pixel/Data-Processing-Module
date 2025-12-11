# PDF to Markdown 转换系统 - 产品需求文档 (PRD)

## 文档版本

- **版本**: v1.1
- **日期**: 2025-11-15
- **作者**: 开发团队
- **更新内容**: 新增第七章"多文件批量上传并发处理方案"

---

## 一、多 PDF 并发处理架构设计

### 1.1 当前架构分析

#### 现状

- **请求处理模式**: 同步等待模式
- **单 PDF 内并发**: 使用 asyncio.Semaphore 限制单个 PDF 内的页面并发数（默认 3 个页面）
- **多 PDF 并发**: 无全局限制，所有请求直接进入处理流程

#### 存在的问题

1. **无全局任务队列**: 20 个 PDF 同时上传时，会同时进入处理流程
2. **资源竞争严重**: 可能同时发起 20×3=60 个 OCR API 调用
3. **API 限流风险**: 超过服务商的并发限制会导致请求失败
4. **内存压力大**: 多个大 PDF 同时加载到内存可能导致 OOM
5. **客户端超时**: 请求需要等待整个 PDF 处理完成才返回，大文件可能超时
6. **无进度反馈**: 客户端无法获知处理进度

#### 瓶颈分析

```
请求层面: 无限制 → 20个PDF同时处理
  ↓
PDF层面: 无限制 → 20个PDF各自处理
  ↓
页面层面: 有限制 → 每个PDF内最多3个页面并发
  ↓
API层面: 过载 → 同时60个API调用（超出限制）
```

---

### 1.2 异步任务队列架构设计（方案 2）

#### 设计目标

1. **请求立即返回**: 上传后立即返回 task_id，不阻塞客户端
2. **全局并发控制**: 限制同时处理的 PDF 文件数量
3. **进度可查询**: 客户端可以实时查询任务状态和进度
4. **资源可控**: 避免内存溢出和 API 限流
5. **易于扩展**: 为后续引入专业任务队列（Celery）预留接口

#### 核心思路

使用 **FastAPI BackgroundTasks** 实现轻量级异步任务队列

---

## 二、技术方案详细设计

### 2.1 架构改造思路

#### 整体流程

```
客户端上传PDF
  ↓
API接收请求 → 创建任务 → 立即返回task_id
  ↓
后台任务队列 → 按顺序/优先级处理
  ↓
客户端轮询 /status/{task_id} 查询进度
  ↓
处理完成 → 客户端下载结果
```

#### 关键组件

**1. 任务状态管理器增强**

- 扩展现有 TaskManager
- 增加任务状态: QUEUED（排队中）、PROCESSING（处理中）、COMPLETED（已完成）、FAILED（失败）
- 增加进度跟踪: 当前页/总页数、百分比
- 增加队列管理: 等待队列、处理队列

**2. 全局并发控制器**

- 使用全局信号量限制同时处理的 PDF 数量
- 配置参数: MAX_CONCURRENT_PDF_TASKS（建议 3-5 个）
- 超出限制的任务进入等待队列

**3. 后台任务执行器**

- 使用 FastAPI BackgroundTasks 执行转换任务
- 任务执行时获取全局信号量
- 执行完成后释放信号量，触发下一个任务

**4. 进度回调机制**

- 在页面处理过程中更新任务进度
- 记录当前处理到第几页
- 计算完成百分比

---

### 2.2 API 接口改造思路

#### 转换接口 POST /api/v1/convert

**改造前（同步模式）**

- 接收文件 → 处理 → 等待完成 → 返回结果
- 问题: 客户端长时间等待，大文件可能超时

**改造后（异步模式）**

- 接收文件 → 创建任务 → 添加到后台队列 → 立即返回 task_id
- 优势: 请求秒级返回，不阻塞客户端

**返回数据结构**

```
{
  "success": true,
  "task_id": "task_abc123",
  "status": "queued",  // 或 "processing"
  "message": "任务已创建，正在处理中",
  "queue_position": 3,  // 队列中的位置（可选）
  "estimated_time": 120  // 预估处理时间（秒，可选）
}
```

#### 状态查询接口 GET /api/v1/status/{task_id}

**增强功能**

- 返回详细的任务状态
- 返回处理进度（当前页/总页数）
- 返回预估剩余时间
- 返回错误信息（如果失败）

**返回数据结构**

```
{
  "task_id": "task_abc123",
  "status": "processing",  // queued/processing/completed/failed
  "progress": {
    "current_page": 15,
    "total_pages": 100,
    "percentage": 15,
    "pages_per_minute": 5  // 处理速度
  },
  "created_at": "2025-11-14T10:00:00",
  "started_at": "2025-11-14T10:01:00",
  "estimated_completion": "2025-11-14T10:20:00",
  "result": null  // 完成后包含下载链接
}
```

#### 下载接口 GET /api/v1/download/{task_id}

**保持不变**

- 任务完成后可下载结果文件

---

### 2.3 核心模块改造思路

#### ConversionService 改造

**改造点 1: 拆分同步和异步方法**

- `convert_sync()`: 原有的同步转换逻辑（内部使用）
- `convert_async()`: 新增的异步入口，用于后台任务

**改造点 2: 添加进度回调**

- 在处理每个页面后调用回调函数
- 更新 TaskManager 中的任务进度
- 支持外部监听进度变化

**改造点 3: 全局并发控制**

- 创建全局信号量（类级别变量）
- 在 convert_async() 中获取信号量
- 处理完成后释放信号量

#### TaskManager 增强

**新增功能 1: 队列管理**

- 维护等待队列（FIFO 或优先级队列）
- 维护处理中任务列表
- 提供队列位置查询

**新增功能 2: 进度跟踪**

- 实时更新任务进度
- 计算处理速度（页/分钟）
- 预估剩余时间

**新增功能 3: 任务清理**

- 定期清理已完成的旧任务
- 配置任务保留时间（默认 24 小时）
- 避免内存无限增长

#### PDF 处理器改造

**改造点: 添加进度回调**

- 在 \_process_page() 完成后调用回调
- 传递当前页码信息
- 不影响现有的并发处理逻辑

---

### 2.4 配置参数设计

#### 新增配置项

**并发控制**

- `MAX_CONCURRENT_PDF_TASKS`: 同时处理的 PDF 文件数（默认 3-5）
- `MAX_QUEUE_SIZE`: 最大队列长度（默认 100，超出则拒绝）
- `TASK_TIMEOUT`: 单个任务超时时间（默认 30 分钟）

**任务管理**

- `TASK_RETENTION_HOURS`: 任务保留时间（默认 24 小时）
- `TASK_CLEANUP_INTERVAL`: 清理间隔（默认 1 小时）
- `ENABLE_PROGRESS_TRACKING`: 是否启用进度跟踪（默认 true）

**性能优化**

- `QUEUE_CHECK_INTERVAL`: 队列检查间隔（默认 1 秒）
- `PROGRESS_UPDATE_INTERVAL`: 进度更新间隔（默认每页更新）

---

## 三、实现步骤规划

### 3.1 第一阶段：基础改造

**步骤 1: 增强 TaskManager**

- 添加 QUEUED 状态支持
- 实现进度跟踪方法
- 实现队列管理方法

**步骤 2: 添加全局并发控制**

- 在 ConversionService 中创建全局信号量
- 实现信号量获取和释放逻辑

**步骤 3: 改造 API 接口**

- 修改 /convert 接口使用 BackgroundTasks
- 增强 /status 接口返回进度信息
- 测试异步流程

### 3.2 第二阶段：进度跟踪

**步骤 4: 实现进度回调**

- 在 PDF 处理器中添加回调机制
- 在每页处理完成后更新进度
- 计算处理速度和预估时间

**步骤 5: 优化状态查询**

- 返回详细的进度信息
- 添加预估完成时间
- 添加队列位置信息

### 3.3 第三阶段：优化和监控

**步骤 6: 任务清理机制**

- 实现定时清理任务
- 清理过期的上传和输出文件
- 添加清理日志

**步骤 7: 监控和告警**

- 添加队列长度监控
- 添加处理速度监控
- 添加失败率监控

---

## 四、数据流设计

### 4.1 正常流程

```
1. 客户端上传PDF
   ↓
2. API创建Task（状态=QUEUED）
   ↓
3. 添加到BackgroundTasks
   ↓
4. 立即返回task_id给客户端
   ↓
5. 后台任务开始执行
   - 尝试获取全局信号量
   - 如果获取成功: 状态→PROCESSING，开始处理
   - 如果获取失败: 保持QUEUED，等待
   ↓
6. 处理过程中
   - 每处理完一页，更新进度
   - 客户端可随时查询状态
   ↓
7. 处理完成
   - 状态→COMPLETED
   - 释放信号量
   - 保存结果文件
   ↓
8. 客户端下载结果
```

### 4.2 并发控制流程

```
假设 MAX_CONCURRENT_PDF_TASKS = 3

时刻T0: 20个PDF同时上传
  ↓
Task 1-3: 立即获取信号量，状态→PROCESSING
Task 4-20: 无法获取信号量，状态→QUEUED
  ↓
时刻T1: Task 1 完成
  ↓
释放信号量 → Task 4 获取信号量，状态→PROCESSING
  ↓
时刻T2: Task 2 完成
  ↓
释放信号量 → Task 5 获取信号量，状态→PROCESSING
  ↓
... 依次处理，直到所有任务完成
```

---

## 五、客户端使用流程

### 5.1 推荐使用方式

**步骤 1: 上传文件**

```
POST /api/v1/convert
返回: {"task_id": "task_abc123", "status": "queued"}
```

**步骤 2: 轮询状态**

```
每隔2-5秒查询一次:
GET /api/v1/status/task_abc123

返回示例:
- 排队中: {"status": "queued", "queue_position": 5}
- 处理中: {"status": "processing", "progress": {"percentage": 35}}
- 已完成: {"status": "completed", "download_url": "..."}
- 失败: {"status": "failed", "error": "..."}
```

**步骤 3: 下载结果**

```
GET /api/v1/download/task_abc123
```

### 5.2 客户端示例伪代码

```
1. 上传文件，获取task_id
2. 循环查询状态:
   - 如果status=queued: 显示"排队中，位置X"
   - 如果status=processing: 显示进度条（X%）
   - 如果status=completed: 下载结果，退出循环
   - 如果status=failed: 显示错误，退出循环
3. 设置超时时间（如30分钟），超时则提示用户
```

---

## 六、性能和资源评估

### 6.1 资源消耗对比

**改造前（20 个 PDF 同时处理）**

- 并发 API 调用: 60 个（20×3）
- 内存占用: 20 个 PDF 同时加载
- 风险: API 限流、内存溢出

**改造后（MAX_CONCURRENT_PDF_TASKS=3）**

- 并发 API 调用: 9 个（3×3）
- 内存占用: 3 个 PDF 同时加载
- 优势: 可控、稳定

### 6.2 处理时间评估

**假设条件**

- 单页 OCR 时间: 2 秒
- 单个 PDF: 100 页
- 页面并发数: 3

**单个 PDF 处理时间**

- 100 页 ÷ 3 并发 × 2 秒 ≈ 67 秒

**20 个 PDF 总时间**

- 改造前（无控制）: 理论 67 秒，实际可能因 API 限流更长或失败
- 改造后（3 并发）: 67 秒 × (20÷3) ≈ 7 分钟

**结论**: 虽然总时间增加，但稳定性和成功率大幅提升

---

## 七、多文件批量上传并发处理方案

### 7.1 需求背景

#### 业务场景

用户需要一次性上传多个 PDF 文档（如 5-20 个），系统需要并发处理这些文档，提升批量处理效率。

#### 核心需求

1. **批量上传**: 支持一次性上传多个文件（建议限制 5-20 个）
2. **并发处理**: 多个文件同时进入后台任务队列并发处理
3. **统一管理**: 为批量上传创建批次 ID，方便统一查询和管理
4. **进度追踪**: 可查询批次整体进度和单个文件进度
5. **结果下载**: 支持单个文件下载和批量打包下载

---

### 7.2 技术方案设计

#### 7.2.1 批量上传接口设计

**新增接口: POST /api/v1/convert/batch**

**请求方式**

- Content-Type: multipart/form-data
- 支持多个文件字段（files[]）
- 可选的批量转换选项（batch_options）

**请求参数**

- files: 文件列表（必填，最多 20 个）
- options: 转换选项 JSON（可选，应用于所有文件）
- batch_name: 批次名称（可选，用于标识）

**响应结构**

```
{
  "success": true,
  "batch_id": "batch_abc123",
  "message": "批量任务已创建",
  "total_files": 5,
  "tasks": [
    {
      "task_id": "task_001",
      "filename": "file1.pdf",
      "status": "queued",
      "queue_position": 1
    },
    {
      "task_id": "task_002",
      "filename": "file2.pdf",
      "status": "queued",
      "queue_position": 2
    }
    // ... 其他文件
  ],
  "batch_status_url": "/api/v1/batch/status/batch_abc123",
  "estimated_total_time": 600  // 预估总时间（秒）
}
```

**业务逻辑**

1. 接收多个文件上传
2. 验证文件数量（不超过最大限制）
3. 验证每个文件大小和类型
4. 生成批次 ID（batch_id）
5. 为每个文件创建独立的任务（task_id）
6. 将所有任务添加到后台队列
7. 立即返回批次信息和任务列表

---

#### 7.2.2 批次状态查询接口

**新增接口: GET /api/v1/batch/status/{batch_id}**

**响应结构**

```
{
  "success": true,
  "batch_id": "batch_abc123",
  "batch_name": "财务报表批量转换",
  "status": "processing",  // queued/processing/completed/partial_failed/failed
  "created_at": "2025-11-15T10:00:00",
  "total_files": 5,
  "completed_files": 2,
  "failed_files": 0,
  "processing_files": 2,
  "queued_files": 1,
  "progress_percentage": 40,
  "tasks": [
    {
      "task_id": "task_001",
      "filename": "file1.pdf",
      "status": "completed",
      "progress": 100,
      "download_url": "/api/v1/download/task_001"
    },
    {
      "task_id": "task_002",
      "filename": "file2.pdf",
      "status": "processing",
      "progress": 65,
      "current_page": 13,
      "total_pages": 20
    },
    {
      "task_id": "task_003",
      "filename": "file3.pdf",
      "status": "queued",
      "queue_position": 5
    }
    // ... 其他任务
  ],
  "estimated_completion": "2025-11-15T10:15:00"
}
```

**批次状态定义**

- `queued`: 所有任务都在排队
- `processing`: 至少有一个任务在处理中
- `completed`: 所有任务都已完成
- `partial_failed`: 部分任务失败，部分成功
- `failed`: 所有任务都失败

---

#### 7.2.3 批量下载接口

**新增接口: GET /api/v1/batch/download/{batch_id}**

**功能说明**

- 将批次中所有已完成的文件打包成 ZIP
- 返回 ZIP 文件供下载
- 文件名格式: `batch_{batch_id}_{timestamp}.zip`

**ZIP 内部结构**

```
batch_abc123_20251115.zip
├── file1.md
├── file2.md
├── file3.md
├── file4.md
├── file5.md
└── batch_summary.json  // 批次摘要信息
```

**batch_summary.json 内容**

```
{
  "batch_id": "batch_abc123",
  "batch_name": "财务报表批量转换",
  "total_files": 5,
  "successful_files": 4,
  "failed_files": 1,
  "created_at": "2025-11-15T10:00:00",
  "completed_at": "2025-11-15T10:12:00",
  "files": [
    {
      "filename": "file1.pdf",
      "output_filename": "file1.md",
      "status": "completed",
      "pages": 25,
      "processing_time": 45.2
    }
    // ... 其他文件信息
  ]
}
```

---

#### 7.2.4 数据模型设计

**BatchTask 模型（新增）**

- batch_id: 批次 ID
- batch_name: 批次名称
- task_ids: 任务 ID 列表
- total_files: 文件总数
- status: 批次状态
- created_at: 创建时间
- completed_at: 完成时间
- metadata: 批次元数据

**BatchManager 类（新增）**

- create_batch(): 创建批次
- get_batch(): 获取批次信息
- update_batch_status(): 更新批次状态
- get_batch_progress(): 计算批次进度
- list_batches(): 列出所有批次

---

#### 7.2.5 并发处理策略

**策略 1: 共享全局队列**

- 批量上传的多个文件进入同一个全局任务队列
- 与单文件上传的任务共享并发限制
- 优点: 实现简单，资源利用均衡
- 缺点: 批次内文件可能被其他任务插队

**策略 2: 批次优先处理（推荐）**

- 批次内的文件优先级高于单文件上传
- 批次内文件按顺序处理，但可并发
- 优点: 批次处理更快完成
- 缺点: 实现稍复杂

**推荐实现**

- 使用策略 1 作为初始版本
- 所有文件（批量和单个）进入统一队列
- 由全局信号量控制并发数（如 3-5 个）
- 批次只是逻辑分组，不影响调度

---

#### 7.2.6 文件保存和清理策略

**上传文件保存**

- 路径: `storage/uploads/batch_{batch_id}/`
- 每个批次创建独立目录
- 便于批量清理

**输出文件保存**

- 路径: `storage/outputs/batch_{batch_id}/`
- 保持与上传文件对应的目录结构
- 便于批量打包下载

**清理策略**

- 批次完成后保留 24 小时（可配置）
- 定时任务清理过期批次目录
- 清理时同时删除上传和输出文件

---

### 7.3 实现步骤

#### 第一阶段: 基础批量上传（1-2 天）

**步骤 1: 数据模型**

- 创建 BatchTask 模型
- 创建 BatchManager 类
- 扩展 TaskManager 支持批次关联

**步骤 2: 批量上传接口**

- 实现 POST /api/v1/convert/batch
- 支持多文件接收和验证
- 创建批次和任务
- 返回批次信息

**步骤 3: 批次状态查询**

- 实现 GET /api/v1/batch/status/{batch_id}
- 聚合批次内所有任务状态
- 计算批次整体进度

#### 第二阶段: 批量下载（1 天）

**步骤 4: ZIP 打包功能**

- 实现文件打包逻辑
- 生成批次摘要文件
- 实现 GET /api/v1/batch/download/{batch_id}

**步骤 5: 文件管理优化**

- 实现批次目录结构
- 实现批次文件清理
- 添加清理定时任务

#### 第三阶段: 优化和测试（1 天）

**步骤 6: 性能优化**

- 优化批量文件上传性能
- 优化 ZIP 打包性能（大批次）
- 添加批次大小限制

**步骤 7: 测试验证**

- 单元测试
- 集成测试（5 个、10 个、20 个文件）
- 压力测试

---

### 7.4 配置参数

**新增配置项**

```
# 批量上传配置
MAX_BATCH_FILES=20              # 单次批量上传最大文件数
MAX_BATCH_SIZE_MB=500           # 批量上传总大小限制（MB）
BATCH_RETENTION_HOURS=24        # 批次保留时间（小时）
ENABLE_BATCH_PRIORITY=false     # 是否启用批次优先处理

# ZIP打包配置
MAX_ZIP_SIZE_MB=1000            # 最大ZIP文件大小（MB）
ZIP_COMPRESSION_LEVEL=6         # ZIP压缩级别（0-9）
```

---

### 7.5 客户端使用流程

**批量上传流程**

```
1. 用户选择多个PDF文件（如5个）
2. 调用 POST /api/v1/convert/batch 上传
3. 获得 batch_id 和 task_id 列表
4. 轮询 GET /api/v1/batch/status/{batch_id} 查询进度
5. 批次完成后，调用 GET /api/v1/batch/download/{batch_id} 下载ZIP
6. 或者单独下载每个文件 GET /api/v1/download/{task_id}
```

**进度展示建议**

- 显示批次整体进度条（如 3/5 完成，60%）
- 显示每个文件的状态和进度
- 完成的文件提供单独下载链接
- 全部完成后提供批量下载按钮

---

### 7.6 性能评估

**假设场景: 批量上传 10 个 PDF**

- 每个 PDF: 50 页
- 单页处理时间: 2 秒
- 页面并发数: 3
- PDF 并发数: 3

**处理时间计算**

- 单个 PDF 处理时间: 50 页 ÷ 3 并发 × 2 秒 ≈ 34 秒
- 10 个 PDF 总时间: 34 秒 × (10÷3) ≈ 4 分钟

**资源消耗**

- 并发 API 调用: 3 个 PDF × 3 个页面 = 9 个
- 内存占用: 3 个 PDF 同时加载
- 磁盘占用: 10 个 PDF 上传 + 10 个 MD 输出

---

### 7.7 错误处理

**部分文件失败场景**

- 批次状态标记为 `partial_failed`
- 成功的文件可正常下载
- 失败的文件显示错误信息
- 批量下载 ZIP 只包含成功的文件

**全部文件失败场景**

- 批次状态标记为 `failed`
- 返回详细的失败原因
- 不提供批量下载（无成功文件）

**文件验证失败**

- 上传时验证每个文件
- 不合格的文件直接拒绝
- 返回具体的验证错误信息

---

### 7.8 后续扩展方向

#### 7.8.1 优先级队列

- 支持 VIP 用户优先处理
- 支持小文件优先处理
- 使用优先级队列替代 FIFO 队列

#### 7.8.2 分布式任务队列

- 引入 Celery + Redis
- 支持多机器分布式处理
- 支持任务持久化（服务重启不丢失）

#### 7.8.3 WebSocket 实时推送

- 替代轮询机制
- 实时推送批次进度更新
- 减少服务器压力

#### 7.8.4 高级批量功能

- 支持文件夹上传（保留目录结构）
- 支持 URL 批量导入
- 支持批次模板（预设转换选项）
- 支持批次任务暂停/恢复

---

## 八、风险和注意事项

### 8.1 技术风险

**BackgroundTasks 的限制**

- 不支持任务持久化（服务重启任务丢失）
- 不支持分布式（单机限制）
- 适合轻量级场景，大规模建议用 Celery

**解决方案**

- 短期使用 BackgroundTasks 快速实现
- 长期规划迁移到 Celery
- 设计时预留接口，便于后续替换

### 8.2 业务风险

**任务丢失**

- 服务重启导致处理中的任务丢失
- 建议: 添加任务状态持久化（数据库或 Redis）

**队列堆积**

- 处理速度慢于上传速度导致队列堆积
- 建议: 设置最大队列长度，超出则拒绝

**客户端超时**

- 大文件处理时间过长
- 建议: 设置合理的超时时间，提示用户耐心等待

---

## 九、总结

### 9.1 改造收益

**稳定性提升**

- 避免 API 限流导致的失败
- 避免内存溢出
- 可控的资源消耗

**用户体验提升**

- 请求立即返回，不阻塞
- 可查询进度，心里有数
- 支持大文件处理

**可维护性提升**

- 清晰的任务状态管理
- 便于监控和调试
- 易于扩展到分布式

### 9.2 实施建议

**分阶段实施**

1. 先实现基础异步队列（1-2 天）
2. 再添加进度跟踪（1 天）
3. 最后优化和监控（1 天）

**测试验证**

- 单任务测试
- 并发任务测试（5 个、10 个、20 个）
- 压力测试（找到系统瓶颈）

**灰度发布**

- 先在测试环境验证
- 小流量灰度（10%用户）
- 全量发布

---

## 十、附录

### 10.1 相关配置参数汇总

```
# 并发控制
MAX_CONCURRENT_PDF_TASKS=3          # 同时处理的PDF数量
MAX_CONCURRENT_API_CALLS=3          # 单PDF内页面并发数
MAX_QUEUE_SIZE=100                  # 最大队列长度

# 任务管理
TASK_TIMEOUT=1800                   # 任务超时（秒）
TASK_RETENTION_HOURS=24             # 任务保留时间（小时）
TASK_CLEANUP_INTERVAL=3600          # 清理间隔（秒）

# 性能优化
ENABLE_PROGRESS_TRACKING=true       # 启用进度跟踪
PROGRESS_UPDATE_INTERVAL=1          # 进度更新间隔（页）
```

### 10.2 关键指标监控

**业务指标**

- 任务成功率
- 平均处理时间
- 队列等待时间

**技术指标**

- API 调用成功率
- 内存使用率
- 队列长度

**告警阈值**

- 队列长度 > 50: 警告
- 队列长度 > 80: 严重
- 任务失败率 > 10%: 警告
- API 失败率 > 5%: 严重

---

**文档结束**
