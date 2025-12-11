# 📷 图片在线压缩工具

一个基于 Vue 3 的高质量图片在线压缩工具，支持多种图片格式输入，输出为优化的 WebP 格式。

## ✨ 特性

- 🖼️ **多种上传方式**：支持点击上传、拖拽上传、粘贴上传（Ctrl+V）
- 🎯 **智能缩放**：自动将图片缩放到最大 1920×1080，保持宽高比
- 🚀 **高质量压缩**：使用 Lanczos 算法进行高质量重采样，WebP 质量设置为 95
- 📦 **批量处理**：支持同时上传和处理多张图片
- 👀 **实时预览**：对比查看原图和处理后的效果
- 💾 **一键下载**：直接下载处理后的 WebP 文件
- ⚡ **Web Worker**：后台处理，不阻塞主线程
- 🎨 **现代化 UI**：美观的渐变背景和流畅的动画效果

## 🛠️ 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - 类型安全
- **Vite** - 快速的构建工具
- **pica** - 高质量图片缩放库（Lanczos 算法）
- **@jsquash/webp** - 基于 WASM 的 WebP 编码器
- **exifr** - EXIF 信息处理

## 📦 安装

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

## 🎯 使用方法

### 1. 点击上传

点击上传区域，选择一张或多张图片文件。

### 2. 拖拽上传

从文件管理器拖拽图片文件到上传区域。

### 3. 粘贴上传

复制图片后，在页面上按 `Ctrl+V` 粘贴。

### 4. 查看结果

- 查看原始尺寸、大小
- 查看处理后尺寸、大小
- 查看压缩率
- 点击"预览"查看对比效果
- 点击"下载"保存 WebP 文件

## 📋 支持的格式

**输入格式**：JPEG, PNG, BMP, GIF, TIFF, WebP

**输出格式**：WebP

## ⚙️ 处理参数

- **最大尺寸**：1920×1080
- **WebP 质量**：95
- **重采样算法**：Lanczos（最高质量）
- **压缩方法**：method=6（最高质量）
- **文件大小限制**：50MB

## 📁 项目结构

```
smallimg/
├── src/
│   ├── components/          # Vue 组件
│   │   ├── ImageUploader.vue      # 上传组件
│   │   ├── ImagePreview.vue       # 预览组件
│   │   └── ProcessingList.vue     # 处理列表组件
│   ├── composables/         # 组合式函数
│   │   └── useImageProcess.ts     # 图片处理逻辑
│   ├── workers/             # Web Workers
│   │   └── image-worker.ts        # 图片处理 Worker
│   ├── utils/               # 工具函数
│   │   ├── image-utils.ts         # 图片工具
│   │   └── file-utils.ts          # 文件工具
│   ├── types/               # TypeScript 类型定义
│   │   └── index.ts
│   ├── App.vue              # 主应用组件
│   ├── main.js              # 入口文件
│   └── style.css            # 全局样式
├── public/                  # 静态资源
├── package.json
├── vite.config.js           # Vite 配置
└── README.md
```

## 🔧 核心实现

### 图片处理流程

1. **读取文件** → ArrayBuffer
2. **解码图片** → ImageBitmap
3. **计算目标尺寸**（保持宽高比）
4. **使用 pica 进行高质量缩放**（Lanczos 算法）
5. **使用 @jsquash/webp 编码为 WebP**
6. **移除元数据**（WebP 编码器默认不包含元数据）
7. **返回处理后的 Blob**

### Web Worker

使用 Web Worker 在后台线程处理图片，避免阻塞主线程，提供流畅的用户体验。

### 尺寸计算规则

- 如果图片已在限制范围内（≤1920×1080），不进行缩放
- 如果超出限制，计算宽度和高度的缩放比例，取较小值
- 使用该比例计算新尺寸，确保两个维度都不超过限制
- 新尺寸向下取整，保持宽高比

## 🎨 特色功能

### 高质量压缩

- 使用 **Lanczos 算法**进行图片缩放，保证最高质量
- WebP 质量设置为 **95**，在文件大小和质量之间取得最佳平衡
- 压缩方法设置为 **method=6**，使用最慢但质量最好的压缩方法

### 用户体验

- 实时进度显示
- 错误提示和成功提示
- 流畅的动画效果
- 响应式设计，支持移动端

## 📝 开发说明

### 添加新功能

1. 在 `src/components/` 中创建新组件
2. 在 `src/composables/` 中添加业务逻辑
3. 在 `src/utils/` 中添加工具函数
4. 在 `src/types/` 中定义 TypeScript 类型

### 修改处理参数

在 `src/workers/image-worker.ts` 中修改默认参数：

```typescript
const {
  maxWidth = 1920, // 最大宽度
  maxHeight = 1080, // 最大高度
  quality = 95, // WebP 质量
  method = 6, // 压缩方法
} = options;
```

## 📄 许可证

MIT

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系方式

如有问题或建议，请提交 Issue。
