# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

这是一个图片压缩项目，包含三个主要实现：

1. **Python CLI 工具** (`compress_images原版webp.py`) - 使用 PIL/Pillow 进行批量图片压缩
2. **Vue 3 Web 应用** (`smallimg/`) - 具有现代化 UI 的在线图片压缩工具
3. **独立 HTML 工具** (`compress_images_web.html`) - 无需依赖的浏览器端压缩

所有实现都将图片压缩为 WebP 格式，具有智能降采样（最大 1920×1080）、高质量重采样和元数据移除功能。

## 开发命令

### Python CLI 工具

```bash
# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 运行压缩脚本
python compress_images原版webp.py

# 安装依赖
pip install Pillow
```

### Vue 3 Web 应用 (`smallimg/`)

```bash
# 进入 Vue 应用目录
cd smallimg

# 安装依赖
npm install

# 启动开发服务器 (http://localhost:5173)
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

### 独立 HTML 工具

直接在浏览器中打开 `compress_images_web.html` - 无需构建过程。

## 架构设计

### Vue 3 Web 应用 (`smallimg/`)

**核心处理流程：**
1. 用户通过点击/拖拽/粘贴上传图片
2. 主线程创建 Worker 并发送文件
3. **Web Worker** (`src/workers/image-worker.ts`) 在后台线程执行处理：
   - 解码图片 → ImageBitmap
   - 计算目标尺寸（保持宽高比，最大 1920×1080）
   - 使用 **pica** 进行缩放（Lanczos 算法，quality=3）
   - 使用 **@jsquash/webp** 编码为 WebP（quality=92, method=6）
   - 报告进度：20%, 40%, 50%, 70%, 90%, 100%
4. 主线程接收结果并更新 UI

**关键文件：**
- `src/workers/image-worker.ts` - Web Worker 处理所有图片处理操作
- `src/composables/useImageProcess.ts` - 管理 Worker 生命周期和通信
- `src/components/ImageUploader.vue` - 处理文件上传（点击/拖拽/粘贴）
- `src/components/ProcessingList.vue` - 显示处理队列和结果
- `src/components/ImagePreview.vue` - 预览模态框，用于前后对比
- `src/types/index.ts` - TypeScript 类型定义

**核心库：**
- **pica** - 使用 Lanczos 算法进行高质量图片缩放
- **@jsquash/webp** - 基于 WASM 的 WebP 编码器，支持高级参数
- **exifr** - 可选的 EXIF 处理（目前未使用但可用）

**Vite 配置要点：**
- 路径别名：`@` → `src/`
- `@jsquash/webp` 被排除在预构建之外（WASM 模块）
- Worker 格式：ES modules

### Python CLI 工具

**处理流程：**
1. 用户输入文件夹路径
2. 查找所有支持格式的图片
3. 对每张图片：
   - 使用 PIL/Pillow 打开
   - 转换为 RGB/RGBA 模式
   - 计算新尺寸（最大 1920×1080）
   - 使用 LANCZOS 重采样进行缩放
   - 保存为 WebP，参数：quality=95, method=6, minimize_size=True
4. 输出压缩统计信息

**关键参数：**
- 质量：95（高质量，平衡压缩）
- 方法：6（最慢但质量最佳）
- 重采样：LANCZOS（PIL 最高质量滤镜）
- 输出后缀：`_compressed.webp`

### 独立 HTML 工具

**架构：**
- 单文件应用，使用原生 JS
- 使用 Canvas API 进行图片处理
- 通过 `createImageBitmap` 处理 EXIF 方向
- 使用原生 Canvas `toWebP` 编码（质量 0-1 范围）
- 使用 JSZip 进行批量下载
- 在 ZIP 输出中保留文件夹结构

## 压缩参数

### Vue 应用 (smallimg) 默认设置
```typescript
quality: 92         // WebP 质量 (0-100)
method: 6          // 压缩方法 (0-6，最高)
pass: 8            // 多遍优化
use_sharp_yuv: 1   // 更锐利的 YUV 采样
sns_strength: 75   // 感知噪点整形
filter_strength: 30    // 去噪强度
filter_sharpness: 3    // 边缘保留
maxWidth: 1920     // 最大宽度
maxHeight: 1080    // 最大高度
```

### Python 脚本默认设置
```python
WEBP_QUALITY = 95
MAX_WIDTH = 1920
MAX_HEIGHT = 1080
USE_MINIMIZE_SIZE = True
COMPRESSION_PASSES = 1  # 注意：PIL 可能不支持 pass 参数
```

## 尺寸计算逻辑

**两种实现使用相同的逻辑：**
```
如果 width ≤ maxWidth 且 height ≤ maxHeight:
    返回原始尺寸（不缩放）
否则:
    ratio = min(maxWidth/width, maxHeight/height)
    newWidth = floor(width × ratio)
    newHeight = floor(height × ratio)
    返回 (newWidth, newHeight)
```

这确保了：
- 保持宽高比
- 两个维度都不超过限制
- 小图片不会被放大

## 使用 Web Workers

Vue 应用使用 Web Workers 防止 UI 阻塞：

**向 Worker 发送消息：**
```typescript
worker.postMessage({ file, options });
```

**从 Worker 接收消息：**
```typescript
// 进度更新
{ type: "progress", progress: 20-100 }

// 成功
{ type: "success", result: { blob, width, height, size } }

// 错误
{ type: "error", error: "错误信息" }
```

**错误处理回退机制：**
- 如果 `pica.resize()` 失败（例如被反指纹保护阻止 getImageData），回退到原生 Canvas `drawImage`，使用 `imageSmoothingQuality: "high"`
- 如果 `@jsquash/webp` 编码失败，回退到 `OffscreenCanvas.convertToBlob()`

## 文件组织

```
proc_image/
├── compress_images原版webp.py    # Python CLI 工具
├── compress_images_web.html       # 独立 HTML 工具
├── prd.md                        # 产品需求文档（中文）
├── smallimg/                     # Vue 3 web 应用
│   ├── src/
│   │   ├── workers/             # Web Workers（后台线程）
│   │   ├── composables/         # Vue 组合式函数（可复用逻辑）
│   │   ├── components/          # Vue UI 组件
│   │   ├── utils/              # 辅助函数
│   │   └── types/              # TypeScript 类型定义
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── tools/libvips/               # libvips 库（未主动使用）
└── testimgs/                    # 测试图片
```

## 测试策略

**测试不同场景：**
1. 各种格式：JPEG, PNG, GIF, BMP, TIFF, WebP
2. 尺寸变化：< 1920×1080, = 1920×1080, > 1920×1080
3. 透明图片（PNG, WebP）
4. 批量处理（多个文件）
5. 大文件（>10MB）
6. 边缘情况：非常宽/高的图片

**预期压缩率：** 文件大小减少 50-90%

## 重要注意事项

- **元数据移除：** WebP 编码会自动去除 EXIF/元数据
- **GIF 处理：** 转换为静态图片（仅第一帧）
- **透明图片：** 通过 RGBA 模式正确处理
- **浏览器兼容性：** Vue 应用需要现代浏览器（Chrome, Edge, Firefox, Safari 15+）
- **文件大小限制：** 建议 ≤50MB 每个文件
- **输出格式：** 始终为 WebP（现代、高效、广泛支持）

## 常见任务

**向 Vue 应用添加新的压缩参数：**
1. 在 `src/types/index.ts` 的 `ProcessOptions` 接口中添加参数
2. 更新 `src/workers/image-worker.ts` 中的 `processImage` 函数
3. 在 `src/composables/useImageProcess.ts` 中传递参数
4. 可选：通过组件 props 在 UI 中公开

**更改默认压缩设置：**
- Vue 应用：编辑 `src/workers/image-worker.ts:40` 和 `src/composables/useImageProcess.ts:97-105` 中的默认值
- Python：编辑 `compress_images原版webp.py` 顶部的常量
- HTML：编辑 `compress_images_web.html` 脚本部分的常量

**调试 Worker 问题：**
- 检查浏览器控制台是否有 Worker 错误
- 在 `image-worker.ts` 中添加 `console.debug()` 语句
- 先用较小的图片测试
- 验证 WASM 模块加载（DevTools 的 Network 标签）
