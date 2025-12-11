# 视频转换功能 - 快速开始

## 5分钟快速开始

### 1. 安装依赖

确保已安装所需的依赖（项目已包含）：
```bash
pip install opencv-python reportlab
```

### 2. 基本使用

```python
import asyncio
from app.core.converters.video.video_converter import VideoConverter

async def main():
    # 创建转换器
    converter = VideoConverter()
    
    # 转换视频为Markdown
    options = {
        'output_type': 'markdown',
        'keyframe_interval': 5,  # 每5秒提取一帧
        'max_frames': 20,        # 最多20帧
    }
    
    result = await converter.convert('my_video.mp4', options)
    
    # 保存结果
    with open('output.md', 'w', encoding='utf-8') as f:
        f.write(result.markdown)
    
    print("✓ 视频已转换为 output.md")

# 运行
asyncio.run(main())
```

### 3. 转换为PDF

```python
async def main():
    converter = VideoConverter()
    
    # 转换视频为PDF
    options = {
        'output_type': 'pdf',
        'keyframe_interval': 3,
        'max_frames': 30,
    }
    
    result = await converter.convert('my_video.mp4', options)
    
    # 保存结果
    with open('output.pdf', 'wb') as f:
        f.write(result.pdf_content)
    
    print("✓ 视频已转换为 output.pdf")

asyncio.run(main())
```

## API使用

### 通过HTTP API转换

```bash
# 转换为Markdown
curl -X POST http://localhost:8000/api/v1/convert \
  -F "file=@video.mp4" \
  -F "options={\"output_type\": \"markdown\"}"

# 转换为PDF
curl -X POST http://localhost:8000/api/v1/convert \
  -F "file=@video.mp4" \
  -F "options={\"output_type\": \"pdf\"}"
```

## 常见场景

### 场景1：快速预览视频内容
```python
options = {
    'output_type': 'markdown',
    'keyframe_interval': 10,  # 10秒间隔，帧数少
    'max_frames': 10,         # 最多10帧
}
```

### 场景2：详细视频分析
```python
options = {
    'output_type': 'pdf',
    'keyframe_interval': 1,   # 1秒间隔，帧数多
    'max_frames': 100,        # 最多100帧
    'frame_quality': 95,      # 高质量
}
```

### 场景3：只获取元数据
```python
options = {
    'output_type': 'markdown',
    'extract_frames': False,      # 不提取帧
    'include_metadata': True,     # 只要元数据
}
```

## 支持的视频格式

- ✓ MP4 (.mp4)
- ✓ AVI (.avi)
- ✓ MOV (.mov)
- ✓ WMV (.wmv)
- ✓ MKV (.mkv)
- ✓ FLV (.flv)

## 常见问题

### Q: 转换大视频时内存不足？
A: 减少 `max_frames` 或增加 `keyframe_interval`

### Q: 如何获取高质量的帧？
A: 设置 `frame_quality` 为 90-100

### Q: 转换速度太慢？
A: 减少 `max_frames` 或增加 `keyframe_interval`

### Q: 支持哪些输出格式？
A: 支持 Markdown 和 PDF 两种格式

## 下一步

- 查看 [完整文档](./docs/VIDEO_CONVERSION.md)
- 运行测试：`pytest tests/test_converters/test_video_converter.py`
- 查看示例：`tests/integration/test_video_conversion_integration.py`

## 获取帮助

有问题？查看以下资源：
- 📖 [完整文档](./docs/VIDEO_CONVERSION.md)
- 🧪 [测试用例](./tests/test_converters/test_video_converter.py)
- 💬 提交Issue获取帮助

