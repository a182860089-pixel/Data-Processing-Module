"""
测试无分页模式功能
"""
import requests
import json
import sys
from pathlib import Path


def test_with_pagination(pdf_path: str):
    """测试带分页模式(默认)"""
    print("\n" + "="*60)
    print("测试1: 带分页模式 (默认)")
    print("="*60)
    
    url = "http://localhost:8000/api/v1/convert"
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        data = {
            'options': json.dumps({
                'include_metadata': True,
                'no_pagination_and_metadata': False
            })
        }
        
        response = requests.post(url, files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 转换成功!")
        print(f"   任务ID: {result['task_id']}")
        print(f"   文件类型: {result['file_type']}")
        print(f"   处理页数: {result['metadata']['pages_processed']}")
        
        # 显示前500个字符
        markdown = result['markdown_content']
        print(f"\n📄 Markdown内容预览 (前500字符):")
        print("-" * 60)
        print(markdown[:500])
        print("-" * 60)
        
        # 检查是否包含元数据和页面标记
        has_metadata = markdown.startswith("---")
        has_page_marker = "<!-- Page" in markdown
        has_separator = "\n---\n" in markdown
        
        print(f"\n✓ 包含元数据: {has_metadata}")
        print(f"✓ 包含页面标记: {has_page_marker}")
        print(f"✓ 包含分隔符: {has_separator}")
        
        return result
    else:
        print(f"❌ 转换失败: {response.status_code}")
        print(f"   错误信息: {response.text}")
        return None


def test_without_pagination(pdf_path: str):
    """测试无分页模式"""
    print("\n" + "="*60)
    print("测试2: 无分页模式 (no_pagination_and_metadata=True)")
    print("="*60)
    
    url = "http://localhost:8000/api/v1/convert"
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        data = {
            'options': json.dumps({
                'no_pagination_and_metadata': True
            })
        }
        
        response = requests.post(url, files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 转换成功!")
        print(f"   任务ID: {result['task_id']}")
        print(f"   文件类型: {result['file_type']}")
        print(f"   处理页数: {result['metadata']['pages_processed']}")
        
        # 显示前500个字符
        markdown = result['markdown_content']
        print(f"\n📄 Markdown内容预览 (前500字符):")
        print("-" * 60)
        print(markdown[:500])
        print("-" * 60)
        
        # 检查是否不包含元数据和页面标记
        has_metadata = markdown.startswith("---")
        has_page_marker = "<!-- Page" in markdown
        has_separator = "\n---\n" in markdown
        
        print(f"\n✓ 不包含元数据: {not has_metadata}")
        print(f"✓ 不包含页面标记: {not has_page_marker}")
        print(f"✓ 不包含分隔符: {not has_separator}")
        
        # 验证结果
        if not has_metadata and not has_page_marker and not has_separator:
            print("\n🎉 无分页模式测试通过!")
        else:
            print("\n⚠️  警告: 无分页模式可能未正确工作")
            if has_metadata:
                print("   - 仍然包含元数据")
            if has_page_marker:
                print("   - 仍然包含页面标记")
            if has_separator:
                print("   - 仍然包含分隔符")
        
        return result
    else:
        print(f"❌ 转换失败: {response.status_code}")
        print(f"   错误信息: {response.text}")
        return None


def main():
    """主函数"""
    # 检查服务是否运行
    try:
        response = requests.get("http://localhost:8000/api/v1/health")
        if response.status_code != 200:
            print("❌ 服务未运行,请先启动服务: python app/main.py")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        print("   请先启动服务: python app/main.py")
        return
    
    # 使用测试PDF文件
    pdf_path = "docs/中华人民共和国学位法（有文本层）.pdf"
    
    if not Path(pdf_path).exists():
        print(f"❌ 测试文件不存在: {pdf_path}")
        print("\n可用的PDF文件:")
        docs_dir = Path("docs")
        if docs_dir.exists():
            for pdf in docs_dir.glob("*.pdf"):
                print(f"   - {pdf}")
        return
    
    print(f"\n📁 使用测试文件: {pdf_path}")
    
    # 运行测试
    result1 = test_with_pagination(pdf_path)
    result2 = test_without_pagination(pdf_path)
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    if result1 and result2:
        print("✅ 所有测试完成")
        print(f"\n带分页模式输出长度: {len(result1['markdown_content'])} 字符")
        print(f"无分页模式输出长度: {len(result2['markdown_content'])} 字符")
    else:
        print("❌ 部分测试失败")


if __name__ == "__main__":
    main()

