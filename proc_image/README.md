# proc_image 图片压缩与异步任务演示项目

本仓库是一个围绕「图片/视频处理」场景构建的前端 + 脚本工具集合，用于：

- 批量将图片压缩为 WebP（保持较高画质、最大 1920×1080）
- 在浏览器中在线压缩图片并预览效果
- 通过独立 HTML 页面完成图片压缩与打包下载
- 演示和测试「异步轮询」任务处理机制（可视化面板）
- 在前端集成视频 → Markdown / PDF 转换功能（依赖后端 API）

---

## 1. 仓库结构

```text
proc_image/
├── compress_images原版webp.py      # Python 批量图片压缩脚本
├── compress_images_web.html         # 独立 HTML 图片压缩工具
├── smallimg/                        # Vue 3 前端应用（图片压缩 + 异步轮询 + 视频转换入口）
│   ├── src/
│   │   ├── components/
│   │   │   ├── ImageUploader.vue    # 图片上传与列表
│   │   │   ├── ImagePreview.vue     # 图片前后对比预览
│   │   │   ├── ProcessingList.vue   # 压缩任务列表
│   │   │   ├── AsyncPollingTest.vue # 异步轮询测试界面
│   │   │   └── VideoUploader.vue    # 视频转换前端组件
│   │   ├── composables/
│   │   │   ├── useImageProcess.ts   # 图片压缩业务逻辑（调用 Web Worker）
│   │   │   └── useAsyncPolling.ts   # 通用异步轮询逻辑
│   │   ├── workers/
│   │   │   └── image-worker.ts      # 在 Worker 线程中执行图片缩放+编码
│   │   ├── utils/                   # 工具函数
│   │   ├── types/                   # TypeScript 类型定义
│   │   ├── App.vue                  # 应用入口，包含多个标签页
│   │   └── main.js                  # 入口脚本
│   ├── README.md                    # smallimg 子项目说明
│   ├── 使用说明.md                   # Web 应用详细使用手册
│   └── VIDEO_INTEGRATION.md         # 视频转换功能前端集成说明
├── ASYNC_POLLING_TEST_GUIDE.md      # 异步轮询测试工具详细使用指南
├── ASYNC_POLLING_QUICK_REFERENCE.md # 异步轮询测试快速参考
├── IMPLEMENTATION_SUMMARY.md        # 异步轮询功能实现总结
├── CLAUDE.md                        # 面向 AI/开发者的技术说明
└── testimgs/                        # 各种测试图片
```

---

## 2. 功能模块概览

### 2.1 图片压缩

仓库内提供三种形态的图片压缩实现：

1. **Python CLI 脚本**（`compress_images原版webp.py`）  
   - 面向本地批量处理场景（备份照片、离线压缩）。  
   - 使用 Pillow 读取/缩放图片，输出 WebP：
     - 最大尺寸：1920×1080（保持宽高比，不放大小图）
     - 质量：95
     - 重采样：LANCZOS

2. **独立 HTML 工具**（`compress_images_web.html`）  
   - 纯前端单文件工具，可直接双击用浏览器打开。  
   - 使用 Canvas API 和 JSZip 完成缩放 + WebP 编码 + 批量打包下载。  
   - 适合不想搭建 Node/Python 环境的简单使用场景。

3. **Vue 3 Web 应用**（`smallimg/`）  
   - 现代化 UI，支持点击 / 拖拽 / 粘贴上传。  
   - 使用 Web Worker + `pica` + `@jsquash/webp` 在后台线程完成高质量压缩。  
   - 支持批量上传、进度显示、结果预览和一键下载。  
   - 详细说明见 `smallimg/README.md` 与 `smallimg/使用说明.md`。

### 2.2 异步轮询测试工具

位于 `smallimg` 前端内，通过顶部标签页「异步轮询测试」进入，对应核心文件：

- 组件：`smallimg/src/components/AsyncPollingTest.vue`
- 业务逻辑：`smallimg/src/composables/useAsyncPolling.ts`

主要用途：

- 可视化演示「轮询获取异步任务进度」的完整流程。  
- 支持配置轮询间隔、模拟时长、任务数量、自动/手动模式。  
- 实时展示总轮询次数、成功/失败次数、平均间隔、总耗时、活跃任务数等指标。  
- 提供详细日志与进度条，可用于调试真实接口时的轮询策略。

配套文档：

- `ASYNC_POLLING_TEST_GUIDE.md`：完整使用说明与场景示例。
- `ASYNC_POLLING_QUICK_REFERENCE.md`：快速上手参数和操作速查。
- `IMPLEMENTATION_SUMMARY.md`：实现细节与架构总结。

### 2.3 视频 → Markdown/PDF 转换前端

在 `smallimg` 项目中新增的视频转换标签页，通过组件 `VideoUploader.vue` 与后端 API 交互：

- 上传本地视频（支持多种常见格式，限制单文件大小）。  
- 配置输出格式（Markdown 或 PDF）、关键帧间隔、最大帧数、帧质量等参数。  
- 展示转换进度并提供结果下载。  
- 可选配置后端 API 地址（默认 `http://localhost:8000`）。

详细说明与操作步骤见 `smallimg/VIDEO_INTEGRATION.md`。

---

## 3. 快速开始

### 3.1 前端 Web 应用（smallimg）

1. 进入子项目目录：

   ```bash
   cd smallimg
   ```

2. 安装依赖：

   ```bash
   npm install
   ```

3. 启动开发服务器：

   ```bash
   npm run dev
   ```

4. 浏览器访问 `http://localhost:5173`：

   - 「图片压缩」页签：体验在线图片压缩。  
   - 「异步轮询测试」页签：体验轮询任务模拟与可视化。  
   - 「视频 → MD/PDF」页签：在本地后端服务开启后体验视频转换功能。

5. 生产构建与预览：

   ```bash
   npm run build
   npm run preview
   ```

> 使用详情、参数解释、常见问题请参考 `smallimg/README.md` 与 `smallimg/使用说明.md`。

### 3.2 Python 批量压缩脚本

1.（可选）在仓库根目录创建并激活虚拟环境：

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   ```

2. 安装依赖：

   ```bash
   pip install Pillow
   ```

3. 运行脚本，根据提示输入待处理图片目录：

   ```bash
   python compress_images原版webp.py
   ```

脚本会在原始图片所在目录生成对应的 WebP 文件，并输出压缩前后大小统计信息。

### 3.3 独立 HTML 图片压缩工具

1. 在文件管理器中找到 `compress_images_web.html`。
2. 双击使用现代浏览器打开（推荐 Chrome / Edge / Firefox）。
3. 拖拽图片到页面，等待压缩完成后下载结果或 ZIP 包。

---

## 4. 关键技术点

- **统一的尺寸策略**：所有实现都采用「最大宽高 1920×1080，保持宽高比，小图不放大」的规则进行缩放。
- **高质量压缩**：
  - Python/PIL：LANCZOS 重采样，WebP 质量约 95。  
  - Vue/Web 前端：`pica` + `@jsquash/webp`，使用高质量参数，平衡速度与体积。  
- **Web Worker**：前端应用在独立线程中处理图片，避免主线程卡顿。
- **异步轮询抽象**：`useAsyncPolling.ts` 将轮询逻辑封装为组合式函数，可直接接到真实业务接口。

更多底层实现细节可以参考 `CLAUDE.md` 与 `IMPLEMENTATION_SUMMARY.md`。

---

## 5. 文档导航

- `smallimg/README.md`：前端图片压缩工具的整体说明。  
- `smallimg/使用说明.md`：面向最终使用者的详细操作手册。  
- `smallimg/VIDEO_INTEGRATION.md`：视频转换前端集成说明与测试建议。  
- `ASYNC_POLLING_TEST_GUIDE.md`：异步轮询测试工具完整使用指南。  
- `ASYNC_POLLING_QUICK_REFERENCE.md`：异步轮询参数/操作速查表。  
- `IMPLEMENTATION_SUMMARY.md`：轮询测试功能的设计与实现总结。  
- `CLAUDE.md`：项目整体架构、关键脚本和默认参数说明。

---

## 6. 贡献与维护

本仓库主要作为内部工具与示例项目使用：

- 可以在 `smallimg` 子项目中扩展新的前端功能（如更多文件处理工具）。
- 可以在 `compress_images原版webp.py` 基础上增加命令行参数或批量策略。
- 若需要对异步轮询逻辑或视频转换功能进行拓展，请同时更新对应的文档文件以保持一致性。
