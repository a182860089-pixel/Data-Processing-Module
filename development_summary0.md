# 开发总结与快速启动指南

本文档总结了本次会话期间完成的开发工作，并提供了如何快速启动两个核心模块（PDF 转 Markdown 后端、统一前端 UI）的说明。

---

## 1. 已完成工作总结

在本次开发中，我们主要完成了以下任务：

### 1.1. 环境搭建与问题修复

- **定位并修复了后端的 `ModuleNotFoundError: No module named 'mupdf'` 错误**：
  - **根本原因**：全局 Python 环境中的 `PyMuPDF` 库安装不完整或版本与项目要求 (`1.23.8`) 不匹配。
  - **解决方案**：为 `data_to_md-main` 项目创建了一个独立的 Python 虚拟环境 (`.venv`)，并在其中干净地安装了 `requirements.txt` 指定的所有依赖。这确保了后端服务拥有一个稳定、隔离的运行环境，彻底解决了启动报错问题。

- **修复了前端模块的启动错误**：
  - 修正了 `npm` 命令执行时的工作目录，确保 `package.json` 文件能被正确找到，使 Vite 开发服务器得以正常启动。

### 1.2. PDF 转 Markdown 前端页面开发

- **从零创建了一个新的 Vue 组件**：`src/components/PdfUploader.vue`，为 PDF 转换后端提供了一个完整、独立的交互界面。
  - **核心功能**：
    - 支持**选择 PDF 文件**，并进行类型校验。
    - 提供“**模式切换**”功能：
      - **阅读模式**：输出纯净的 Markdown，适合直接阅读。
      - **调试模式**：输出带页码和元数据，便于检查 OCR 效果。
    - 调用后端 `/api/v1/convert` 接口执行转换。
    - 在页面上直接**显示返回的 Markdown 文本**。
    - 提供“**复制内容**”和“**下载 .md 文件**”的便捷操作。

### 1.3. 统一化的前端用户界面

- **将图片压缩与 PDF 转换功能整合**：对现有的 `proc_image/smallimg` 前端项目进行了重构，将其升级为一个包含两大功能的“数据处理小工具”。
- **实现方式**：
  - 修改了主视图 `src/App.vue`，引入了**标签页（Tab）式布局**。
  - **标签页 1: “📷 图片压缩”**：保留了原有的图片压缩功能。
  - **标签页 2: “📄 PDF → Markdown”**：集成了新创建的 `PdfUploader` 组件。
- **最终效果**：现在只需访问 `http://localhost:5173` 这一个地址，即可在统一的界面中方便地切换使用图片和 PDF 处理功能。

---

## 2. 快速启动指南

你需要**两个独立的终端窗口**（或在同一个终端工具里开两个标签页），分别用来启动后端和前端。

### 终端 1：启动后端服务 (PDF→Markdown)

此服务运行在 `http://localhost:8000`。

```powershell
# 1. 进入后端项目目录
cd "D:\Data Processing Module\data_to_md-main"

# 2. 使用虚拟环境的 Python 启动 uvicorn 服务
# (这条命令会自动使用我们创建好的 .venv 环境，避免了全局环境的问题)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**如何验证**：在浏览器中打开 `http://localhost:8000/docs`。如果能看到 FastAPI 的接口文档页面，说明后端已成功运行。

### 终端 2：启动前端界面 (Web UI)

此服务运行在 `http://localhost:5173`。

```powershell
# 1. 进入前端项目目录
cd "D:\Data Processing Module\proc_image\smallimg"

# 2. 安装依赖 (如果你还没装过，或者新加了依赖)
npm install

# 3. 启动 Vite 开发服务器
npm run dev
```

**如何使用**：在浏览器中打开 `http://localhost:5173`。你会看到一个包含“图片压缩”和“PDF → Markdown”两个标签页的统一界面。
