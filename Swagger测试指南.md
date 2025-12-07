# Swagger API 测试指南

## 快速开始

### 1. 启动服务器

```bash
cd "D:\Data Processing Module\data_to_md-main"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 访问 Swagger UI

打开浏览器访问：
- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

---

## API 测试步骤

### 方法 1：使用 Swagger UI（推荐）

#### 步骤 1：打开 Swagger UI
```
http://localhost:8000/docs
```

#### 步骤 2：找到转换接口
```
POST /api/v1/convert
```

#### 步骤 3：点击"Try it out"按钮

#### 步骤 4：填写参数
- **file**: 选择要测试的文件
- **options**: 输入 JSON 格式的转换选项

#### 步骤 5：点击"Execute"执行请求

---

## 测试用例

### 测试 1：文件类型检测 API

**目的**：验证文件类型检测功能

**步骤**：
1. 访问 http://localhost:8000/docs
2. 找到 `POST /api/v1/convert` 接口
3. 点击 "Try it out"
4. 选择一个文件上传
5. 点击 "Execute"

**预期结果**：
```json
{
  "success": true,
  "task_id": "task_xxx",
  "message": "文件转换完成",
  "filename": "test.docx",
  "file_type": "docx",
  "download_url": "/api/v1/download/task_xxx",
  "metadata": {...}
}
```

### 测试 2：Office 文档转 PDF

**目的**：测试 DOCX/PPTX/XLSX 转 PDF

**准备**：创建测试文件
```bash
# 创建简单的测试 Word 文档（使用 python-docx）
python -c "
from docx import Document
doc = Document()
doc.add_heading('Test Document', 0)
doc.add_paragraph('This is a test paragraph.')
doc.save('test.docx')
"
```

**步骤**：
1. 在 Swagger UI 中选择 `test.docx` 文件
2. 选择转换选项：
   ```json
   {
     "keep_layout": true,
     "office_dpi": 96
   }
   ```
3. 执行转换
4. 检查响应

**预期结果**：
- 返回成功状态
- 文件类型识别为 `docx`
- 包含下载链接

### 测试 3：图片转 PDF

**目的**：测试图片转 PDF 功能

**准备**：创建测试图片
```bash
python -c "
from PIL import Image
img = Image.new('RGB', (200, 200), color='blue')
img.save('test.jpg')
"
```

**步骤**：
1. 在 Swagger UI 中选择 `test.jpg` 文件
2. 输入转换选项：
   ```json
   {
     "page_size": "A4",
     "fit_mode": "contain"
   }
   ```
3. 执行转换
4. 检查结果

**预期结果**：
- 成功转换
- 文件类型识别为 `jpg`
- 包含 PDF 下载链接

### 测试 4：健康检查

**目的**：验证 API 服务状态

**步骤**：
1. 在 Swagger UI 中找到 `GET /api/v1/health` 接口
2. 点击 "Try it out"
3. 点击 "Execute"

**预期结果**：
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 使用 curl 进行测试

### 1. 健康检查
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

### 2. 转换 DOCX 文件
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@test.docx" \
  -F 'options={"keep_layout": true, "office_dpi": 96}'
```

### 3. 转换 JPG 图片
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@test.jpg" \
  -F 'options={"page_size": "A4", "fit_mode": "contain"}'
```

### 4. 查询任务状态
```bash
curl -X GET "http://localhost:8000/api/v1/status/{task_id}"
```

### 5. 下载转换结果
```bash
curl -X GET "http://localhost:8000/api/v1/download/{task_id}" \
  -o output.pdf
```

---

## 使用 Python 进行测试

### 完整测试脚本

```python
import requests
from pathlib import Path

# 配置
API_URL = "http://localhost:8000/api/v1"
TEST_FILE = "test.docx"

def test_convert_office():
    """测试 Office 文档转 PDF"""
    
    # 1. 检查健康状态
    print("1. 检查 API 健康状态...")
    response = requests.get(f"{API_URL}/health")
    print(f"   状态: {response.json()}")
    
    # 2. 上传并转换文件
    print(f"\n2. 转换文件: {TEST_FILE}")
    
    with open(TEST_FILE, 'rb') as f:
        files = {'file': f}
        options = {
            'keep_layout': True,
            'office_dpi': 96
        }
        data = {'options': str(options)}
        
        response = requests.post(
            f"{API_URL}/convert",
            files=files,
            data=data
        )
    
    result = response.json()
    print(f"   转换状态: {result.get('success')}")
    print(f"   任务 ID: {result.get('task_id')}")
    print(f"   文件类型: {result.get('file_type')}")
    
    # 3. 查询任务状态
    if result.get('success'):
        task_id = result['task_id']
        print(f"\n3. 查询任务状态...")
        
        status_response = requests.get(f"{API_URL}/status/{task_id}")
        status = status_response.json()
        print(f"   任务状态: {status.get('status')}")
    
    # 4. 下载结果
    print(f"\n4. 下载转换结果...")
    download_response = requests.get(
        f"{API_URL}/download/{task_id}"
    )
    
    if download_response.status_code == 200:
        with open('output.pdf', 'wb') as f:
            f.write(download_response.content)
        print(f"   已保存到: output.pdf")
    
    print("\n✓ 测试完成!")

if __name__ == "__main__":
    test_convert_office()
```

运行脚本：
```bash
python test_api.py
```

---

## 常见问题与解决方案

### Q1: 服务器无法启动

**错误**：`Address already in use`

**解决**：
```bash
# 查看占用 8000 端口的进程
netstat -ano | findstr :8000

# 或使用其他端口
python -m uvicorn app.main:app --port 8001
```

### Q2: 上传文件失败

**错误**：`413 Request Entity Too Large`

**解决**：
- 增加 `MAX_REQUEST_SIZE_MB` 配置
- 或上传较小的文件

### Q3: 转换失败

**检查项**：
1. 文件格式是否支持
2. 文件是否损坏
3. 查看服务器日志获取详细错误信息

### Q4: 无法访问 Swagger

**原因**：服务器未启动或端口配置错误

**解决**：
```bash
# 确认服务器正在运行
curl http://localhost:8000/

# 检查服务器日志
# 可能需要重新启动
```

---

## Swagger 界面说明

### 主要部分

1. **左侧菜单**：按标签分组的 API 接口
   - `/health` - 健康检查
   - `/convert` - 文件转换
   - `/status` - 任务状态查询
   - `/download` - 结果下载
   - `/image` - 图片压缩（阶段 2）
   - `/batch` - 批量处理（阶段 7）

2. **请求面板**
   - Method：HTTP 方法（GET、POST 等）
   - URL：完整的 API 端点
   - Parameters：输入参数
   - Request body：请求体

3. **响应面板**
   - Status code：HTTP 状态码
   - Response headers：响应头
   - Response body：响应内容

### 常用操作

| 操作 | 说明 |
|------|------|
| Try it out | 切换到测试模式 |
| Execute | 发送请求 |
| Cancel | 取消请求 |
| Clear | 清空输入 |

---

## 测试检查清单

- [ ] 服务器成功启动
- [ ] 能访问 Swagger UI（http://localhost:8000/docs）
- [ ] 健康检查 API 响应正常
- [ ] 能上传 Office 文件（DOCX/PPTX/XLSX）
- [ ] 能上传图片文件（JPG/PNG）
- [ ] 转换后能下载结果
- [ ] 任务状态查询功能正常
- [ ] 错误处理和错误信息合理

---

## 性能测试建议

### 简单压测
```bash
# 使用 Apache Bench
ab -n 100 -c 10 http://localhost:8000/

# 或使用 wrk
wrk -t4 -c100 -d30s http://localhost:8000/
```

### 并发文件上传测试
```bash
# 批量上传文件并测试并发
for i in {1..10}; do
  curl -X POST "http://localhost:8000/api/v1/convert" \
    -F "file=@test.jpg" &
done
wait
```

---

## 下一步

- ✅ 所有 API 端点验证
- ✅ 各文件格式支持验证
- ✅ 错误处理验证
- 📋 负载测试
- 📋 集成测试
- 📋 生产环境部署

---

**更新日期**：2025-12-06
