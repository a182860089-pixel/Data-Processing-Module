"""
API 转换测试脚本
测试 DOCX 文件转 PDF 的完整流程
"""
import requests
import json
import time

API_BASE_URL = "http://localhost:8000/api/v1"
TEST_FILE = "test_document.docx"

def test_convert():
    print("=" * 60)
    print("开始 API 测试")
    print("=" * 60)
    
    # 1. 检查服务器状态
    print("\n[1/4] 检查服务器状态...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print(f"✓ 服务器正常: {response.json()}")
        else:
            print(f"✗ 服务器错误: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ 无法连接服务器: {e}")
        return
    
    # 2. 上传并转换文件
    print(f"\n[2/4] 转换文件: {TEST_FILE}")
    
    try:
        with open(TEST_FILE, 'rb') as f:
            # 准备转换选项
            options = {
                "keep_layout": True,
                "office_dpi": 96
            }
            
            files = {'file': f}
            data = {'options': json.dumps(options)}
            
            print(f"  - 文件大小: {f.seek(0, 2)} bytes")
            f.seek(0)
            print(f"  - 转换选项: {json.dumps(options)}")
            
            response = requests.post(
                f"{API_BASE_URL}/convert",
                files=files,
                data=data
            )
        
        print(f"  - 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 转换成功!")
            print(f"  - Task ID: {result.get('task_id')}")
            print(f"  - 文件类型: {result.get('file_type')}")
            print(f"  - 成功状态: {result.get('success')}")
            
            task_id = result.get('task_id')
            
        else:
            print(f"✗ 转换失败: {response.text}")
            return
    
    except FileNotFoundError:
        print(f"✗ 文件不存在: {TEST_FILE}")
        return
    except Exception as e:
        print(f"✗ 上传失败: {e}")
        return
    
    # 3. 查询任务状态
    print(f"\n[3/4] 查询任务状态...")
    time.sleep(1)  # 等待一秒
    
    try:
        response = requests.get(f"{API_BASE_URL}/status/{task_id}")
        if response.status_code == 200:
            status = response.json()
            print(f"✓ 状态查询成功!")
            print(f"  - 任务状态: {status.get('status')}")
            print(f"  - 任务ID: {status.get('task_id')}")
        else:
            print(f"✗ 状态查询失败: {response.text}")
    except Exception as e:
        print(f"✗ 状态查询错误: {e}")
    
    # 4. 下载结果
    print(f"\n[4/4] 下载转换结果...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/download/{task_id}")
        if response.status_code == 200:
            # 保存到文件
            output_file = "converted_output.pdf"
            with open(output_file, 'wb') as f:
                f.write(response.content)
            print(f"✓ 下载成功!")
            print(f"  - 文件已保存: {output_file}")
            print(f"  - 文件大小: {len(response.content)} bytes")
        else:
            print(f"✗ 下载失败: {response.status_code}")
    except Exception as e:
        print(f"✗ 下载错误: {e}")
    
    print("\n" + "=" * 60)
    print("✓ 测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    test_convert()
