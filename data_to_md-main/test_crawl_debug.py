"""
调试脚本：复现 ConversionCache.get() 错误
"""
import asyncio
import traceback
import sys

# 确保项目路径在 sys.path 中
sys.path.insert(0, r"D:\Data Processing Module\data_to_md-main")

async def test_crawl():
    try:
        print("Step 1: 导入 WeChatCrawler...")
        from app.services.crawler.wechat_crawler import WeChatCrawler
        
        print("Step 2: 创建 WeChatCrawler 实例...")
        crawler = WeChatCrawler()
        
        print("Step 3: 调用 crawl_article...")
        result = await crawler.crawl_article(
            url="https://mp.weixin.qq.com/s/test",
            extract_images=False,
            timeout=30
        )
        
        print(f"Step 4: 结果 = {result}")
        
    except Exception as e:
        print(f"\n错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        print("\n完整堆栈:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_crawl())
