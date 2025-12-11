# 视频转换功能文档

## 概述

本项目现已支持视频文件到Markdown和PDF的转换功能。系统可以自动提取视频的关键帧、元数据和时间戳信息，生成结构化的Markdown或PDF文档。

## 支持的视频格式

- **MP4** (.mp4)
- **AVI** (.avi)
- **MOV** (.mov)
- **WMV** (.wmv)
- **MKV** (.mkv)
- **FLV** (.flv)

## 功能特性

### 1. 自动关键帧提取
- 根据指定的时间间隔自动从视频中提取关键帧
- 支持自定义最大帧数限制
- 自动计算帧的时间戳和位置信息

### 2. 元数据提取
- 视频时长（Duration）
- 帧率（FPS）
- 总帧数
- 分辨率（Resolution）
- 文件大小
- 视频编码格式（Codec）

### 3. 多格式输出
- **Markdown输出**：包含嵌入式Base64编码的图像和元数据表格
- **PDF输出**：专业格式的PDF文档，包含美化的表格和分页的关键帧

## 使用方法

### API调用

#### 1. 转换为Markdown

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -F "file=@video.mp4" \
  -F "options={\"output_type\": \"markdown\", \"keyframe_interval\": 5, \"max_frames\": 50}"
```

#### 2. 转换为PDF

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -F "file=@video.mp4" \
  -F "options={\"output_type\": \"pdf\", \"keyframe_interval\": 3, \"max_frames\": 30}"
```

### Python代码示例

#### 基本转换示例

```python
import asyncio
from app.core.converters.video.video_converter import VideoConverter

async def convert_video():
    converter = VideoConverter()
    
    # 转换选项
    options = {
        'output_type': 'markdown',  # 或 'pdf'
        'keyframe_interval': 5,      # 每5秒提取一帧
        'max_frames': 50,            # 最多提取50帧
        'include_metadata': True,    # 包含元数据
        'include_frames': True,      # 包含关键帧
        'frame_quality': 85          # 帧质量（1-100）
    }
    
    # 执行转换
    result = await converter.convert('path/to/video.mp4', options)
    
    # 获取结果
    if result.output_type == 'markdown':
        print(result.markdown)
    else:
        with open('output.pdf', 'wb') as f:
            f.write(result.pdf_content)

# 运行
asyncio.run(convert_video())
```

#### 集成到ConversionService

```python
from app.services.conversion.conversion_service import ConversionService

async def process_video():
    service = ConversionService()
    
    result = await service.convert(
        file_path='path/to/video.mp4',
        filename='video.mp4',
        options={
            'output_type': 'pdf',
            'keyframe_interval': 3,
            'max_frames': 100
        }
    )
    
    print(f"转换完成: {result['task_id']}")
    print(f"输出类型: {result['output_type']}")
    print(f"处理时间: {result['metadata']['processing_time']}秒")
```

## 配置选项

### 转换选项参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_type` | string | 'markdown' | 输出格式：'markdown' 或 'pdf' |
| `keyframe_interval` | int | 5 | 关键帧提取间隔（秒） |
| `max_frames` | int | 100 | 最多提取的帧数 |
| `extract_frames` | bool | True | 是否提取关键帧 |
| `include_metadata` | bool | True | 是否包含视频元数据 |
| `include_frames` | bool | True | 是否包含关键帧图像 |
| `frame_quality` | int | 85 | 帧的JPEG质量（1-100） |

### 全局配置（config.py）

```python
# 视频转换配置
VIDEO_MAX_SIZE_MB = 500              # 最大视频文件大小（MB）
VIDEO_KEYFRAME_INTERVAL = 5           # 默认关键帧间隔（秒）
VIDEO_MAX_FRAMES = 100                # 默认最大帧数
VIDEO_FRAME_QUALITY = 85              # 默认帧质量
VIDEO_EXTRACT_FRAMES = True           # 默认是否提取帧
```

## 输出示例

### Markdown输出

```markdown
# 视频内容摘要

## 视频信息

| 属性 | 值 |
|------|-----|
| 时长 | 00:01:30 |
| 分辨率 | 1920x1080 |
| 帧率 | 30.00 FPS |
| 总帧数 | 2700 |
| 编码格式 | h264 |
| 文件大小 | 125.50 MB |
| 提取帧数 | 30 |

## 关键帧内容

### 帧 1 - 00:00:00.000

![Frame 1](data:image/jpeg;base64,...)

- **时间戳**: 00:00:00.000
- **帧号**: 0
- **分辨率**: 1920x1080

### 帧 2 - 00:00:05.000

...
```

### PDF输出

生成的PDF包含：
- 标题页
- 视频信息表格
- 关键帧图像及信息
- 专业的布局和格式

## 工作流程

```
视频文件
   ↓
验证视频文件 (VideoConverter.validate)
   ↓
提取视频信息和关键帧 (VideoProcessor.process)
   ├─ 读取视频属性
   ├─ 计算关键帧位置
   ├─ 提取关键帧图像
   └─ 编码为Base64
   ↓
生成输出内容
   ├─ Markdown: VideoMarkdownGenerator.generate
   └─ PDF: VideoPDFGenerator.generate
   ↓
返回ConversionResult
```

## 性能考虑

### 内存使用
- 每个关键帧在内存中占用约100-300KB（取决于分辨率和质量）
- 建议通过`max_frames`参数限制帧数以避免内存溢出

### 处理时间
- 小视频（<1分钟）：通常 < 5秒
- 中等视频（1-10分钟）：通常 5-30秒
- 大视频（>10分钟）：取决于帧数和分辨率

### 优化建议
1. 减小`keyframe_interval`值来提取更少的帧
2. 降低`frame_quality`以减小输出文件大小
3. 对大文件启用流式处理（如果需要）

## 错误处理

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| 无效的视频文件 | 文件损坏或格式不支持 | 检查文件完整性，确保格式正确 |
| 超出最大文件大小 | 视频过大 | 减小video_max_size_mb或压缩视频 |
| 内存不足 | 帧数或质量太高 | 减小max_frames或frame_quality |
| 编码错误 | 不支持的视频编码 | 使用支持的编码格式重新编码 |

## 测试

### 运行单元测试

```bash
pytest tests/test_converters/test_video_converter.py -v
```

### 运行集成测试

```bash
pytest tests/integration/test_video_conversion_integration.py -v
```

### 测试覆盖范围

- ✓ 视频文件验证
- ✓ 关键帧提取
- ✓ Markdown生成
- ✓ PDF生成
- ✓ 元数据提取
- ✓ 错误处理
- ✓ 各种转换选项

## 架构设计

### 核心组件

```
VideoConverter (主转换器)
    ├─ VideoProcessor (视频处理和帧提取)
    ├─ VideoMarkdownGenerator (Markdown生成)
    └─ VideoPDFGenerator (PDF生成)
```

### 文件结构

```
app/core/converters/video/
    ├─ __init__.py
    ├─ video_converter.py          # 主转换器类
    ├─ video_processor.py          # 视频处理逻辑
    ├─ markdown_generator.py       # Markdown生成
    └─ pdf_generator.py            # PDF生成

tests/
    ├─ test_converters/
    │   └─ test_video_converter.py # 单元测试
    └─ integration/
        └─ test_video_conversion_integration.py # 集成测试
```

## 扩展和自定义

### 添加新的视频格式

1. 在`app/models/enums.py`中添加新的FileType
2. 在`app/core/factory/converter_factory.py`中注册转换器
3. VideoConverter已支持OpenCV支持的所有格式

### 自定义输出格式

```python
class CustomVideoGenerator:
    async def generate(self, video_info, options):
        # 自定义生成逻辑
        pass

# 修改VideoConverter使用自定义生成器
converter.custom_generator = CustomVideoGenerator()
```

## 许可证

同项目许可证

## 支持

如有问题或建议，请提交Issue或Pull Request。

